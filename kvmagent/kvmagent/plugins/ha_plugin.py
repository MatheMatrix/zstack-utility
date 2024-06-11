from kvmagent import kvmagent
from zstacklib.utils import bash
from zstacklib.utils import jsonobject
from zstacklib.utils import http
from zstacklib.utils import log
from zstacklib.utils import shell
from zstacklib.utils import linux
from zstacklib.utils import lvm
from zstacklib.utils import thread
from zstacklib.utils import qemu
from zstacklib.utils import qemu_img
from zstacklib.utils import ceph
from zstacklib.utils import sanlock
from zstacklib.utils import xmlobject
from zstacklib.utils import jsonobject
from zstacklib.utils import iscsi
import os.path
import time
import traceback
import threading
import rados
import rbd
import json
import math
from enum import Enum
from datetime import datetime, timedelta
from distutils.version import LooseVersion
import functools
import pprint
import inspect
import random
from zstacklib.utils import singleton
from zstacklib.utils import iproute
import zstacklib.utils.ip as ipUtils

logger = log.get_logger(__name__)

EOF = "this_is_end"

class UmountException(Exception):
    pass

class AgentRsp(object):
    def __init__(self):
        self.success = True
        self.error = None


class CephHostHeartbeatCheckRsp(AgentRsp):
    def __init__(self):
        super(CephHostHeartbeatCheckRsp, self).__init__()
        self.result = None
        self.vmUuids = []


class CheckFileSystemVmStateRsp(AgentRsp):
    def __init__(self):
        super(CheckFileSystemVmStateRsp, self).__init__()
        self.result = None
        self.vmUuids = []

class CheckShareBlockVmStateRsp(AgentRsp):
    def __init__(self):
        super(CheckShareBlockVmStateRsp, self).__init__()
        self.result = None
        self.vmUuids = []

class CheckIscsiVmStateRsp(AgentRsp):
    def __init__(self):
        super(CheckIscsiVmStateRsp, self).__init__()
        self.result = None
        self.vmUuids = []

class GetVmFencerRuleRsp(AgentRsp):
    def __init__(self):
        super(GetVmFencerRuleRsp, self).__init__()
        self.allowRules = None
        self.blockRules = None

class DelVpcHaFromHostRsp(AgentRsp):
    def __init__(self):
        super(DelVpcHaFromHostRsp, self).__init__()

class ScanRsp(AgentRsp):
    def __init__(self):
        super(ScanRsp, self).__init__()
        self.result = None


class SanlockScanRsp(AgentRsp):
    def __init__(self):
        super(SanlockScanRsp, self).__init__()
        self.result = None  # type: dict[str, bool]
        self.vmUuids = []


class ReportPsStatusCmd(object):
    def __init__(self):
        self.hostUuid = None
        self.psUuids = None
        self.psStatus = None
        self.reason = None

class ReportSelfFencerCmd(object):
    def __init__(self):
        self.hostUuid = None
        self.psUuids = None
        self.reason = None
        self.fencerFailure = None

class AbstractHaFencer(object):
    def __init__(self, interval, max_attempts, ps_uuid, run_fencer_list):
        self.interval = interval
        self.max_attempts = max_attempts
        self.ps_uuid = ps_uuid
        self.run_fencer_list = run_fencer_list
        self.failure = 0

    def reset_failure_count(self):
        self.failure = 0

    def write_fencer_heartbeat(self):
        pass

    def read_fencer_heartbeat(self, host_uuid, ps_uuid):
        pass

    def exec_fencer(self):
        pass

    def is_fencer_private_args_change(self, cmd):
        pass

    def update_ha_fencer(self, cmd, ha_fencer):
        pass

class AbstractStorageFencer(AbstractHaFencer):
    def __init__(self, interval, max_attempts, ps_uuid, run_fencer_list):
        super(AbstractStorageFencer, self).__init__(interval, max_attempts, ps_uuid, run_fencer_list)
        self.fencer_triggered_callback = None  # type: callable[list[str], str]
        self.report_storage_status_callback = None  # type: callable

    def get_ha_fencer_name(self):
        pass

    def write_fencer_heartbeat(self):
        pass

    def read_fencer_heartbeat(self, host_uuid, ps_uuid):
        pass

    def exec_fencer(self):
        pass

    def is_fencer_private_args_change(self, cmd):
        pass

    def update_ha_fencer(self, cmd, ha_fencer):
        pass

# TODO: sharedblock lun reader
    # def get_record_vm_lun(self, vg_uuid, host_uuid):
        # return '/dev/%s/host_%s' % (vg_uuid, host_uuid)

    # def read_fencer_heartbeat(self, host_uuid, vg_uuid):
    #     current_read_heartbeat_time = [None]
    #     current_vm_uuids = [None]
    #     volume_abs_path = self.get_record_vm_lun(vg_uuid, host_uuid)

    #     # writer has been moved to sharedblock agent, ZSTAC-58438
    #     def read_content_from_lv():
    #         with open(volume_abs_path, "r+") as f:
    #             content = f.read().strip().replace(b'\u0000', b'').replace(b'\x00', b'')
    #             content = content.split(EOF)[0]
    #             if len(content) == 0:
    #                 return None, None

    #             sbl_data = json.loads(content)
    #             current_read_heartbeat_time[0] = int(sbl_data.get('heartbeat_time'))
    #             if sbl_data.get('vm_uuids') is None:
    #                 current_vm_uuids[0] = []
    #             else:
    #                 current_vm_uuids[0] = sbl_data.get('vm_uuids').split(',')

    #             logger.debug("read shareblock current_read_heartbeat_time:%s, current_vm_uuids: %s" %
    #                          (current_read_heartbeat_time[0], current_vm_uuids[0]))

    #             if int(time.time()) - 4 * 60 < current_read_heartbeat_time[0]:
    #                 current_read_heartbeat_time[0] += random.randint(1, 100)

    #             return current_read_heartbeat_time[0], current_vm_uuids[0]

    #     if os.path.exists(volume_abs_path):
    #         return read_content_from_lv()

    #     r, o, e = bash.bash_roe("timeout -s SIGKILL %s lvchange -asy %s" % (self.storage_timeout, volume_abs_path))
    #     if r == 0:
    #         return read_content_from_lv()

    #     return None, None

# TODO: sblk fencer args updated

last_multipath_run = time.time()
QEMU_VERSION = qemu.get_version()
LIBVIRT_VERSION = linux.get_libvirt_version()
host_storage_name = "hostStorageState"
LIVE_LIBVIRT_XML_DIR = "/var/run/libvirt/qemu"
global_allow_fencer_rule = {} # type: dict[str, list]
global_block_fencer_rule = {} # type: dict[str, list]
global_fencer_rule_lock = threading.Lock()
SHAREBLOCK_VM_HA_PARAMS_PATH = "/var/run/zstack/shareBlockVmHaParams"
WRITE_SHAREBLOCKVMHAPARAMS_LOCK = threading.Lock()


def create_shareblock_vm_ha_params(cmd):
    with WRITE_SHAREBLOCKVMHAPARAMS_LOCK:
        if os.path.exists(SHAREBLOCK_VM_HA_PARAMS_PATH):
            return
        with open(SHAREBLOCK_VM_HA_PARAMS_PATH, "w") as f:
            f.write(jsonobject.dumps(cmd))


def update_shareblock_vm_ha_params(vg_uuids, fencer_cmd=None):
    with WRITE_SHAREBLOCKVMHAPARAMS_LOCK:
        if not os.path.exists(SHAREBLOCK_VM_HA_PARAMS_PATH):
            return
        with open(SHAREBLOCK_VM_HA_PARAMS_PATH, 'r+') as f:
            cmd = f.read().strip()
            if len(cmd) == 0 or cmd == '{}':
                return

            cmd_json = json.loads(cmd)
            if fencer_cmd:
                cmd_json.update(fencer_cmd.__dict__)
            cmd_json["vgUuids"] = vg_uuids
            f.seek(0)
            f.truncate(0)
            f.write(jsonobject.dumps(cmd_json))


def remove_shareblock_vm_ha_params():
    with WRITE_SHAREBLOCKVMHAPARAMS_LOCK:
        if os.path.exists(SHAREBLOCK_VM_HA_PARAMS_PATH):
            os.remove(SHAREBLOCK_VM_HA_PARAMS_PATH)

