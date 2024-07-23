import cephdriver
import zstacklib.utils.jsonobject as jsonobject
from zstacklib.utils import ceph, bash, shell

logger = log.get_logger(__name__)


class ZstoneDriver(cephdriver.CephDriver):
    def __init__(self, *args, **kwargs):
        super(ZstoneDriver, self).__init__()

    def get_file_actual_size(self, path):
        def get_volume_actual_size():
            name = path.split('/')[-1]
            used_size = None
            result = jsonobject.loads(jstr)
            if result.images is not None:
                for image in result.images:
                    if image.snapshot is None and image.name == name:
                        used_size = int(image.used_size)
                        break
            return used_size

        def get_snapshot_actual_size():
            snapshot = path.split('@')[-1]
            used_size = None
            result = jsonobject.loads(jstr)
            if result.images is not None:
                for image in result.images:
                    if image.snapshot == snapshot:
                        used_size = int(image.used_size)
                        break
            return used_size

        r, jstr = bash.bash_ro("rbd du %s --format json" % path)
        if r == 0 and bool(jstr):
            return get_snapshot_actual_size() if ceph.is_snapshot(path) else get_volume_actual_size()

        return self.get_file_actual_size_by_rbd_du(path)

    def volume_size_with_internal_snapshot(self):
        return False
