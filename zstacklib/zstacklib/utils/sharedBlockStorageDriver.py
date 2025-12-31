import os
import struct
import time

from kvmagent.plugins.shared_block_plugin import VM_METADATA_TAG
from zstacklib.utils import lvm
from zstacklib.utils.storageDriver import StorageDriver, BlkMetaHeader, BlkMeta, META_MAGIC


class SharedBlockStorageDriver(StorageDriver):
    def blk_write_open(self, metadata_path):
        try:
            return os.open(metadata_path, os.O_WRONLY)
        except OSError as e:
            raise IOError("Failed to open block device %s: %s" % (metadata_path, str(e)))

    def write_meta(self, metadata_path, meta):
        header_bytes = struct.pack('4sI', meta.header.magic, meta.header.length)

        try:
            fd = self.blk_write_open(metadata_path)
            try:
                os.write(fd, header_bytes)
                if meta.header.length > 0:
                    os.write(fd, meta.data)
            finally:
                os.close(fd)
        except IOError as e:
            raise IOError("Failed to write metadata to %s: %s" % (metadata_path, str(e)))

    def write_metadata(self, metadata_path, imf):
        lv_exists = lvm.lv_exists(metadata_path)
        lv_size = 1024 * 1024
        if not lv_exists:
            lvm.create_lv_from_absolute_path(metadata_path, lv_size,
                                             "%s::%s::%s" % (VM_METADATA_TAG, "hostUuid", time.time()), exact_size=True)

        with lvm.RecursiveOperateLv(metadata_path, shared=False):
            # Create metadata header
            header = BlkMetaHeader(magic=META_MAGIC, length=len(imf))

            # Create metadata
            meta = BlkMeta(header=header, data=imf)

            # Write to the logical volume
            self.write_meta(metadata_path, meta)

    def read_metadata(self, metadata_path):
        return True