def add_fencer_rule(cmd):
    with global_fencer_rule_lock:
        global global_allow_fencer_rule
        global_allow_fencer_rule.update(
            {rule['fencerName']: global_allow_fencer_rule.get(rule['fencerName'], []) + rule['vmUuids'] for rule in cmd['allowRules']})
        global global_block_fencer_rule
        global_block_fencer_rule.update(
            {rule['fencerName']: global_block_fencer_rule.get(rule['fencerName'], []) + rule['vmUuids'] for rule in cmd['blockRules']})
        logger.debug("add fencer rules %s, global allow fencer: %s, global block fencer: %s" %
                     (jsonobject.dumps(cmd), global_allow_fencer_rule, global_block_fencer_rule))


def remove_fencer_rule(cmd):
    with global_fencer_rule_lock:
        if cmd["allowRules"]:
            global global_allow_fencer_rule
            for rule in cmd["allowRules"]:
                if rule["fencerName"] not in global_allow_fencer_rule:
                    continue
                global_allow_fencer_rule[rule["fencerName"]] = \
                    [vm_uuid for vm_uuid in global_allow_fencer_rule[rule["fencerName"]] if vm_uuid not in rule["vmUuids"]]
                logger.debug("remove allow fencer rule %s, global allow fencer[%s]: %s" %
                             (jsonobject.dumps(cmd), rule["fencerName"], global_allow_fencer_rule[rule["fencerName"]]))

        if cmd["blockRules"]:
            global global_block_fencer_rule
            for rule in cmd["blockRules"]:
                if rule["fencerName"] not in global_block_fencer_rule:
                    continue
                global_block_fencer_rule[rule["fencerName"]] = \
                    [vm_uuid for vm_uuid in global_block_fencer_rule[rule["fencerName"]] if vm_uuid not in rule["vmUuids"]]
                logger.debug("remove block fencer rule %s, global block fencer[%s]: %s" %
                             (jsonobject.dumps(cmd), rule["fencerName"], global_block_fencer_rule[rule["fencerName"]]))


def is_allow_fencer(fencer_name, vm_uuid):
    with global_fencer_rule_lock:
        global global_allow_fencer_rule
        logger.debug("global allow fencer: %s" % global_allow_fencer_rule)
        if fencer_name in global_allow_fencer_rule:
            return vm_uuid in global_allow_fencer_rule[fencer_name]
        return False


def is_block_fencer(fencer_name, vm_uuid):
    with global_fencer_rule_lock:
        global global_block_fencer_rule
        logger.debug("global block fencer: %s" % global_block_fencer_rule)
        if fencer_name in global_block_fencer_rule:
            return vm_uuid in global_block_fencer_rule[fencer_name]
        return False


def clean_network_config(vm_uuids):
    for c in kvmagent.ha_cleanup_handlers:
        logger.debug('clean network config handler: %s\n' % c)
        thread.ThreadFacade.run_in_thread(c, (vm_uuids,))

zstack_uuid_pattern = "'[0-9a-f]{8}[0-9a-f]{4}[1-5][0-9a-f]{3}[89ab][0-9a-f]{3}[0-9a-f]{12}'"

def find_vm_uuid_list_by_process():
    vm_in_process_uuid_list = shell.call("ps -ef | grep -P -o '(qemu-kvm|qemu-system).*?-name\s+(guest=)?\K.*?,' | sed 's/.$//'")
    return vm_in_process_uuid_list.splitlines()

def find_vm_uuid_list_by_virsh():
    vm_in_virsh_uuid_list = shell.call("virsh list | egrep -o %s" % zstack_uuid_pattern + " | sort | uniq")
    return vm_in_virsh_uuid_list.splitlines()

def find_ps_running_vm(store_uuid):
    vm_in_process_uuid_list = find_vm_uuid_list_by_virsh()

    vm_in_ps_uuid_list = []
    for vm_uuid in vm_in_process_uuid_list:
        out = bash.bash_o("virsh dumpxml %s | grep '<source' | head -1 | grep %s" % (vm_uuid.strip(), store_uuid)).strip().splitlines()
        if len(out) != 0:
            vm_in_ps_uuid_list.append(vm_uuid.strip())
    logger.debug('vm_in_ps_%s_uuid_list:' % store_uuid + str(vm_in_ps_uuid_list))
    return vm_in_ps_uuid_list

def not_exec_kill_vm(strategy, vm_uuid, fencer_name):
    return strategy == 'Permissive' and not is_allow_fencer(fencer_name, vm_uuid)


def kill_vm_by_xml(maxAttempts, strategy, mountPath, isFlushbufs = True):
    vm_pids_dict, on_storage_vm_uuids = get_runnning_vm_root_volume_on_ps(maxAttempts, strategy, mountPath, isFlushbufs)
    reason = "because we lost connection to the storage, failed to read the heartbeat file %s times" % maxAttempts
    kill_vm_use_pid(vm_pids_dict, reason)
    return vm_pids_dict, on_storage_vm_uuids


@bash.in_bash
def get_runnning_vm_root_volume_on_ps(maxAttempts, strategy, mountPath, isFlushbufs = True, vm_uuid_only = False):
    # 1. get root volume from live vm xml
    # 2. make sure io has error
    # 3. filter for mountPaths
    vm_pids_dict = {}
    on_storage_vm_uuids = []
    for file_name in linux.listdir(LIVE_LIBVIRT_XML_DIR):
        xs = file_name.split(".")
        if len(xs) != 2 or xs[1] != "xml":
            continue

        xml = linux.read_file(os.path.join(LIVE_LIBVIRT_XML_DIR, file_name))
        if not mountPath in xml:
            continue

        vm = linux.VmStruct()
        vm.uuid = xs[0]
        if not vm.root_volume:
            logger.warn("found strange vm[pid: %s, uuid: %s], can not find boot volume" % (vm.pid, vm.uuid))
            continue

        if not mountPath in vm.root_volume:
            continue

        on_storage_vm_uuids.append(vm.uuid)
        if is_allow_fencer(host_storage_name, vm.uuid):
            logger.debug("fencer detect ha strategy is %s skip fence vm[uuid:%s]" % (strategy, vm.uuid))
            continue

        if isFlushbufs:
            r = bash.bash_r("timeout 5 blockdev --flushbufs %s" % vm.root_volume)
            if r == 0:
                logger.debug("volume %s for vm %s io success, skiped" % (vm.root_volume, vm.uuid))
                continue

        if vm_uuid_only:
            vm_pids_dict[vm.uuid] = None
            on_storage_vm_uuids.append(vm.uuid)
            continue

        vm.pid = linux.get_vm_pid(vm.uuid)
        vm.load_from_xml(xml)

        vm_pids_dict[vm.uuid] = vm.pid
    return vm_pids_dict, on_storage_vm_uuids


def kill_vm(maxAttempts, strategy, mountPaths=None, isFileSystem=None):
    virsh_list = shell.call("virsh list --all")
    logger.debug("virsh_list:\n" + virsh_list)
    
    vm_in_process_uuid_list = find_vm_uuid_list_by_process()
    logger.debug('vm_in_process_uuid_list:\n' + '\n'.join(vm_in_process_uuid_list))

    # kill vm's qemu process
    vm_pids_dict = {}
    on_storage_vm_uuids = []
    for vm_uuid in vm_in_process_uuid_list:
        vm_uuid = vm_uuid.strip()
        if not vm_uuid:
            continue

        if mountPaths and isFileSystem is not None \
                and not need_kill(vm_uuid, mountPaths, isFileSystem):
            continue

        on_storage_vm_uuids.append(vm_uuid)
        if not_exec_kill_vm(strategy, vm_uuid, host_storage_name):
            logger.debug("fencer detect ha strategy is %s skip fence vm[uuid:%s]" % (strategy, vm_uuid))
            continue

        vm_pid = linux.find_vm_pid_by_uuid(vm_uuid)
        if not vm_pid:
            logger.warn('vm %s pid not found' % vm_uuid)
            continue

        vm_pids_dict[vm_uuid] = vm_pid
    reason = "because we lost connection to the storage, failed to read the heartbeat file %s times" % maxAttempts
    kill_vm_use_pid(vm_pids_dict, reason)
    return vm_pids_dict, on_storage_vm_uuids

def kill_vm_use_pid(vm_pids_dict, reason):
    for vm_uuid, vm_pid in vm_pids_dict.items():
        kill = shell.ShellCmd('kill -9 %s' % vm_pid)
        kill(False)
        if kill.return_code == 0:
            logger.warn('kill the vm[uuid:%s, pid:%s] %s' % (vm_uuid, vm_pid, reason))
        else:
            logger.warn('failed to kill the vm[uuid:%s, pid:%s] %s' % (vm_uuid, vm_pid, kill.stderr))


