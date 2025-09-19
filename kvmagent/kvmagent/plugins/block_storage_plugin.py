import os.path
import random
import time

from kvmagent import kvmagent
from kvmagent.plugins.imagestore import ImageStoreClient
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import linux
from zstacklib.utils import log
from zstacklib.utils import shell
from zstacklib.utils import bash
from zstacklib.utils import lock
from zstacklib.utils import rbd

logger = log.get_logger(__name__)

INITIATOR_FILE_PATH = "/etc/iscsi/initiatorname.iscsi"


class RetryException(Exception):
    pass


class IOException(Exception):
    pass


class AgentRsp(object):
    def __init__(self):
        self.success = True
        self.error = None
        self.totalCapacity = None
        self.availableCapacity = None


class AgentCmd(object):
    def __init__(self):
        pass


class GetInitiatorNameRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(GetInitiatorNameRsp, self).__init__()
        self.initiatorName = None


class CreateHeartbeatCmd(AgentCmd):
    @log.sensitive_fields("iscsiChapUserPassword")
    def __init__(self):
        super(CreateHeartbeatCmd, self).__init__()
        self.wwn = None
        self.iscsiServerIp = None
        self.iscsiServerPort = None
        self.iscsiChapUserName = None
        self.iscsiChapUserPassword = None
        self.heartbeatInstallPath = None
        self.target = None


class DeleteHeartbeatCmd(AgentCmd):
    def __init__(self):
        super(DeleteHeartbeatCmd, self).__init__()
        self.heartbeatPath = None


class DiscoverLunCmd(CreateHeartbeatCmd):
    def __init__(self):
        super(DiscoverLunCmd, self).__init__()


class LogoutLunCmd(CreateHeartbeatCmd):
    def __init__(self):
        super(LogoutLunCmd, self).__init__()


class CreateHeartbeatRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(CreateHeartbeatRsp, self).__init__()


class DeleteHeartbeatRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(DeleteHeartbeatRsp, self).__init__()


class ResizeVolumeRsp(AgentRsp):
    def __init__(self):
        super(ResizeVolumeRsp, self).__init__()
        self.size = None


class NoFailurePingRsp(AgentRsp):
    def __init__(self):
        super(NoFailurePingRsp, self).__init__()
        self.disconnectedPSInstallPath = []


def get_block_storage_properties(install_path, ps_uuid_and_sys_id_host_id_mapping):
    if install_path is None:
        raise Exception("install path can not be null")
    ps_uuid = install_path.split("/")[-1].split("-")[-1]
    sys_id = ps_uuid_and_sys_id_host_id_mapping[ps_uuid]["sysId"]
    host_id = ps_uuid_and_sys_id_host_id_mapping[ps_uuid]["hostId"]
    if sys_id is None or host_id is None:
        raise Exception("ps uuid[%s] not found in sys id and host id mapping" % ps_uuid)
    return install_path, sys_id, host_id


def translate_absolute_path_from_wwn(wwn):
    if wwn is None:
        raise Exception("wwn can not be null")
    return "/dev/disk/by-id/wwn-0x" + wwn


def heartbeat_io_check(heartbeat_path, fs_id, host_id):
    rbd_rw_handler = rbd.get_rbd_rw_handler()
    hb_timestamp = time.time()
    hb_content = {
        "heartbeat_time": hb_timestamp
    }
    r = rbd_rw_handler.write(heartbeat_path, fs_id, host_id, 1024, jsonobject.dumps(hb_content))
    if not r:
        return False
    hb_content = rbd_rw_handler.read(heartbeat_path, fs_id, host_id, 1024)
    if hb_content is None:
        return False
    hb_content = jsonobject.loads(hb_content)
    hb_content_timestamp = hb_content["heartbeat_time"]
    if not hb_content_timestamp:
        return False
    if hb_content_timestamp == hb_timestamp:
        return True
    return False


