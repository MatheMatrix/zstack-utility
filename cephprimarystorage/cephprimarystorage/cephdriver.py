import zstacklib.utils.sizeunit as sizeunit

from zstacklib.utils import ceph
import zstacklib.utils.jsonobject as jsonobject
from zstacklib.utils.bash import *
import rbd

logger = log.get_logger(__name__)


class CephDriver(object):
    def __init__(self, *args, **kwargs):
        super(CephDriver, self).__init__()

    def _wrap_shareable_cmd(self, cmd, cmd_string):
        if cmd.shareable:
            return cmd_string + " --image-shared"
        return cmd_string

    def _normalize_install_path(self, path):
        return path.replace('ceph://', '')

    def _get_file_size(self, path):
        o = shell.call('rbd --format json info %s' % path)
        o = jsonobject.loads(o)
        return long(o.size_)

    def clone_volume(self, cmd, rsp):
        src_path = self._normalize_install_path(cmd.srcPath)
        dst_path = self._normalize_install_path(cmd.dstPath)

        shell.call('rbd clone %s %s' % (src_path, dst_path))
        rsp.installPath = dst_path
        return rsp

    def create_volume(self, cmd, rsp, agent=None):
        path = self._normalize_install_path(cmd.installPath)
        rsp.size = cmd.size

        if cmd.skipIfExisting and shell.run("rbd info %s" % path) == 0:
            return rsp

        multiple_of_MB = cmd.size % sizeunit.m == 0
        if cmd.systemTags and ceph.is_qcow2_format(cmd.systemTags):
            vol_path = "rbd:%s" % path
            linux.qcow2_create(vol_path, cmd.size, False)
        elif multiple_of_MB:
            call_string = 'rbd create --size %s --image-format 2 %s' % (sizeunit.Byte.toMegaByte(cmd.size), path)
            call_string = self._wrap_shareable_cmd(cmd, call_string)
            shell.call(call_string)
        elif ceph.rbd_create_support_byte():
            call_string = 'rbd create --size %dB --image-format 2 %s' % (cmd.size, path)
            call_string = self._wrap_shareable_cmd(cmd, call_string)
            shell.call(call_string)
        else:
            pool, image = path.split('/')
            ioctx = agent.get_ioctx(pool)
            rbd_inst = rbd.RBD()
            rbd_inst.create(ioctx, image, cmd.size)

        return rsp

    @linux.retry(times=30, sleep_time=5)
    def do_deletion(self, cmd, path, skip_if_not_exist=False, defer=False):
        if shell.run('rbd info %s' % path) != 0 and skip_if_not_exist:
            return

        if defer and ceph.support_defer_deleting():
            if cmd.expirationTime is not None and cmd.expirationTime > 0:
                shell.call("rbd trash mv %s %s" % (path, ceph.get_defer_deleting_options(cmd)))
                return

        shell.call('rbd rm %s' % path)

    def create_snapshot(self, cmd, rsp):
        spath = self._normalize_install_path(cmd.snapshotPath)

        o = shell.ShellCmd('rbd snap create %s' % spath)
        o(False)
        if o.return_code != 0:
            shell.run("rbd snap rm %s" % spath)
            o.raise_error()

        rsp.size = self._get_file_size(spath)
        return rsp

    def delete_snapshot(self, cmd):
        spath = self._normalize_install_path(cmd.snapshotPath)
        shell.call('rbd snap rm %s' % spath)

    def validate_token(self, cmd):
        pass

    def rollback_snapshot(self, cmd):
        spath = self._normalize_install_path(cmd.snapshotPath)
        shell.call('rbd snap rollback %s' % spath)