def mount_path_is_nfs(mount_path):
    typ = shell.call("mount | grep '%s' | awk '{print $5}'" % mount_path)
    return typ.startswith('nfs')


@linux.retry(times=8, sleep_time=2)
def do_kill_and_umount(mount_path, is_nfs):
    kill_progresses_using_mount_path(mount_path)
    umount_fs(mount_path, is_nfs)


def kill_and_umount(mount_path, is_nfs):
    do_kill_and_umount(mount_path, is_nfs)
    if is_nfs:
        shell.ShellCmd("systemctl start nfs-client.target")(False)


def umount_fs(mount_path, is_nfs):
    if is_nfs:
        shell.ShellCmd("systemctl stop nfs-client.target")(False)
        time.sleep(2)
    o = shell.ShellCmd("umount -f %s" % mount_path)
    o(False)
    if o.return_code != 0:
        raise UmountException(o.stderr)


def kill_progresses_using_mount_path(mount_path):
    o = shell.ShellCmd("pkill -9 -e -f '%s'" % mount_path)
    o(False)
    logger.warn('kill the progresses with mount path: %s, killed process: %s' % (mount_path, o.stdout))

# TODO: fix this
def get_block_vm_root_volume_path(vm_uuid, root_volume_path):
    vm = vm_plugin.get_vm_by_uuid(vm_uuid)
    sysinfo = vm.domain_xmlobject.sysinfo
    if xmlobject.has_element(sysinfo, "oemStrings") is not True:
        return root_volume_path

    oem_strings = sysinfo.oemStrings.get_child_node_as_list('entry')
    for oem_string in oem_strings:
        if oem_string.text_.startswith("storage:"):
            return oem_string.text_.replace("storage:", "") + root_volume_path

    return root_volume_path


def get_running_vm_root_volume_path(vm_uuid, is_file_system):
    # 1. get "-drive ... -device ... bootindex=1,
    # 2. get "-boot order=dc ... -drive id=drive-virtio-disk"
    # 3. make sure io has error
    # 4. filter for pv
    out = linux.find_vm_process_by_uuid(vm_uuid)
    if not out:
        logger.warn("can not find process of vm[uuid: %s]" % vm_uuid)
        return None

    pid = out.split(" ")[0]
    cmdline = out.split(" ", 3)[-1]
    if "bootindex=1" in cmdline:
        root_volume_path = find_root_volume_with_bootindex_from_ps_output(cmdline, vm_uuid, is_file_system)
    elif " -boot order=dc" in cmdline:
        # TODO: maybe support scsi volume as boot volume one day
        root_volume_path = find_root_volume_with_bootorder_from_ps_output(cmdline)
    else:
        logger.warn("found strange vm[pid: %s, cmdline: %s], can not find boot volume" % (pid, cmdline))
        return None

    if not root_volume_path:
        logger.warn("failed to find vm[uuid: %s] root volume path,"
                    " dump process info for debug, process dump:\n %s" % (vm_uuid, out))
    else:
        logger.debug("find vm[uuid: %s] root volume path %s" % (vm_uuid, root_volume_path))

    if is_file_system:
        if "/dev/disk/by-id/wwn" in root_volume_path:
            return get_block_vm_root_volume_path(vm_uuid, root_volume_path)
        return root_volume_path

    return root_volume_path.replace("rbd:", "")


def find_root_volume_with_bootindex_and_file_system_from_ps_output(cmdline):
    parts = cmdline.split("bootindex=1")
    if len(parts) <= 1:
        return None

    filename_parts = parts[0].split('filename')
    if len(filename_parts) > 1:
        return filename_parts[-1].split('"')[2]

    drive_parts = parts[0].split(" -drive file=")
    if len(drive_parts) > 1:
        return drive_parts[-1].split(",")[0]

    return None


def find_root_volume_with_bootindex_from_ps_output(cmdline, vm_uuid, is_file_system):
    # try to get vm running qemu version
    qemu_version = qemu.get_running_version(vm_uuid)
    if qemu_version == "":
        qemu_version = QEMU_VERSION

    if LooseVersion(LIBVIRT_VERSION) >= LooseVersion("6.0.0") and LooseVersion(qemu_version) >= LooseVersion("4.2.0"):
        if is_file_system:
            root_volume_path = find_root_volume_with_bootindex_and_file_system_from_ps_output(cmdline)
        else:
            root_volume_path = cmdline.split("bootindex=1")[0].split('image')[0].split('"')[-3] + '/'
    else:
        root_volume_path = cmdline.split("bootindex=1")[0].split(" -drive file=")[-1].split(",")[0]

    return root_volume_path

def find_root_volume_with_bootorder_from_ps_output(cmdline):
    return cmdline.split("id=drive-virtio-disk0")[0].split(" -drive file=")[-1].split(",")[0]

def need_kill(vm_uuid, storage_paths, is_file_system):
    vm_path = get_running_vm_root_volume_path(vm_uuid, is_file_system)

    if not vm_path or vm_path == "" or any([vm_path.startswith(ps_path) for ps_path in storage_paths]):
        return True

    return False

def login_heartbeat_path(url):
    if not url.startswith("iscsi://"):
        raise Exception("unsupported install path[%s]" % url)
    heartbeat_path = iscsi.connect_iscsi_target(url, connect_all=True)

    def wait_device_to_show(_):
        return os.path.exists(heartbeat_path)

    if not linux.wait_callback_success(wait_device_to_show, timeout=30, interval=0.5):
        raise Exception('ISCSI device[%s] is not shown up after 30s' % heartbeat_path)
    return heartbeat_path


