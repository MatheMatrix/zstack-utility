from typing import Type, TypeVar

from kvmagent import kvmagent
from zstacklib.utils import jsonobject


# ============================================================================
# Shared Models
# ============================================================================

class PVRef(object):
    pvUuid = None # type: str | None
    pvName = None # type: str | None
    pvDevicePath = None # type: str | None


class PVHealthRef(PVRef):
    healthy = None # type: bool | None


class VGRef(object):
    vgUuid = None # type: str | None
    vgName = None # type: str | None


class LVRef(object):
    lvUuid = None # type: str | None
    lvName = None # type: str | None
    lvPath = None # type: str | None


class FileSystemRef(object):
    fsUuid = None # type: str | None
    fsType = None # type: str | None


class VolumeRef(object):
    volumeUuid = None # type: str | None
    installPath = None # type: str | None
    deviceType = None # type: str | None
    format = None # type: str | None
    size = None # type: int | None


class CacheTO(object):
    """Corresponds to Java CacheTO extends BaseVirtualDeviceTO"""
    cacheUuid = None          # type: str | None
    poolUuid = None           # type: str | None
    installPath = None        # type: str | None
    cacheMode = None          # type: str | None


class VolumeTO(object):
    """Corresponds to Java VolumeTO extends BaseVirtualDeviceTO"""

    # Device type constants (mirrors Java static fields)
    FILE = "file"
    ISCSI = "iscsi"
    CEPH = "ceph"
    SHAREDBLOCK = "sharedblock"
    SCSILUN = "scsilun"
    BLOCK = "block"
    MINISTORAGE = "mini"
    QUORUM = "quorum"
    VHOST = "vhost"
    CBD = "cbd"

    # Instance fields
    installPath = None        # type: str | None
    size = None               # type: int | None
    deviceId = None           # type: int | None
    deviceType = "file"       # type: str
    volumeUuid = None         # type: str
    chapUsername = None       # type: str | None
    chapPassword = None       # type: str | None
    secretUuid = None         # type: str | None
    monInfo = None            # type: list[jsonobject.JsonObject] | None

    useVirtio = None          # type: bool | None
    useVirtioSCSI = None      # type: bool | None
    shareable = None          # type: bool | None
    cacheMode = "none"        # type: str
    aioNative = None          # type: bool | None
    wwn = None                # type: str | None
    bootOrder = None          # type: int | None
    physicalBlockSize = None  # type: int | None
    type = None               # type: str | None
    format = None             # type: str | None
    primaryStorageType = None # type: str | None
    multiQueues = None        # type: str | None
    ioThreadId = None         # type: int | None
    ioThreadPin = None        # type: str | None
    controllerIndex = None    # type: int | None
    cache = None              # type: CacheTO | None

    _nested_types = {
        'cache': CacheTO,
    }


# ============================================================================
# Nested deserialization helper
# ============================================================================

def _collect_nested_types(cls):
    """Collect _nested_types mappings from the entire MRO chain of *cls*.

    Later (more-derived) classes override earlier ones when keys collide.
    """
    merged = {}
    for klass in reversed(cls.mro()):
        nt = klass.__dict__.get('_nested_types')
        if nt and isinstance(nt, dict):
            merged.update(nt)
    return merged


def _deserialize_nested(cls, json_object):
    """Instantiate *cls* and populate its declared class-level attributes
    from *json_object* (a ``jsonobject.JsonObject``).  Nested data-model
    classes referenced via ``_nested_types`` are recursively instantiated.
    """
    obj = cls.__new__(cls)
    nested = _collect_nested_types(cls)

    for klass in reversed(cls.mro()):
        if klass is object:
            continue
        for attr, value in klass.__dict__.items():
            if attr.startswith('_'):
                continue
            if callable(value) or isinstance(value, (staticmethod, classmethod, property)):
                continue
            if attr not in json_object.to_dict():
                continue

            raw = getattr(json_object, attr)

            if attr in nested and raw is not None and isinstance(raw, jsonobject.JsonObject):
                setattr(obj, attr, _deserialize_nested(nested[attr], raw))
            elif attr in nested and raw is not None and isinstance(raw, list):
                inner_cls = nested[attr]
                setattr(obj, attr, [
                    _deserialize_nested(inner_cls, item)
                    if isinstance(item, jsonobject.JsonObject) else item
                    for item in raw
                ])
            else:
                setattr(obj, attr, raw)
    return obj


