import os

from zstacklib.utils.storageDriver import StorageDriver


class LocalStorageDriver(StorageDriver):
    def write_metadata(self, metadata_path, imf):
        if not os.path.exists(os.path.dirname(metadata_path)):
            os.makedirs(os.path.dirname(metadata_path))

        try:
            with open(metadata_path, 'wb') as f:
                f.write(imf)
            print "[LocalStorage] Manifest written to", metadata_path
            return True
        except IOError as e:
            raise IOError("[LocalStorage] Failed to write to file %s: %s" % (metadata_path, str(e)))

    def read_metadata(self, metadata_path):
        if not os.path.exists(metadata_path):
            raise IOError("File not found: %s" % metadata_path)
        with open(metadata_path, 'r') as f:
            return f.read()
