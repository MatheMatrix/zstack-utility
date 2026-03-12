class VmMetadataScanEntry(object):
    __slots__ = (
        'vmUuid', 'vmName', 'vmCategory', 'architecture',
        'schemaVersion', 'metadataPath', 'sizeBytes', 'lastUpdateTime',
        'incomplete',
    )

    def __init__(self, vmUuid='', vmName='', vmCategory='', architecture='',
                 schemaVersion='', metadataPath='', sizeBytes=0,
                 lastUpdateTime=0, incomplete=False):
        self.vmUuid = vmUuid
        self.vmName = vmName
        self.vmCategory = vmCategory
        self.architecture = architecture
        self.schemaVersion = schemaVersion
        self.metadataPath = metadataPath
        self.sizeBytes = sizeBytes
        self.lastUpdateTime = lastUpdateTime
        self.incomplete = incomplete

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


class VmMetadataHandler(object):
    def write(self, cmd):
        """Write VM metadata.  Returns ``dict``."""
        return self._do_write(
            metadataPath=cmd.metadataPath,
            metadata=cmd.metadata,
            vmInstanceUuid=getattr(cmd, 'vmInstanceUuid', None) or '',
            vmInstanceName=getattr(cmd, 'vmInstanceName', None) or '',
            architecture=getattr(cmd, 'architecture', None) or '',
            schemaVersion=getattr(cmd, 'schemaVersion', None) or '',
        )

    def get(self, cmd):
        """Read a single VM metadata file's content.  Returns ``dict`` with key ``metadata``."""
        return self._do_get(cmd.metadataPath)

    def get_all(self, cmd):
        """Retrieve all VM metadata entries.  Returns ``dict``."""
        return self._do_get_all(cmd.metadataPath)

    def scan(self, cmd):
        return self._do_scan(cmd.metadataDir)

    def cleanup(self, cmd):
        """Delete a VM's metadata.  Returns ``dict``."""
        return self._do_cleanup(cmd.metadataPath)

    def _do_write(self, metadataPath, metadata, vmInstanceUuid, vmInstanceName, architecture, schemaVersion):
        raise NotImplementedError

    def _do_get(self, metadataPath):
        """Read a single metadata file.  Returns ``dict`` with key ``metadata``."""
        raise NotImplementedError

    def _do_get_all(self, metadataPath):
        raise NotImplementedError

    def _do_scan(self, metadataDir):
        """Returns list of VmMetadataScanEntry."""
        raise NotImplementedError

    def _do_cleanup(self, metadataPath):
        raise NotImplementedError