# ============================================================================
# Base Command/Response
# ============================================================================
_T = TypeVar("_T", bound="VMLocalVolumeCacheBaseCommand")

class VMLocalVolumeCacheBaseCommand(kvmagent.AgentCommand):
    """Base command class with nested deserialization support.

    Subclasses may declare a ``_nested_types`` dict mapping attribute names
    to their data-model classes.  ``from_json`` will recursively instantiate
    those nested classes from the corresponding ``JsonObject`` subtree.
    """

    @classmethod
    def from_json(cls, json_object):
        # type: (Type[_T], jsonobject.JsonObject) -> _T
        return _deserialize_nested(cls, json_object)


class VMLocalVolumeCacheBaseResponse(kvmagent.AgentResponse):
    """Base response class"""

    success = True # type: bool
    __error = "" # type: str

    @property
    def error(self):
        return self.__error

    @error.setter
    def error(self, value):
        if value is None or value == "":
            self.success = True
        else:
            self.success = False
        self.__error = value
        self.__dict__['error'] = value

class BaseCmd(VMLocalVolumeCacheBaseCommand):
    poolUuid = None # type: str

class PoolBaseCmd(BaseCmd):
    mountPoint = None # type: str
    force = False # type: bool


class CacheBaseCmd(BaseCmd):
    volume = None # type: VolumeTO

    _nested_types = {
        'volume': VolumeTO,
    }


# ============================================================================
# Command Definitions
# ============================================================================

class InitPoolCmd(PoolBaseCmd):
    """Initialize cache pool on host"""

    pvs = None # type: list[str]


class ConnectPoolCmd(PoolBaseCmd):
    """Connect to existing cache pool"""
    pass


class ExtendPoolCmd(PoolBaseCmd):
    """Extend cache pool pvs and capacity"""

    pvs = None # type: list[str]


class DeletePoolCmd(PoolBaseCmd):
    """Delete cache pool"""
    pass


class CheckPoolCmd(PoolBaseCmd):
    """Check pool health status"""
    pass


class GetPoolCapacityCmd(PoolBaseCmd):
    """Get pool capacity"""
    pass


class GcPoolCmd(PoolBaseCmd):
    """Garbage collect unexpected files/directories in pool mount point"""
    volumes = None  # type: list[VolumeTO] | None

    _nested_types = {
        'volumes': VolumeTO,
    }


class AllocateCacheCmd(CacheBaseCmd):
    """Allocate cache volume"""
    pass


class DeleteCacheCmd(CacheBaseCmd):
    """Release cache volume"""
    pass


class FlushCacheCmd(CacheBaseCmd):
    """Flush cache to backing volume"""
    pass


class GetCacheCapacityCmd(CacheBaseCmd):
    """Get cache file capacity"""
    pass


# ============================================================================
# Response Definitions
# ============================================================================

class EmptyRsp(VMLocalVolumeCacheBaseResponse):
    """Empty response"""
    pass


class PoolRsp(VMLocalVolumeCacheBaseResponse):
    """Pool details response"""

    poolUuid = None # type: str | None
    mountPoint = None # type: str | None
    pvs = None # type: list[PVRef] | None
    vg = None # type: VGRef | None
    lv = None # type: LVRef | None
    filesystem = None # type: FileSystemRef | None


class PoolHealthRsp(VMLocalVolumeCacheBaseResponse):
    """Pool health response"""

    healthy = None # type: bool | None
    pvs = None # type: list[PVHealthRef] | None
    vg = None # type: bool | None
    lv = None # type: bool | None
    filesystem = None # type: bool | None


class PoolCapacityRsp(VMLocalVolumeCacheBaseResponse):
    """Pool capacity response"""

    total = None # type: int | None
    used = None # type: int | None
    available = None # type: int | None
    allocated = None # type: int | None
    dirty = None # type: int | None


class CacheRsp(VMLocalVolumeCacheBaseResponse):
    """Allocate cache volume response"""

    installPath = None # type: str | None
    virtualSize = None # type: int | None
    actualSize = None # type: int | None



class GcPoolRsp(VMLocalVolumeCacheBaseResponse):
    """Pool GC response"""

    gcFiles = None  # type: list[str] | None
    gcCount = None  # type: int | None


InitPoolRsp = ConnectPoolRsp = ExtendPoolRsp = PoolRsp
DeleteCacheRsp = DeletePoolRsp = EmptyRsp
