import zstacklib.utils.sizeunit as sizeunit

from zstacklib.utils import ceph, bash
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

        if ceph.is_xsky():
            # do NOT round to MB
            call_string = 'rbd create --size %dB --image-format 2 %s' % (cmd.size, path)
            call_string = self._wrap_shareable_cmd(cmd, call_string)
            shell.call(call_string)
        else:
            pool, image = path.split('/')
            ioctx = agent.get_ioctx(pool)
            rbd_inst = rbd.RBD()
            try:
                rbd_inst.create(ioctx, image, cmd.size)
            except Exception as e:
                logger.debug("caught an exception[%s] when creating volume, try again now" % str(e))
                size_M = sizeunit.Byte.toMegaByte(cmd.size) + 1
                call_string = 'rbd create --size %s --image-format 2 %s' % (size_M, path)
                call_string = self._wrap_shareable_cmd(cmd, call_string)
                shell.call(call_string)
                rsp.size = sizeunit.MegaByte.toByte(size_M)

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

    @in_bash
    def get_file_actual_size(self, path):
        fast_diff_enabled = shell.run(
            "rbd --format json info %s | grep fast-diff | grep -qv 'fast diff invalid'" % path) == 0

        # if no fast-diff supported and not xsky ceph skip actual size check
        if not fast_diff_enabled and not ceph.is_xsky():
            return None

        r, jstr = bash.bash_ro("rbd du %s --format json" % path)
        total_size = 0
        result = jsonobject.loads(jstr)
        if result.images is not None:
            for item in result.images:
                total_size += int(item.used_size)
            return sizeunit.get_size(total_size)

        return self.get_file_actual_size_by_rbd_du(path)

    @in_bash
    def get_file_actual_size_by_rbd_du(self, path):
        r, size = bash.bash_ro(
            "rbd du %s | awk 'END {if(NF==3) {print $3} else {print $4,$5} }' | sed s/[[:space:]]//g" % path,
            pipe_fail=True)
        if r != 0:
            return None

        size = size.strip()
        if not size:
            return None

        return sizeunit.get_size(size)

    def volume_size_with_internal_snapshot(self):
        return True
