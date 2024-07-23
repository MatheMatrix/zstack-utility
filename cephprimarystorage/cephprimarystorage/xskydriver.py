import cephdriver
import zstacklib.utils.jsonobject as jsonobject
from zstacklib.utils import bash, sizeunit
from zstacklib.utils.bash import in_bash

logger = log.get_logger(__name__)


class XskyDriver(cephdriver.CephDriver):
    def __init__(self, *args, **kwargs):
        super(XskyDriver, self).__init__()

    @in_bash
    def get_file_actual_size(self, path):
        r, jstr = bash.bash_ro("rbd du %s --format json" % path)
        total_size = None
        result = jsonobject.loads(jstr)
        if result.images is not None:
            for item in result.images:
                total_size += int(item.used_size)
            return sizeunit.get_size(total_size)

        return self.get_file_actual_size_by_rbd_du(path)

    def volume_size_with_internal_snapshot(self):
        return True