class BlockStoragePlugin(kvmagent.KvmAgent):
    GET_INITIATOR_NAME_PATH = "/block/primarystorage/getinitiatorname"
    CREATE_HEART_BEAT_PATH = "/block/primarystorage/createheartbeat"
    DELETE_HEART_BEAT_PATH = "/block/primarystorage/deleteheartbeat"
    DOWNLOAD_FROM_IMAGESTORE = "/block/imagestore/download"
    UPLOAD_TO_IMAGESTORE = "/block/imagestore/upload"
    COMMIT_VOLUME_AS_IMAGE = "/block/imagestore/commit"
    DISCOVERY_LUN = "/block/primarystorage/discoverlun"
    LOGOUT_TARGET = "/block/primarystorage/logouttarget"
    NO_FAILURE_PING_PATH = "/block/primarystorage/ping"

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.GET_INITIATOR_NAME_PATH, self.get_initiator_name)
        http_server.register_async_uri(self.CREATE_HEART_BEAT_PATH, self.create_heartbeat, cmd=CreateHeartbeatCmd())
        http_server.register_async_uri(self.DELETE_HEART_BEAT_PATH, self.delete_heartbeat, cmd=DeleteHeartbeatCmd())
        http_server.register_async_uri(self.DOWNLOAD_FROM_IMAGESTORE, self.download_from_imagestore)
        http_server.register_async_uri(self.DISCOVERY_LUN, self.discover_lun, cmd=DiscoverLunCmd())
        http_server.register_async_uri(self.LOGOUT_TARGET, self.logout_target, cmd=LogoutLunCmd())
        http_server.register_async_uri(self.UPLOAD_TO_IMAGESTORE, self.upload_to_imagestore)
        http_server.register_async_uri(self.COMMIT_VOLUME_AS_IMAGE, self.commit_to_imagestore)
        http_server.register_async_uri(self.NO_FAILURE_PING_PATH, self.no_failure_ping)

        self.imagestore_client = ImageStoreClient()

    @kvmagent.replyerror
    def get_initiator_name(self, req):
        logger.debug("start to get host initiator")
        rsp = GetInitiatorNameRsp()
        initiator_name = linux.read_file(INITIATOR_FILE_PATH)
        file_content = initiator_name.splitlines()[0]
        rsp.initiatorName = file_content.split("InitiatorName=")[-1]
        rsp.success = True
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def delete_heartbeat(self, req):
        logger.debug("start to delete heartbeat")
        rsp = DeleteHeartbeatRsp()
        rsp.success = True
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    @lock.lock('iscsiadm')
    @bash.in_bash
    def create_heartbeat(self, req):
        logger.debug("starting to create heartbeat")
        rsp = CreateHeartbeatRsp()

        link_cmd = "ln -sf /usr/lib64/librbd.so /usr/lib64/librbd.so.1 && ln -sf /usr/lib64/librados.so /usr/lib64/librados.so.2"
        r, _, e = bash.bash_roe(link_cmd)
        if r != 0:
            rsp.success = False
            rsp.error = "can not create symbolic link for librbd.so and librados.so, cause %s" % e
            return jsonobject.dumps(rsp)

        rsp.success = True
        return jsonobject.dumps(rsp)

    def make_sure_lun_has_been_mapped(self, cmd_info):
        successfully_find_lun = False
        try:
            successfully_find_lun = self.check_lun_status(cmd_info)
        except Exception as e:
            pass
        if successfully_find_lun is True:
            return successfully_find_lun

        try:
            self._logout_target(cmd_info)
        except Exception as e:
            pass
        # just sleep 1 second
        time.sleep(1)
        self.iscsi_login(cmd_info)
        try:
            logger.debug("let's rescan scsi bus since can not find lun and try again")
            bash.bash_roe("timeout 120 /usr/bin/rescan-scsi-bus.sh -r >/dev/null")
            bash.bash_roe("timeout 120 /usr/bin/rescan-scsi-bus.sh -u >/dev/null")
        except Exception as e:
            pass
        successfully_find_lun = self.check_lun_status(cmd_info)
        return successfully_find_lun

    @linux.retry(times=20, sleep_time=random.uniform(1, 3))
    def wait_lun_ready(self, abs_path):
        if os.path.exists(abs_path) is True:
            logger.debug("successfully find lun wwn: " + abs_path)
            return

        logger.debug("Can not find lun wwn: " + abs_path + ", let's retry")
        raise RetryException("Can not find lun wwn: " + abs_path)

    def check_lun_status(self, cmd_info):
        abs_path = translate_absolute_path_from_wwn(cmd_info.wwn)
        self.wait_lun_ready(abs_path)
        return os.path.exists(abs_path)

    @kvmagent.replyerror
    def discover_lun(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = AgentRsp()

        return jsonobject.dumps(rsp)
        logger.debug("start to discover target:" + cmd.target)
        self.discovery_iscsi(cmd)
        iscsi_already_login = self.find_iscsi_session(cmd)
        if iscsi_already_login is True:
            logger.debug("iscsi already login, just to find lun")
        else:
            logger.debug("start to login")
            self.iscsi_login(cmd)
        rsp.success = self.make_sure_lun_has_been_mapped(cmd)
        if rsp.success is not True:
            rsp.error = "can not find lun: " + cmd.wwn
        return jsonobject.dumps(rsp)

    @bash.in_bash
    def discovery_iscsi(self, loginCmd):
        r, o, e = bash.bash_roe(
            "timeout 10 iscsiadm -m discovery --type sendtargets --portal %s" % (loginCmd.iscsiServerIp)
        )
        if r != 0:
            raise Exception("can not discovery iscsi portal %s, cause %s" % (
                loginCmd.iscsiServerIp, e))

    @bash.in_bash
    def find_iscsi_session(self, loginCmd):
        sid = bash.bash_o("iscsiadm -m session | grep %s:%s | grep %s | awk '{print $2}'" % (
            loginCmd.iscsiServerIp, loginCmd.iscsiServerPort, loginCmd.target)).strip("[]\n ")
        if sid == "" or sid is None:
            return False
        return True

    @kvmagent.replyerror
    def logout_target(self, req):
        rsp = AgentRsp
        rsp.success = True
        logout_cmd = jsonobject.loads(req[http.REQUEST_BODY])
        try:
            self._logout_target(logout_cmd)
        except Exception as e:
            rsp.success = False
            rsp.error = e.message
            logger.debug(e)
        return jsonobject.dumps(rsp)

    @linux.retry(times=10, sleep_time=random.uniform(1, 3))
    def wait_lun_deleted(self, abs_path):
        if os.path.exists(abs_path) is False:
            logger.debug("lun: %s has been deleted." % abs_path)
            return

        logger.debug("lun: " + abs_path + " still exists, let's retry")
        raise RetryException("fail to delete lun: " + abs_path)

    @bash.in_bash
    def _logout_target(self, logout_cmd):
        wwn = logout_cmd.wwn
        disk_path = translate_absolute_path_from_wwn(wwn)
        device_letter = bash.bash_o("ls -al %s | awk -F '/' '{print $NF}'" % disk_path).strip();
        linux.write_file("/sys/block/%s/device/delete" % device_letter, "1")
        self.wait_lun_deleted(disk_path)

        sid = bash.bash_o("iscsiadm -m session | grep %s:%s | grep %s | awk '{print $2}'" % (
            logout_cmd.iscsiServerIp, logout_cmd.iscsiServerPort, logout_cmd.target)).strip("[]\n ")
        if sid == "" or sid is None:
            return

        attached_lun = bash.bash_o("iscsiadm -m session -r %s -P 3 | grep 'Attached scsi disk' | grep 'running'" % sid)
        if attached_lun == "" or attached_lun is None:
            shell.call('timeout 10 iscsiadm --mode node --targetname "%s" -p %s:%s --logout' % (
                logout_cmd.target, logout_cmd.iscsiServerIp, logout_cmd.iscsiServerPort))

    @bash.in_bash
    def iscsi_login(self, loginCmd):
        already_login = self.find_iscsi_session(loginCmd)
        if already_login is True:
            return True
        target = loginCmd.target
        if loginCmd.iscsiChapUserName and loginCmd.iscsiChapUserPassword:
            bash.bash_o(
                'iscsiadm --mode node --targetname "%s" -p %s:%s --op=update --name node.session.auth.authmethod --value=CHAP' % (
                    target, loginCmd.iscsiServerIp, loginCmd.iscsiServerPort))
            bash.bash_o(
                'iscsiadm --mode node --targetname "%s" -p %s:%s --op=update --name node.session.auth.username --value=%s' % (
                    target, loginCmd.iscsiServerIp, loginCmd.iscsiServerPort, loginCmd.iscsiChapUserName))
            bash.bash_o(
                'iscsiadm --mode node --targetname "%s" -p %s:%s --op=update --name node.session.auth.password --value=%s' % (
                    target, loginCmd.iscsiServerIp, loginCmd.iscsiServerPort,
                    linux.shellquote(loginCmd.iscsiChapUserPassword)))
        r, o, e = bash.bash_roe('iscsiadm --mode node --targetname "%s" -p %s:%s --login' %
                                (target, loginCmd.iscsiServerIp, loginCmd.iscsiServerPort))
        if r != 0:
            raise Exception("fail to login iscsi %s")

        @linux.retry(times=5, sleep_time=random.uniform(1, 3))
        def retry_check_session(login_info):
            login = self.find_iscsi_session(login_info)
            if login is not True:
                raise Exception("fail to login iscsi %s")

        try:
            retry_check_session(loginCmd)
        except Exception as e:
            return False

        return True

        # check iscsi session

    @kvmagent.replyerror
    def download_from_imagestore(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        fmt = linux.get_img_fmt(cmd.backupStorageInstallPath)
        if not cmd.concurrency or cmd.concurrency <= 0:
            cmd.concurrency = 4
        primary_storage_install_path = "{0}:conf={1}".format(cmd.primaryStorageInstallPath, rbd.get_config_path_from_fs_id(cmd.primaryStorageSysId))
        linux.qcow2_convert_to_raw(cmd.backupStorageInstallPath, primary_storage_install_path,
                                   "-f", fmt, "-n", "-Wm", str(cmd.concurrency))
        rsp = AgentRsp()
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def upload_to_imagestore(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        cmd.primaryStorageInstallPath = "{0}:conf={1}".format(cmd.primaryStorageInstallPath, rbd.get_config_path_from_fs_id(cmd.primaryStorageSysId))
        return self.imagestore_client.upload_to_imagestore(cmd, req)

    @kvmagent.replyerror
    def commit_to_imagestore(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        return self.imagestore_client.commit_to_imagestore(cmd, req)

    def stop(self):
        pass

    @kvmagent.replyerror
    def no_failure_ping(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = NoFailurePingRsp()
        rsp.success = True
        for heartbeat_install_path in cmd.heartbeatInstallPath:
            heartbeat_path, fs_id, host_id = get_block_storage_properties(
                heartbeat_install_path,
                cmd.psUuidAndSysIdHostIdMapping
            )
            successfully_create_heartbeat = heartbeat_io_check(heartbeat_path, fs_id, host_id)
            if successfully_create_heartbeat is False:
                rsp.disconnectedPSInstallPath.append(heartbeat_install_path)
                error_msg = "fail to write heartbeat for ping, please check host connection with ps, heartbeat " \
                            "path: " + heartbeat_path
                logger.debug('heartbeat io check failed, cause: %s' % error_msg)
        return jsonobject.dumps(rsp)
