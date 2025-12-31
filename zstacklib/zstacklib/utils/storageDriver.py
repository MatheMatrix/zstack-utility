from abc import ABCMeta, abstractmethod

# Magic number: 'ZIMF' in hex
META_MAGIC = '\x5a\x49\x4d\x46'

# Maximum header length: 4MB
MAX_HDR_LENGTH = 4 * 1024 * 1024

class BlkMetaHeader(object):
    """
    Metadata header structure
    Similar to BlkMetaHeader in blkmeta.go
    """

    def __init__(self, magic, length):
        self.magic = magic
        self.length = length


class BlkMeta(object):
    """
    Metadata structure
    Similar to BlkMeta in blkmeta.go
    """

    def __init__(self, header, data):
        self.header = header
        self.data = data


class StorageDriver(object):
    """
    Abstract base class for storage drivers
    Similar to StorageDriver interface in driver.go
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def write_metadata(self, metadata_path, imf):
        raise NotImplementedError("Subclasses must implement write_metadata")

    @abstractmethod
    def read_metadata(self, metadata_path):
        raise NotImplementedError("Subclasses must implement read_metadata")

