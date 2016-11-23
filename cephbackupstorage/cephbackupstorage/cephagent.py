__author__ = 'frank'

import zstacklib.utils.daemon as daemon
import zstacklib.utils.http as http
import zstacklib.utils.log as log
import zstacklib.utils.shell as shell
import zstacklib.utils.iptables as iptables
import zstacklib.utils.jsonobject as jsonobject
import zstacklib.utils.lock as lock
import zstacklib.utils.linux as linux
import zstacklib.utils.sizeunit as sizeunit
from zstacklib.utils import plugin
from zstacklib.utils.rollback import rollback, rollbackable
from zstacklib.utils.bash import *

import os
import os.path
import functools
import traceback
import pprint
import threading

logger = log.get_logger(__name__)

class AgentResponse(object):
    def __init__(self, success=True, error=None):
        self.success = success
        self.error = error if error else ''
        self.totalCapacity = None
        self.availableCapacity = None

class InitRsp(AgentResponse):
    def __init__(self):
        super(InitRsp, self).__init__()
        self.fsid = None

class DownloadRsp(AgentResponse):
    def __init__(self):
        super(DownloadRsp, self).__init__()
        self.size = None
        self.actualSize = None
        self.inject = None

class GetImageSizeRsp(AgentResponse):
    def __init__(self):
        super(GetImageSizeRsp, self).__init__()
        self.size = None
        self.actualSize = None

class PingRsp(AgentResponse):
    def __init__(self):
        super(PingRsp, self).__init__()
        self.failure = None

class GetFactsRsp(AgentResponse):
    def __init__(self):
        super(GetFactsRsp, self).__init__()
        self.fsid = None
        self.monAddr = None

def replyerror(func):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            content = traceback.format_exc()
            err = '%s\n%s\nargs:%s' % (str(e), content, pprint.pformat([args, kwargs]))
            rsp = AgentResponse()
            rsp.success = False
            rsp.error = str(e)
            logger.warn(err)
            return jsonobject.dumps(rsp)
    return wrap