class HaPlugin(kvmagent.KvmAgent):
    SCAN_HOST_PATH = "/ha/scanhost"
    SANLOCK_SCAN_HOST_PATH = "/sanlock/scanhost"
    CEPH_HOST_HEARTBEAT_CHECK_PATH = "/ceph/host/heartbeat/check"
    SETUP_SELF_FENCER_PATH = "/ha/selffencer/setup"
    CANCEL_SELF_FENCER_PATH = "/ha/selffencer/cancel"
    CEPH_SELF_FENCER = "/ha/ceph/setupselffencer"
    CANCEL_CEPH_SELF_FENCER = "/ha/ceph/cancelselffencer"
    SHAREDBLOCK_SELF_FENCER = "/ha/sharedblock/setupselffencer"
    CANCEL_SHAREDBLOCK_SELF_FENCER = "/ha/sharedblock/cancelselffencer"
    ALIYUN_NAS_SELF_FENCER = "/ha/aliyun/nas/setupselffencer"
    CANCEL_NAS_SELF_FENCER = "/ha/aliyun/nas/cancelselffencer"
    ISCSI_SELF_FENCER = "/ha/iscsi/setupselffencer"
    CANCEL_ISCSI_SELF_FENCER = "/ha/iscsi/cancelselffencer"
    BLOCK_SELF_FENCER = "/ha/block/setupselffencer"
    CANCEL_BLOCK_SELF_FENCER = "/ha/block/cancelselffencer"
    FILESYSTEM_CHECK_VMSTATE_PATH = "/filesystem/check/vmstate"
    SHAREDBLOCK_CHECK_VMSTATE_PATH = "/sharedblock/check/vmstate"
    ISCSI_CHECK_VMSTATE_PATH = "/iscsi/check/vmstate"
    ADD_VM_FENCER_RULE_TO_HOST = "/add/vm/fencer/rule/to/host"
    REMOVE_VM_FENCER_RULE_FROM_HOST = "/remove/vm/fencer/rule/from/host"
    GET_VM_FENCER_RULE = "/get/vm/fencer/rule/"
    CBD_SETUP_SELF_FENCER_PATH = "/ha/cbd/setupselffencer"

    RET_SUCCESS = "success"
    RET_FAILURE = "failure"
    RET_NOT_STABLE = "unstable"
    STORAGE_DISCONNECTED = "Disconnected"
    STORAGE_CONNECTED = "Connected"

    def __init__(self):
        # {ps_uuid: created_time} e.g. {'07ee15b2f68648abb489f43182bd59d7': 1544513500.163033}
        self.run_fencer_timestamp = {}  # type: dict[str, float]
        self.fencer_fire_timestamp = {}  # type: dict[str, float]
        self.global_storage_ha = []
        self.storage_status = {}  # type: dict[str, float]
        self.fencer_lock = threading.RLock()
        self.sblk_fencer_running = False
        self.abstract_ha_fencer_checker = {}
        self.vpc_uuids = []
        self.vpc_lock = threading.RLock()

    @kvmagent.replyerror
    def cancel_ceph_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        self.cancel_fencer(cmd.uuid)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def cancel_filesystem_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        for ps_uuid in cmd.psUuids:
            self.cancel_fencer(ps_uuid)

        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def cancel_aliyun_nas_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        self.cancel_fencer(cmd.uuid)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def cancel_block_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        self.cancel_fencer(cmd.uuid)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def cancel_iscsi_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        self.cancel_fencer(cmd.uuid)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def setup_aliyun_nas_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        # TODO: fix aliyun nas url
        mount_point = FileSystemMountPoint(cmd.url, cmd.mountPath, True, None)
        fencer = FileSystemFencer(cmd.uuid,
                                       cmd.maxAttempts,
                                       cmd.interval,
                                       cmd.storageCheckerTimeout,
                                       cmd.strategy,
                                       cmd.hostUuid,
                                       mount_point)
        fencer_manager.register_fencer(fencer)
        fencer_manager.start_fencer(fencer)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def setup_block_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        created_time = time.time()
        self.setup_fencer(cmd.uuid, created_time)
        install_path = cmd.installPath
        heart_beat_wwn_path = install_path.replace("block://", "/dev/disk/by-id/wwn-0x")
        rsp = AgentRsp()

        if os.path.exists(heart_beat_wwn_path) is not True:
            try:
                bash.bash_roe("timeout 120 /usr/bin/rescan-scsi-bus.sh -u >/dev/null")
            except Exception as e:
                pass

        # recheck wwn path
        if os.path.exists(heart_beat_wwn_path) is not True:
            err_msg = "fail to find heartbeat lun, please make sure host is connected with ps";
            logger.debug(err_msg)
            rsp.success = False
            rsp.error = err_msg
            return jsonobject.dumps(rsp)

        block_fencer = BlockStorageFencer(cmd, heart_beat_wwn_path)
        fencer_manager.register_fencer(block_fencer)
        fencer_manager.start_fencer(block_fencer)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def setup_cbd_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        created_time = time.time()
        self.setup_fencer(cmd.uuid, created_time)

        @thread.AsyncThread
        def heartbeat_on_cbd(ps_uuid, covering_paths):
            fencer_list = []
            if cmd.fencers is not None:
                fencer_list = cmd.fencers

            if host_storage_name in fencer_list:
                fencer_list.append(CbdHeartbeatController.ha_fencer_name)

            cbd_controller = CbdHeartbeatController(cmd.interval, cmd.maxAttempts, ps_uuid, fencer_list)
            cbd_controller.covering_paths = covering_paths
            cbd_controller.report_storage_status = False
            cbd_controller.storage_failure = False
            cbd_controller.failure = 0
            cbd_controller.strategy = cmd.strategy
            cbd_controller.storage_check_timeout = cmd.storageCheckerTimeout
            cbd_controller.host_uuid = cmd.hostUuid
            cbd_controller.host_id = cmd.hostId
            cbd_controller.heartbeat_required_space = cmd.heartbeatRequiredSpace
            cbd_controller.heartbeat_path = cmd.heartbeatUrl
            cbd_controller.heartbeat_url = cmd.heartbeatUrl
            cbd_controller.fencer_triggered_callback = self.report_self_fencer_triggered
            cbd_controller.report_storage_status_callback = self.report_storage_status

            self.setup_fencer(ps_uuid, created_time)
            update_fencer = True
            try:
                fencer_init = {cbd_controller.get_ha_fencer_name(): cbd_controller}
                logger.debug("cbd start run fencer list :%s" % ",".join(fencer_list))
                while self.run_fencer(ps_uuid, created_time):
                    time.sleep(cmd.interval)
                    cbd_controller.exec_fencer_list(fencer_init, update_fencer)
                    update_fencer = False

                logger.debug('stop self-fencer on of cbd protocol storage ' + ps_uuid)
            except Exception as e:
                logger.debug('self-fencer on cbd protocol storage %s stopped abnormally, %s' % (ps_uuid, e))
                content = traceback.format_exc()
                logger.warn(content)
                self.report_storage_status([cmd.uuid], self.STORAGE_DISCONNECTED)

        heartbeat_on_cbd(cmd.uuid, cmd.coveringPaths)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def setup_iscsi_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        created_time = time.time()
        self.setup_fencer(cmd.uuid, created_time)

        heartbeat_path = login_heartbeat_path(cmd.heartbeatUrl)

        iscsi_fencer = IscsiFencer(cmd, heartbeat_path, cmd.coveringPaths)
        fencer_manager.register_fencer(iscsi_fencer)
        fencer_manager.start_fencer(iscsi_fencer)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def cancel_sharedblock_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        fencer_manager.stop_fencer(cmd.uuid)
        fencer_manager.unregister_fencer(cmd.uuid)
        return jsonobject.dumps(AgentRsp())

    def setup_sharedblock_self_fencer_from_json(self, cmd):
        # setup sharedblock agent parameters
        sblk_fencer = SharedBlockStorageFencer(cmd)
        fencer_manager.register_fencer(sblk_fencer)
        fencer_manager.start_fencer(sblk_fencer)

        # setup sharedblock check based on sanlock
        sanlock_vg_fencer = SanlockVolumeGroupFencer(cmd)
        fencer_manager.register_fencer(sanlock_vg_fencer)
        fencer_manager.start_fencer(sanlock_vg_fencer)

    @kvmagent.replyerror
    def setup_sharedblock_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        self.setup_sharedblock_self_fencer_from_json(cmd)
        return jsonobject.dumps(AgentRsp())

    @kvmagent.replyerror
    def setup_ceph_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        mon_url = '\;'.join(cmd.monUrls)
        mon_url = mon_url.replace(':', '\\\:')

        for pool_name in cmd.poolNames:
            ceph_fencer = CephFencer("%s-%s" % (cmd.uuid, pool_name),
                                     pool_name,
                                     cmd)
            fencer_manager.register_fencer(ceph_fencer)
            fencer_manager.start_fencer(ceph_fencer)

        return jsonobject.dumps(AgentRsp())

    def try_remount_fs(self, mount_path, ps_uuid, created_time, file_system_controller, url, options):
        if mount_path_is_nfs(mount_path):
            shell.run("systemctl start nfs-client.target")

        while self.run_fencer(ps_uuid, created_time):
            if linux.is_mounted(path=mount_path) and file_system_controller.update_heartbeat_file():
                self.report_storage_status([ps_uuid], 'Connected')
                logger.debug("fs[uuid:%s] is reachable again, report to management" % ps_uuid)
                break
            try:
                logger.debug('fs[uuid:%s] is unreachable, it will be remounted after 180s' % ps_uuid)
                time.sleep(180)
                if not self.run_fencer(ps_uuid, created_time):
                    break
                linux.remount(url, mount_path, options)
                self.report_storage_status([ps_uuid], 'Connected')
                logger.debug("remount fs[uuid:%s] success, report to management" % ps_uuid)
                break
            except:
                logger.warn('remount fs[uuid:%s] fail, try again soon' % ps_uuid)
                kill_progresses_using_mount_path(mount_path)

        logger.debug('stop remount fs[uuid:%s]' % ps_uuid)

    @kvmagent.replyerror
    def setup_self_fencer(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        for mount_path, uuid, mounted_by_zstack, url, options in zip(cmd.mountPaths, cmd.uuids, cmd.mountedByZStack, cmd.urls, cmd.mountOptions):
            if not linux.timeout_isdir(mount_path):
                raise Exception('the mount path[%s] is not a directory' % mount_path)

            # file_system_controller = FileSystemHeartbeatController(cmd.interval, cmd.maxAttempts, ps_uuid, None)
            # file_system_controller.fencer_triggered_callback = self.report_self_fencer_triggered
            # file_system_controller.try_remount_fs_callback = self.try_remount_fs
            mount_point = FileSystemMountPoint(url, mount_path, mounted_by_zstack, options)
            fencer = FileSystemFencer(uuid,
                                       cmd.maxAttempts,
                                       cmd.interval,
                                       cmd.storageCheckerTimeout,
                                       cmd.strategy,
                                       cmd.hostUuid,
                                       mount_point)
            fencer_manager.register_fencer(fencer)
            fencer_manager.start_fencer(fencer)

        return jsonobject.dumps(AgentRsp())


    @kvmagent.replyerror
    def scan_host(self, req):
        rsp = ScanRsp()

        success = 0
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        for i in range(0, cmd.times):
            if shell.run("nmap --host-timeout 10s -sP -PI %s --disable-arp-ping | grep -q 'Host is up'" % cmd.ip) == 0:
                success += 1

            if success == cmd.successTimes:
                rsp.result = self.RET_SUCCESS
                return jsonobject.dumps(rsp)

            time.sleep(cmd.interval)

        if success == 0:
            rsp.result = self.RET_FAILURE
            return jsonobject.dumps(rsp)

        # WE SUCCEED A FEW TIMES, IT SEEMS THE CONNECTION NOT STABLE
        success = 0
        for i in range(0, cmd.successTimes):
            if shell.run("nmap --host-timeout 10s -sP -PI %s --disable-arp-ping | grep -q 'Host is up'" % cmd.ip) == 0:
                success += 1

            time.sleep(cmd.successInterval)

        if success == cmd.successTimes:
            rsp.result = self.RET_SUCCESS
            return jsonobject.dumps(rsp)

        if success == 0:
            rsp.result = self.RET_FAILURE
            return jsonobject.dumps(rsp)

        rsp.result = self.RET_NOT_STABLE
        logger.info('scanhost[%s]: %s' % (cmd.ip, rsp.result))
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def file_system_check_vmstate(self, req):
        rsp = CheckFileSystemVmStateRsp()
        rsp.result = {}

        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        ps_uuid = cmd.primaryStorageUuid
        record_vm_running_path = FileSystemFencer.format_heartbeat_path(cmd.mountPath, cmd.targetHostUuid)
        if not os.path.exists(record_vm_running_path):
            rsp.result[ps_uuid] = False
            return jsonobject.dumps(rsp)

        logger.debug("check if host[%s] is still alive" % cmd.targetHostUuid)
        heartbeat_success, vm_running_uuids = FileSystemFencer.read_heartbeat_file(record_vm_running_path)
        result = {ps_uuid: heartbeat_success}
        rsp.result = result
        rsp.vmUuids = vm_running_uuids
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def ceph_host_heartbeat_check(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = CephHostHeartbeatCheckRsp()

        ceph_controller = CephHeartbeatController(cmd.interval, cmd.times, cmd.primaryStorageUuid, None)
        result = {}
        runningVms = []

        ceph_conf, keyring_path, username = ceph.get_ceph_client_conf(cmd.primaryStorageUuid, cmd.manufacturer)

        if not os.path.exists(ceph_conf):
            rsp.success = False
            return jsonobject.dumps(rsp)

        additional_conf_dict = {}
        if keyring_path:
            # use additional_conf_dict to make keyring file a config of Rados connection
            # and resolve compatibility issue of open-source and other types of ceph storage.
            additional_conf_dict['keyring'] = keyring_path

        for pool_name in cmd.poolNames:
            image = None
            with rados.Rados(conffile=ceph_conf, conf=additional_conf_dict, name=username) as cluster:
                with cluster.open_ioctx(pool_name) as ioctx:
                    heartbeat_object_name = ceph.get_heartbeat_object_name(cmd.primaryStorageUuid, cmd.targetHostUuid)
                    if not heartbeat_object_name:
                        logger.debug("Failed to get heartbeat file info of pool %s" % pool_name)
                        continue

                    ceph_controller.ioctx = ioctx
                    ceph_controller.heartbeat_object_name = heartbeat_object_name
                    ceph_controller.host_uuid = cmd.targetHostUuid
                    ceph_controller.storage_check_timeout = cmd.storageCheckerTimeout
                    ceph_controller.max_attempts = cmd.times
                    ceph_controller.interval = cmd.interval

                    heartbeat_success, vm_uuids = ceph_controller.check_fencer_heartbeat(
                        ceph_controller.host_uuid, ceph_controller.storage_check_timeout, ceph_controller.interval,
                        ceph_controller.max_attempts, cmd.primaryStorageUuid)

                    result[pool_name] = heartbeat_success
                    if vm_uuids is not None:
                        runningVms.extend(vm_uuids)
                    if not heartbeat_success:
                        break

        rsp.result = result
        rsp.vmUuids = list(set(runningVms))
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def sanlock_scan_host(self, req):
        def parseLockspaceHostIdPair(s):
            xs = s.split(':', 3)
            return xs[0].split()[-1], int(xs[1])

        def check_host_status(myHostId, lkspc, hostIds):
            hstatus = shell.call("timeout 5 sanlock client host_status -s %s -D" % lkspc)
            parser = sanlock.SanlockHostStatusParser(hstatus)

            result = {}
            if not parser.is_alive(myHostId):
                logger.info("[SANLOCK] current node has no LIVE records for lockspace: %s" % lkspc)
                return result

            for target in cmd.hostIds:
                hostId, psUuid = target.hostId, target.psUuid
                if psUuid not in lkspc: continue

                timed_out = parser.is_timed_out(hostId)
                if timed_out is not None:
                    result[psUuid + '_' + str(hostId)] = not timed_out
            return result

        rsp = SanlockScanRsp()
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        cstatus = shell.call("timeout 5 sanlock client gets -h 1")
        logger.info("[SANLOCK] reports client status:\n" + cstatus)
        pairs = [ parseLockspaceHostIdPair(line) for line in filter(lambda x: x.startswith('s'), cstatus.splitlines()) ]

        if len(pairs) == 0:
            logger.info("[SANLOCK] host id not found")
            return jsonobject.dumps(rsp)

        result = {}
        for lkspc, hid in pairs:
            res = check_host_status(hid, lkspc, cmd.hostIds)
            result.update(res)

        if len(result) == 0:
            return jsonobject.dumps(rsp)

        rsp.result = result
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def sharedblock_check_vmstate(self, req):
        rsp = CheckShareBlockVmStateRsp()
        rsp.result = {}
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        heartbeat_success, vm_uuids = self.sblk_health_checker.check_fencer_heartbeat(
            cmd.hostUuid, cmd.storageCheckerTimeout, cmd.interval, cmd.times, cmd.psUuid, cmd.hostId)
        rsp.result[cmd.psUuid] = heartbeat_success
        rsp.vmUuids = vm_uuids
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def iscsi_check_vmstate(self, req):
        rsp = CheckIscsiVmStateRsp()
        rsp.result = {}
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = CheckIscsiVmStateRsp()

        iscsi_controller = IscsiHeartbeatController(cmd.interval, cmd.times, cmd.primaryStorageUuid, None)
        iscsi_controller.heartbeat_path = login_heartbeat_path(cmd.heartbeatUrl)
        iscsi_controller.host_uuid = cmd.hostUuid
        iscsi_controller.host_id = cmd.hostId
        iscsi_controller.storage_check_timeout = cmd.storageCheckerTimeout
        iscsi_controller.max_attempts = cmd.times
        iscsi_controller.interval = cmd.interval
        iscsi_controller.ps_uuid = cmd.primaryStorageUuid

        heartbeat_success, vm_uuids = iscsi_controller.check_fencer_heartbeat(
            iscsi_controller.host_id, iscsi_controller.storage_check_timeout, iscsi_controller.interval,
            iscsi_controller.max_attempts, cmd.primaryStorageUuid)

        rsp.result = {cmd.primaryStorageUuid: heartbeat_success}
        rsp.vmUuids = list(set(vm_uuids))
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def add_vm_fencer_rule_to_host(self, req):
        rsp = AgentRsp()
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        add_fencer_rule(cmd)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def remove_vm_fencer_rule_from_host(self, req):
        rsp = AgentRsp()
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        remove_fencer_rule(cmd)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def get_vm_fencer_rule(self, req):
        rsp = GetVmFencerRuleRsp()
        rsp.allowRules = global_allow_fencer_rule
        rsp.blockRules = global_block_fencer_rule
        return jsonobject.dumps(rsp)


    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.SCAN_HOST_PATH, self.scan_host)
        http_server.register_async_uri(self.SANLOCK_SCAN_HOST_PATH, self.sanlock_scan_host)
        http_server.register_async_uri(self.SETUP_SELF_FENCER_PATH, self.setup_self_fencer)
        http_server.register_async_uri(self.CEPH_SELF_FENCER, self.setup_ceph_self_fencer)
        http_server.register_async_uri(self.CANCEL_SELF_FENCER_PATH, self.cancel_filesystem_self_fencer)
        http_server.register_async_uri(self.CANCEL_CEPH_SELF_FENCER, self.cancel_ceph_self_fencer)
        http_server.register_async_uri(self.SHAREDBLOCK_SELF_FENCER, self.setup_sharedblock_self_fencer)
        http_server.register_async_uri(self.CANCEL_SHAREDBLOCK_SELF_FENCER, self.cancel_sharedblock_self_fencer)
        http_server.register_async_uri(self.ALIYUN_NAS_SELF_FENCER, self.setup_aliyun_nas_self_fencer)
        http_server.register_async_uri(self.CANCEL_NAS_SELF_FENCER, self.cancel_aliyun_nas_self_fencer)
        http_server.register_async_uri(self.BLOCK_SELF_FENCER, self.setup_block_self_fencer)
        http_server.register_async_uri(self.CANCEL_BLOCK_SELF_FENCER, self.cancel_block_self_fencer)
        http_server.register_async_uri(self.ISCSI_SELF_FENCER, self.setup_iscsi_self_fencer)
        http_server.register_async_uri(self.CANCEL_ISCSI_SELF_FENCER, self.cancel_iscsi_self_fencer)
        http_server.register_async_uri(self.CEPH_HOST_HEARTBEAT_CHECK_PATH, self.ceph_host_heartbeat_check)
        http_server.register_async_uri(self.FILESYSTEM_CHECK_VMSTATE_PATH, self.file_system_check_vmstate)
        http_server.register_async_uri(self.SHAREDBLOCK_CHECK_VMSTATE_PATH, self.sharedblock_check_vmstate)
        http_server.register_async_uri(self.ISCSI_CHECK_VMSTATE_PATH, self.iscsi_check_vmstate)
        http_server.register_async_uri(self.ADD_VM_FENCER_RULE_TO_HOST, self.add_vm_fencer_rule_to_host)
        http_server.register_async_uri(self.REMOVE_VM_FENCER_RULE_FROM_HOST, self.remove_vm_fencer_rule_from_host)
        http_server.register_async_uri(self.GET_VM_FENCER_RULE, self.get_vm_fencer_rule)
        http_server.register_async_uri(self.CBD_SETUP_SELF_FENCER_PATH, self.setup_cbd_self_fencer)


    def stop(self):
        pass

    def configure(self, config):
        self.config = config


    @thread.AsyncThread
    def report_self_fencer_triggered(self, ps_uuids, vm_uuids_string=None):
        url = self.config.get(kvmagent.SEND_COMMAND_URL)
        if not url:
            logger.warn('cannot find SEND_COMMAND_URL, unable to report self fencer triggered on [psList:%s]' % ps_uuids)
            return

        host_uuid = self.config.get(kvmagent.HOST_UUID)
        if not host_uuid:
            logger.warn(
                'cannot find HOST_UUID, unable to report self fencer triggered on [psList:%s]' % ps_uuids)
            return

        def report_to_management_node():
            cmd = ReportSelfFencerCmd()
            cmd.psUuids = ps_uuids
            cmd.hostUuid = host_uuid
            cmd.vmUuidsString = vm_uuids_string
            cmd.fencerFailure = True
            cmd.reason = "primary storage[uuids:%s] on host[uuid:%s] heartbeat fail, self fencer has been triggered" % (ps_uuids, host_uuid)

            logger.debug(
                'host[uuid:%s] primary storage[psList:%s], triggered self fencer, report it to %s' % (
                    host_uuid, ps_uuids, url))
            http.json_dump_post(url, cmd, {'commandpath': '/kvm/reportselffencer'})

        report_to_management_node()


    @thread.AsyncThread
    def report_storage_status(self, ps_uuids, ps_status, reason="", retry_times=1, sleep_time=10):
        url = self.config.get(kvmagent.SEND_COMMAND_URL)
        if not url:
            logger.warn('cannot find SEND_COMMAND_URL, unable to report storages status[psList:%s, status:%s]' % (
                ps_uuids, ps_status))
            return

        host_uuid = self.config.get(kvmagent.HOST_UUID)
        if not host_uuid:
            logger.warn(
                'cannot find HOST_UUID, unable to report storages status[psList:%s, status:%s]' % (ps_uuids, ps_status))
            return

        @linux.retry(times=retry_times, sleep_time=sleep_time)
        def report_to_management_node():
            if any(ps in self.storage_status and self.storage_status[ps] != ps_status for ps in ps_uuids):
                logger.debug("storage%s status changed, skip report %s" % (ps_uuids, ps_status))
                return

            cmd = ReportPsStatusCmd()
            cmd.psUuids = ps_uuids
            cmd.hostUuid = host_uuid
            cmd.psStatus = ps_status
            cmd.reason = reason

            logger.debug(
                'primary storage[psList:%s] has new connection status[%s], report it to %s' % (
                    ps_uuids, ps_status, url))
            http.json_dump_post(url, cmd, {'commandpath': '/kvm/reportstoragestatus'})

        report_to_management_node()


def get_vm_pids_dict():
    virsh_list = shell.call("virsh list --all")
    logger.debug("virsh_list:\n" + virsh_list)

    vm_in_process_uuid_list = shell.call("ps -ef | grep -P -o '(qemu-kvm|qemu-system).*?-name\s+(guest=)?\K.*?,' | sed 's/.$//'")
    logger.debug('vm_in_process_uuid_list:\n' + vm_in_process_uuid_list)

    # vm's qemu process pid
    vm_pids_dict = {}
    for vm_uuid in vm_in_process_uuid_list.splitlines():
        vm_uuid = vm_uuid.strip()
        if not vm_uuid:
            continue

        vm_pid = linux.find_vm_pid_by_uuid(vm_uuid)
        if not vm_pid:
            logger.warn('vm %s pid not found' % vm_uuid)
            continue

        vm_pids_dict[vm_uuid] = vm_pid

    return vm_pids_dict


class FencerResult(Enum):
    SUCCESS = 1
    PARTIAL_SUCCESS = 2
    FAILURE = 3


class FencerPosition(Enum):
    BEFORE = 1
    AFTER = 2


@singleton.singleton
class FencerManager:
    def __init__(self):
        self.fencers = {}
        self.fencer_timestamp = {}
        self.fencer_lock = threading.RLock()

    def register_fencer(self, fencer):
        with self.fencer_lock:
            self.fencers[fencer.name] = fencer
            created_time = time.time()
            exists_time = self.fencer_timestamp.get(fencer.name, None)
            if exists_time and exists_time > created_time:
                logger.debug('exists fencer create time: %d, got create time: %d' % (exists_time, created_time))
                return False

            self.fencer_timestamp[fencer.name] = created_time

    def unregister_fencer(self, name):
        with self.fencer_lock:
            del self.fencers[name]
            del self.fencer_timestamp[name]

    def get_fencer(self, name):
        return self.fencers[name]

    def start_fencer(self, name):
        with self.fencer_lock:
            self.fencers[name].start()

    def stop_fencer(self, name):
        with self.fencer_lock:
            self.fencers[name].stop()

    def get_fencer_status(self, name):
        with self.fencer_lock:
            return self.fencers[name].get_status()


class Fencer(object):
    def __init__(self, name, max_failures, interval, timeout, strategy):
        self.name = name
        self.max_failures = max_failures
        self.interval = interval
        self.timeout = timeout
        self.failure_count = 0

        # keep legacy ha strategy for compatibility
        self.strategy = strategy

        self.stop_flag = False

    def check(self):
        pass

    def get_status(self):
        return "General Fencer Status:\n" \
                "name: %s\n" \
                "max_failures: %s\n" \
                "interval: %s\n" \
                "timeout: %s\n" \
                "strategy: %s\n" \
                "failure_count: %s\n" % (self.name,
                                         self.max_failures,
                                         self.interval,
                                         self.timeout,
                                         self.strategy,
                                         self.failure_count)

    def filter_need_be_fenced_vm(self, vm_uuid):
        pass

    def handle_fencer_failure(self):
        # find all running vm uuid set
        vm_pids_dict = get_vm_pids_dict()

        if len(vm_pids_dict):
            logger.debug("no running vm found")

        # filter vm running on current fencer
        need_be_fenced_uuid_list = filter(lambda uuid: self.filter_need_be_fenced_vm(uuid), vm_pids_dict.keys())

        vm_pids_dict = {uuid: vm_pids_dict[uuid] for uuid in need_be_fenced_uuid_list}

        logger.debug("vm_pids_dict: %s\n" % jsonobject.dumps(vm_pids_dict))
        reason = "because we lost connection to the storage, failed to read the heartbeat file %s times" % max_failures
        kill_vm_use_pid(vm_pids_dict, reason)

    @thread.AsyncThread
    def start(self):
        self.stop_flag = False

        while True:
            # stop run fencer but not expected without api changes
            if self.stop_flag:
                break

            result = self.check()

            # reset failure count to avoid unstable status
            if result == FencerResult.SUCCESS:
                self.failure_count = 0
            elif result == FencerResult.FAILURE:
                self.failure_count += 1

            logger.debug("fencer %s heartbeat of on storage failure(%d/%d)" %
                    (self.name, self.failure_count, self.max_failures))

            # fence the vm if the fencer failed
            if self.is_failed():
                logger.error("Fencer %s failed %s times, execute failure strategy" % (self.name, self.failure_count))
                try:
                    self.handle_fencer_failure()
                except Exception as e:
                    logger.error("Fencer %s failed to handle failure: %s" % (self.name, e))

                self.failure_count = 0

            time.sleep(self.interval)

    def stop(self):
        self.stop_flag = True

    def get_failure_count(self):
        return self.failure_count

    def is_failed(self):
        return self.failure_count >= self.max_failures

fencer_manager = FencerManager()

class VmNetworkFencer(Fencer):
    def __init__(self, name, cmd):
        super(VmNetworkFencer, self).__init__(name, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd.strategy)
        self.falut_nic_count = {}

    def do_check(self):
        vm_use_falut_nic_pids_dict, falut_nic = self.find_vm_use_falut_nic()
        if len(vm_use_falut_nic_pids_dict) == 0:
            return True

        logger.debug("Physical nic[%s] status has been checked %s times and is still down" % (",".join(falut_nic), self.max_failures))
        return False

    def get_ha_fencer_name(self):
        return "hostBusinessNic"

    def find_vm_use_falut_nic(self):
        vm_use_falut_nic_pids_dict = {}
        falut_nic = self.find_falut_business_nic()
        if len(falut_nic) == 0:
            return vm_use_falut_nic_pids_dict, falut_nic
        logger.debug("nics[%s] is down" % ",".join(falut_nic))

        zstack_uuid_pattern = "'[0-9a-f]{8}[0-9a-f]{4}[1-5][0-9a-f]{3}[89ab][0-9a-f]{3}[0-9a-f]{12}'"
        vm_in_process_uuid_list = shell.call("virsh list | egrep -o " + zstack_uuid_pattern + " | sort | uniq")
        for vm_uuid in vm_in_process_uuid_list.splitlines():
            if is_block_fencer(self.get_ha_fencer_name(), vm_uuid):
                continue

            bridge_nics = shell.call("virsh domiflist %s | grep bridge | awk '{print $3}'" % vm_uuid)
            for bridge_nic in bridge_nics.splitlines():
                if len(bridge_nic) == 0:
                    continue

                if '_' in bridge_nic:
                    bridge_nic = bridge_nic.split('_')[1]

                if '.' in bridge_nic:
                    bridge_nic = bridge_nic.split('.')[0]

                if len(bridge_nic) == 0:
                    continue

                if bridge_nic.strip() in falut_nic:
                    vm_pid = linux.find_vm_pid_by_uuid(vm_uuid)
                    if not vm_pid:
                        logger.warn('vm %s pid not found' % vm_uuid)
                        continue
                    vm_use_falut_nic_pids_dict[vm_uuid] = vm_pid
        logger.debug("vm_use_falut_nic_pids_dict: %s" % vm_use_falut_nic_pids_dict)
        return vm_use_falut_nic_pids_dict, falut_nic

    def find_falut_business_nic(self):
        nics = []
        nics.extend(ipUtils.get_host_physicl_nics())
        nics.extend(self.get_nomal_bond_nic())
        for new_nic in nics:
            if new_nic not in self.falut_nic_count:
                self.falut_nic_count[new_nic] = 0
            try:
                ip = iproute.query_links(new_nic)
                if ip[0].state == 'DOWN':
                    self.falut_nic_count[new_nic] += 1
                else:
                    self.falut_nic_count[new_nic] = 0
            except Exception as e:
                logger.warn('iproute query_links is except, %s' % e)
                continue

        return [nic for nic, count in self.falut_nic_count.items() if count > self.max_failures]

    def get_nomal_bond_nic(self):
        bond_path = "/proc/net/bonding/"
        if os.path.exists(bond_path):
            return os.listdir(bond_path)
        return []


class StorageFencer(Fencer):
    def __init__(self, name, max_failures, interval, timeout, strategy):
        super(StorageFencer, self).__init__(name, max_failures, interval, timeout, strategy)

    def retry_to_recover_storage(self):
        """
        retry to recover storage connection
        """
        pass

    def do_check(self):
        """
        how to check connection to storage
        """
        pass

    def check(self):
        try:
            if self.do_check():
                return FencerResult.SUCCESS

            return FencerResult.FAILURE
        except Exception as e:
            logger.warn("Fencer %s check failed: %s" % (self.name, e))
            return FencerResult.FAILURE

    def recover(self):
        return self.retry_to_recover_storage()

    def get_storage_heartbeat_content(self, unique_str_in_storage_path):
        vm_uuids = find_ps_running_vm(unique_str_in_storage_path)
        dict = {"heartbeat_time": time.time(),
                    "vm_uuids": "" if len(vm_uuids) == 0 else ','.join(str(x) for x in vm_uuids)}
        return json.dumps(dict)

    @staticmethod
    def read_heartbeat_file(heartbeat_file_path):
        try:
            with open(heartbeat_file_path, 'r') as f:
                return json.loads(f.read())
        except Exception as e:
            logger.warn("read heartbeat file %s failed: %s" % (heartbeat_file_path, e))
            return None


class FileSystemMountPoint:
    def __init__(self, url, mount_path, mounted_by_zstack, options):
        """
        :param url: file system url
        :param mount_path: file system mount path
        :param mounted_by_zstack: whether the file system is mounted by zstack
        :param options: mount options
        """

        self.url = url
        self.mount_path = mount_path
        self.mounted_by_zstack = mounted_by_zstack
        self.options = options


class FileSystemFencer(StorageFencer):
    @staticmethod
    def format_heartbeat_path(storage_mount_path, host_uuid):
        return os.path.join(os.path.join(storage_mount_path, 'heartbeat'), 'heartbeat-file-%s.hb' % host_uuid)

    def __init__(self, ps_uuid, max_failures, interval, timeout, strategy, host_uuid, mount_point):
        """
        :param ps_uuid: primary storage uuid
        :param max_failures: max failures before fencer
        :param interval: interval to check the storage
        :param timeout: timeout to check the storage
        :param strategy: ha strategy
        :param host_uuid: host uuid
        :param mount_point: file system mount point
        """

        super(FileSystemFencer, self).__init__(ps_uuid, max_failures, interval, timeout, strategy)
        self.mount_point = mount_point
        self.ps_uuid = ps_uuid

        self.heartbeat_file_path = os.path.join(os.path.join(self.mount_point.mount_path, 'heartbeat'),
                                                 'heartbeat-file-kvm-host-%s.hb' % host_uuid)

    def do_check(self):
        touch = shell.ShellCmd('timeout %s touch %s' 
                                % (self.timeout, self.heartbeat_file_path))
        touch(False)
        if touch.return_code != 0:
            logger.warn('unable to touch %s, %s %s'
                          % (self.heartbeat_file_path, touch.stderr, touch.stdout))
            return False

        content = self.get_storage_heartbeat_content(self.ps_uuid)
        with open(self.heartbeat_file_path, 'w') as f:
            f.write(json.dumps(content))
        return True

    def retry_to_recover_storage(self):
        if not self.mount_point.mounted_by_zstack:
            logger.debug("skip to remount the file system[%s] because it is not mounted by zstack" % self.mount_point.mount_path)
            return False

        logger.debug("remount the file system[%s] because it is mounted by zstack" % self.mount_point.mount_path)
        return True

    def get_status(self):
        return "FileSystemFencer Status:\n" \
                "ps_uuid: %s\n" \
                "max_failures: %s\n" \
                "interval: %s\n" \
                "timeout: %s\n" \
                "strategy: %s\n" \
                "mount_point: %s\n" % (self.ps_uuid,
                                        self.max_failures,
                                        self.interval,
                                        self.timeout,
                                        self.strategy,
                                        self.mount_point.mount_path)



class SanlockVolumeGroupFencer(StorageFencer):
    def __init__(self, cmd):
        super(SanlockVolumeGroupFencer, self).__init__(cmd.vgUuid, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd.strategy)
        self.cmd = cmd

    def do_check(self):
        # Note: sanlock use function lru_cache to accelerate fencers execution performance
        # when large number of volume groups exist
        lockspaces = sanlock.get_lockspaces()
        p = sanlock.get_sanlock_client_status()
        vg = self.cmd.vgUuid
        r = p.get_lockspace_record(vg)
        if not r:
            failure = "lockspace for vg %s not found" % vg
            logger.warn(failure)
            return False

        if r.is_adding:
            logger.warn("lockspace for vg %s is adding, skip run fencer" % vg)
            return True

        if r.get_lockspace() not in lockspaces:
            failure = "can not find lockspace of %s" % vg
            logger.warn(failure)
            return False

        if r.get_renewal_last_result() == 1:
            return True

        # if attemp time is over 100 seconds, we consider it as a failure
        # because sanlock will try to renew the lockspace every 10 seconds
        if math.fabs(r.get_renewal_last_attempt() - r.get_renewal_last_success()) > 100:
            failure = "sanlock last renewal failed with %s and last attempt is %s, last success is %s, which is over 100 seconds" % \
                    (r.get_renewal_last_result(), r.get_renewal_last_attempt(), r.get_renewal_last_success())
            logger.warn(failure)
            return False

        return True

    def retry_to_recover_storage(self):
        lvm.remove_partial_lv_dm(self.cmd.vgUuid)

        if lvm.check_vg_status(self.cmd.vgUuid, self.cmd.storageCheckerTimeout, True)[0]:
            return

        lvm.drop_vg_lock(self.cmd.vgUuid)
        lvm.remove_device_map_for_vg(self.cmd.vgUuid)

    # TODO: fix performance issue by support find vm from different source
    def filter_need_be_fenced_vm(self, vm_uuid):
        # we will check one io to determine volumes on pv should be kill
        invalid_pv_uuids = lvm.get_invalid_pv_uuids(self.vg_uuid, self.cmd.checkIo)
        logger.debug("got invalid pv uuids: %s" % invalid_pv_uuids)
        vms = lvm.get_running_vm_root_volume_on_pv(self.vg_uuid, invalid_pv_uuids, True)
        vms = [vm for vm in vms if vm['vm_uuid'] == vm_uuid]
        return len(vms) > 0


class SharedBlockStorageFencer(StorageFencer):
    def __init__(self, cmd):
        super(SharedBlockStorageFencer, self).__init__(cmd.vgUuid, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd)
        self.vg_name = cmd.vgUuid
        self.cmd = cmd

    def do_check(self):
        success, original_conf, updated_conf = self.update_sharedblock_agent_param([self.cmd.vgUuid])

        if not success:
            logger.warn('failed to update sblk fencer heartbeat param on the shared block storage[%s],' \
                        ' param_path: %s'
                         % (self.vg_name, SHAREBLOCK_VM_HA_PARAMS_PATH))
            return False

        logger.debug("update sblk fencer heartbeat param from: \n" \
                     "%s \n" \
                     "to: \n" \
                     "%s" % (original_conf, updated_conf))
        return True

    def get_status(self):
        return "SharedBlockStorageFencer Status:\n" \
                "vg_uuid: %s\n" \
                "max_failures: %s\n" \
                "interval: %s\n" \
                "timeout: %s\n" \
                "strategy: %s\n" % (self.vg_name,
                                    self.max_failures,
                                    self.interval,
                                    self.timeout,
                                    self.strategy)

    def update_sharedblock_agent_param(self, vg_uuids):
        if len(vg_uuids) == 0:
            return True, None, None

        original_conf = None
        updated_conf = None
        # TODO fix this
        # need fie lock
        # fix empty file config, should update it instead of return
        updated_conf = jsonobject.dumps(self.cmd)
        with open(SHAREBLOCK_VM_HA_PARAMS_PATH, 'w+') as f:
            cmd = f.read().strip()
            original_conf = cmd
            f.write(updated_conf)

        return True, original_conf, updated_conf


class IscsiNodeStatus(object):
    def __init__(self, vm_uuids):
        self.vm_uuids = vm_uuids
        self.heartbeat_time = time.time()


class IscsiFencer(StorageFencer):
    def __init__(self, cmd, heartbeat_path, covering_paths):
        super(IscsiFencer, self).__init__(cmd.uuid, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd)
        self.coveringPaths = covering_paths
        self.heartbeat_path = heartbeat_path
        self.host_id = cmd.hostId
        self.heartbeat_required_space = 1024 * 1024
        self.cmd = cmd

    @bash.in_bash
    def _fill_heartbeat_file(self, vm_uuids):
        # type -> (list[str])
        offset = self.host_id * self.heartbeat_required_space
        tmp_file = linux.write_to_temp_file(jsonobject.dumps(IscsiNodeStatus(vm_uuids)) + EOF)
        cmd = "dd if=%s of=%s bs=%s seek=%s oflag=direct" % \
              (tmp_file, self.heartbeat_path, offset, self.host_id)

        r, o, e = bash.bash_roe("timeout 20 " + cmd)
        linux.rm_file_force(tmp_file)
        return r == 0

    def _heartbeat_io_check(self):
        heartbeat_check = shell.ShellCmd('sg_inq %s' % self.heartbeat_path)
        heartbeat_check(False)
        if heartbeat_check.return_code != 0:
            logger.warn('failed to check heartbeat[%s], %s' % (self.heartbeat_path, heartbeat_check.stderr))
            return False

        return True

    def do_check(self):
        running_vm_uuids = set()
        for covering_path in self.coveringPaths:
            running_vm_uuids.update(find_ps_running_vm(covering_path))

        if self._heartbeat_io_check() and self._fill_heartbeat_file(list(running_vm_uuids)):
            return True

        return False


class CephFencer(StorageFencer):
    def __init__(self, fencer_name, pool_name,  cmd):
        super(CephFencer, self).__init__(fencer_name, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd.strategy)
        self.pool_name = pool_name
        self.cmd = cmd

        # used as content of the heartbeat object
        self.heartbeat_counter = 0
        self.heartbeat_object_name = ceph.get_heartbeat_object_name(cmd.uuid, cmd.hostUuid)
        self.ioctx = ceph.get_ioctx(cmd.primaryStorageUuid, cmd.manufacturer, pool_name)

        self.fencer_name = "ceph-fencer-%s" % pool_name

    def get_ha_fencer_name(self):
        return self.fencer_name

    def __exit__(self):
        if self.ioctx:
            # TODO: close ioctx
            pass

        return

    def do_check(self):
        try:
            return self.write_fencer_heartbeat()
        except Exception as e:
            logger.warn('failed to check the ceph storage heartbeat, %s' % e)
            return False

    def write_fencer_heartbeat(self):
        """
        Increase the heartbeat counter and write the heartbeat content to the ceph storage.

        :return: True if the operation is successful, False otherwise.
        """

        if self.heartbeat_counter > 100000:
            self.heartbeat_counter = 0
        else:
            self.heartbeat_counter += 1

        vm_in_ps_uuid_list = find_ps_running_vm(self.pool_name)
        content = {"heartbeat_count": str(self.heartbeat_counter), "vm_uuids": None if len(vm_in_ps_uuid_list) == 0 else ','.join(str(x) for x in vm_in_ps_uuid_list)}
        completion = self.ioctx.aio_write_full(self.heartbeat_object_name, str(content))

        waited_time = 0
        while not completion.is_complete():
            time.sleep(1)
            waited_time += 1
            if waited_time == self.timeout:
                logger.debug("write operation to %s not finished util fencer's timeout[%d], report update failure" % (self.heartbeat_object_name, self.timeout))
                return False, waited_time

        # del completion to avoid threading deadlock ZSTAC-57892
        # refer: https://github.com/python/cpython/issues/88588
        del completion
        return True, waited_time


class BlockStorageFencer(StorageFencer):
    def __init__(self, cmd, heartbeat_wwn_path):
        super(BlockStorageFencer, self).__init__(cmd.vgUuid, cmd.maxAttempts, cmd.interval, cmd.storageCheckerTimeout, cmd)
        self.heartbeat_wwn_path = heartbeat_wwn_path
        self.cmd = cmd

    def do_check(self):
        heartbeat_check = shell.ShellCmd('sg_inq %s' % self.heartbeat_wwn_path)
        heartbeat_check(False)
        if heartbeat_check.return_code != 0:
            return False

        return True

    # TODO: need fix this
    def try_recover_storage(self):
        bash.bash_roe("timeout 120 /usr/bin/rescan-scsi-bus.sh -r >/dev/null")
        bash.bash_roe("timeout 120 /usr/bin/rescan-scsi-bus.sh -u >/dev/null")