class CephAgent(object):
    INIT_PATH = "/ceph/backupstorage/init"
    DOWNLOAD_IMAGE_PATH = "/ceph/backupstorage/image/download"
    DELETE_IMAGE_PATH = "/ceph/backupstorage/image/delete"
    PING_PATH = "/ceph/backupstorage/ping"
    ECHO_PATH = "/ceph/backupstorage/echo"
    GET_IMAGE_SIZE_PATH = "/ceph/backupstorage/image/getsize"
    GET_FACTS = "/ceph/backupstorage/facts"

    http_server = http.HttpServer(port=7761)
    http_server.logfile_path = log.get_logfile_path()

    def __init__(self):
        self.http_server.register_async_uri(self.INIT_PATH, self.init)
        self.http_server.register_async_uri(self.DOWNLOAD_IMAGE_PATH, self.download)
        self.http_server.register_async_uri(self.DELETE_IMAGE_PATH, self.delete)
        self.http_server.register_async_uri(self.PING_PATH, self.ping)
        self.http_server.register_async_uri(self.GET_IMAGE_SIZE_PATH, self.get_image_size)
        self.http_server.register_async_uri(self.GET_FACTS, self.get_facts)
        self.http_server.register_sync_uri(self.ECHO_PATH, self.echo)

    def _set_capacity_to_response(self, rsp):
        o = shell.call('ceph df -f json')
        df = jsonobject.loads(o)

        if df.stats.total_bytes__ is not None :
            total = long(df.stats.total_bytes_)
        elif df.stats.total_space__ is not None:
            total = long(df.stats.total_space__) * 1024
        else:
            raise Exception('unknown ceph df output: %s' % o)

        if df.stats.total_avail_bytes__ is not None:
            avail = long(df.stats.total_avail_bytes_)
        elif df.stats.total_avail__ is not None:
            avail = long(df.stats.total_avail_) * 1024
        else:
            raise Exception('unknown ceph df output: %s' % o)

        rsp.totalCapacity = total
        rsp.availableCapacity = avail

    @replyerror
    def echo(self, req):
        logger.debug('get echoed')
        return ''

    def _normalize_install_path(self, path):
        return path.lstrip('ceph:').lstrip('//')

    def _get_file_size(self, path):
        o = shell.call('rbd --format json info %s' % path)
        o = jsonobject.loads(o)
        return long(o.size_)

    @replyerror
    def get_image_size(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = GetImageSizeRsp()
        path = self._normalize_install_path(cmd.installPath)
        rsp.size = self._get_file_size(path)
        return jsonobject.dumps(rsp)

    @replyerror
    @in_bash
    def get_facts(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        o = bash_o('ceph mon_status')
        mon_status = jsonobject.loads(o)
        fsid = mon_status.monmap.fsid_

        rsp = GetFactsRsp()

        facts = bash_o('ceph -s -f json')
        mon_facts = jsonobject.loads(facts)
        for mon in mon_facts.monmap.mons:
            ADDR = mon.addr.split(':')[0]
            if bash_r('ip route | grep -w {{ADDR}} > /dev/null') == 0:
                rsp.monAddr = ADDR
                break

        if not rsp.monAddr:
            raise Exception('cannot find mon address of the mon server[%s]' % cmd.monUuid)

        rsp.fsid = fsid
        return jsonobject.dumps(rsp)

    @replyerror
    def init(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        o = shell.call('ceph mon_status')
        mon_status = jsonobject.loads(o)
        fsid = mon_status.monmap.fsid_

        existing_pools = shell.call('ceph osd lspools')
        for pool in cmd.pools:
            if pool.predefined and pool.name not in existing_pools:
                raise Exception('cannot find pool[%s] in the ceph cluster, you must create it manually' % pool.name)
            elif pool.name not in existing_pools:
                shell.call('ceph osd pool create %s 100' % pool.name)

        rsp = InitRsp()
        rsp.fsid = fsid
        self._set_capacity_to_response(rsp)

        return jsonobject.dumps(rsp)

    def _parse_install_path(self, path):
        return path.lstrip('ceph:').lstrip('//').split('/')

    def _inject_qemu_ga(self, install_path):
        cmd = "bash /usr/local/zstack/imagestore/qemu-ga/auto-qemu-ga.sh %s" % install_path
        logger.debug("inject qemu-ga, try to exec: %s" % cmd)
        try:
            bash_o(cmd, True)
        except BashError as e:
            logger.warn("inject failed due to:")
            logger.warn(e)

    @replyerror
    @rollback
    def download(self, req):
        def fail_if_has_backing_file(fpath):
            if linux.qcow2_get_backing_file(fpath):
                raise Exception('image has backing file')

        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        pool, image_name = self._parse_install_path(cmd.installPath)
        tmp_qemu_name = 'tmp-%s_qemu' % image_name
        tmp_image_name = 'tmp-%s' % image_name

        if cmd.url.startswith('http://') or cmd.url.startswith('https://'):
            shell.call('set -o pipefail; wget --no-check-certificate -q %s -O %s ' % (cmd.url, tmp_qemu_name))
            fail_if_has_backing_file(tmp_qemu_name)
            if cmd.inject:
                self._inject_qemu_ga(tmp_qemu_name)
            shell.call('rbd import --image-format 2 %s %s/%s' % (tmp_qemu_name, pool, tmp_image_name))
            actual_size = linux.get_file_size_by_http_head(cmd.url)
        elif cmd.url.startswith('file://'):
            src_path = cmd.url.lstrip('file:')
            src_path = os.path.normpath(src_path)
            if not os.path.isfile(src_path):
                raise Exception('cannot find the file[%s]' % src_path)
            fail_if_has_backing_file(src_path)
            shell.call('cp -f %s %s' % (src_path, tmp_qemu_name))
            if cmd.inject:
                self._inject_qemu_ga(tmp_qemu_name)
            shell.call("rbd import --image-format 2 %s %s/%s" % (tmp_qemu_name, pool, tmp_image_name))
            actual_size = os.path.getsize(src_path)
        else:
            raise Exception('unknown url[%s]' % cmd.url)
        shell.call('rm -f %s' % tmp_qemu_name)

        @rollbackable
        def _1():
            shell.call('rbd rm %s/%s' % (pool, tmp_image_name))
        _1()

        file_format = shell.call("set -o pipefail; qemu-img info rbd:%s/%s | grep 'file format' | cut -d ':' -f 2" % (pool, tmp_image_name))
        file_format = file_format.strip()
        if file_format not in ['qcow2', 'raw']:
            raise Exception('unknown image format: %s' % file_format)

        if file_format == 'qcow2':
            conf_path = None
            try:
                with open('/etc/ceph/ceph.conf', 'r') as fd:
                    conf = fd.read()
                    conf = '%s\n%s\n' % (conf, 'rbd default format = 2')
                    conf_path = linux.write_to_temp_file(conf)

                shell.call('qemu-img convert -f qcow2 -O rbd rbd:%s/%s rbd:%s/%s:conf=%s' % (pool, tmp_image_name, pool, image_name, conf_path))
                shell.call('rbd rm %s/%s' % (pool, tmp_image_name))
            finally:
                if conf_path:
                    os.remove(conf_path)
        else:
            shell.call('rbd mv %s/%s %s/%s' % (pool, tmp_image_name, pool, image_name))

        o = shell.call('rbd --format json info %s/%s' % (pool, image_name))
        image_stats = jsonobject.loads(o)

        rsp = DownloadRsp()
        rsp.size = long(image_stats.size_)
        rsp.actualSize = actual_size
        rsp.format = file_format
        self._set_capacity_to_response(rsp)
        return jsonobject.dumps(rsp)

    @replyerror
    def ping(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = PingRsp()

        facts = bash_o('ceph -s -f json')
        mon_facts = jsonobject.loads(facts)
        found = False
        for mon in mon_facts.monmap.mons:
            if cmd.monAddr in mon.addr:
                found = True
                break

        if not found:
            rsp.success = False
            rsp.failure = "MonAddrChanged"
            rsp.error = 'The mon addr is changed on the mon server[uuid:%s], not %s anymore.' \
                        'Reconnect the ceph primary storage' \
                        ' may solve this issue' % (cmd.monUuid, cmd.monAddr)
            return jsonobject.dumps(rsp)


        create_img = shell.ShellCmd('rbd create %s --image-format 2 --size 1' % cmd.testImagePath)
        create_img(False)
        if create_img.return_code != 0:
            rsp.success = False
            rsp.failure = 'UnableToCreateFile'
            rsp.error = "%s %s" % (create_img.stderr, create_img.stdout)
        else:
            rm_img = shell.ShellCmd('rbd rm %s' % cmd.testImagePath)
            rm_img(False)

        return jsonobject.dumps(rsp)

    @replyerror
    def delete(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        pool, image_name = self._parse_install_path(cmd.installPath)
        shell.call('rbd rm %s/%s' % (pool, image_name))

        rsp = AgentResponse()
        self._set_capacity_to_response(rsp)
        return jsonobject.dumps(rsp)


class CephDaemon(daemon.Daemon):
    def __init__(self, pidfile):
        super(CephDaemon, self).__init__(pidfile)

    def run(self):
        self.agent = CephAgent()
        self.agent.http_server.start()


