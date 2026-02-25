from functools import partial, reduce
from kvmagent.plugins.vm_local_volume_cache.command_wrapper.filesystem import FileSystemCommandWrapper, FileSystemInfoFields, MountPointInfoFields
from kvmagent.plugins.vm_local_volume_cache.command_wrapper.lvm import LVInfoFields, LvmCommandWrapper, LvmObjectType, PVInfoFields, VGInfoFields
from kvmagent.plugins.vm_local_volume_cache.command_wrapper.qemu_img import QemuImgCommandWrapper


class LvmObjectInfoMeta(type):
    object_type_map = {
            LvmObjectType.PV: {"fields": PVInfoFields, "loader": partial(LvmCommandWrapper.get_lvm_object_by_uuid, object_type=LvmObjectType.PV)},
            LvmObjectType.VG: {"fields": VGInfoFields, "loader": partial(LvmCommandWrapper.get_lvm_object_by_uuid, object_type=LvmObjectType.VG)},
            LvmObjectType.LV: {"fields": LVInfoFields, "loader": partial(LvmCommandWrapper.get_lvm_object_by_uuid, object_type=LvmObjectType.LV)},
        }

    def __new__(mcs, name, bases, attrs):
        cls = super(LvmObjectInfoMeta, mcs).__new__(mcs, name, bases, attrs)
        if name == 'LvmObjectInfo':
            return cls
        object_type = attrs.get("_object_type")
        if not object_type:
            raise Exception("LvmObjectInfo subclass must define _object_type class variable")
        if object_type not in mcs.object_type_map:
            raise Exception("Unsupported LVM object type: %s" % object_type)
        
        setattr(cls, "_fields", mcs.object_type_map[object_type]["fields"])
        setattr(cls, "_loader", mcs.object_type_map[object_type]["loader"])

        return cls

class LvmObjectInfo(object):
    __metaclass__ = LvmObjectInfoMeta

    # Instance variables
    __info = None # type: dict[str, str] | None
    _uuid = None # type: str | None

    # Class variables
    _object_type = None # type: LvmObjectType | None
    _fields = None # type: type[PVInfoFields | VGInfoFields | LVInfoFields] | None
    _loader = None

    def __init__(self, uuid):
        # type: (str) -> None
        self._uuid = uuid

    def reload(self):
        # type: () -> None
        self.__info = None

    def _load(self):
        # type: () -> dict[str, str]
        info = self._loader(object_uuid=self._uuid) # type: ignore

        if not info:
            raise Exception("No such LVM object with UUID: %s" % self._uuid)

        return info

    def __getitem__(self, name):
        # type: (str|PVInfoFields|VGInfoFields|LVInfoFields) -> str
        key = name.value if isinstance(name, (PVInfoFields, VGInfoFields, LVInfoFields)) else name
        if not self.__info:
            self.__info = self._load()
        if (self._fields is not None) and (key not in self._fields._value2member_map_):
            raise KeyError("No such field: %s" % name)
        return self.__info.get(key, "")

    def __len__(self):
        if not self.__info:
            self.__info = self._load()
        return len(self.__info)
    
    def __hash__(self):
        return hash(self._uuid)

class PVInfo(LvmObjectInfo):
    _object_type = LvmObjectType.PV

    def __str__(self):
        return "<pv_uuid=%s, pv_name=%s>" % (self._uuid, self[PVInfoFields.PV_NAME])
    
    def __repr__(self):
        return self.__str__()

class VGInfo(LvmObjectInfo):
    _object_type = LvmObjectType.VG

    def __str__(self):
        return "<vg_uuid=%s, vg_name=%s>" % (self._uuid, self[VGInfoFields.VG_NAME])
    
    def __repr__(self):
        return self.__str__()

class LVInfo(LvmObjectInfo):
    _object_type = LvmObjectType.LV

    def __str__(self):
        return "<lv_uuid=%s, lv_name=%s>" % (self._uuid, self[LVInfoFields.LV_NAME])
    
    def __repr__(self):
        return self.__str__()

class FileSystemInfo(object):
    __info = None # type: dict[str, str] | None

    block_device = None # type: str | None

    def __init__(self, block_device):
        # type: (str) -> None
        self.block_device = block_device
    
    def reload(self):
        # type: () -> None
        self.__info = None

    def _load(self):
        # type: () -> dict[str, str]
        if not self.block_device:
            raise Exception("Block device is not specified for FileSystemInfo")
        info = FileSystemCommandWrapper.get_filesystem_object(self.block_device)
        if not info:
            raise Exception("No filesystem found on block device: %s" % self.block_device)
        return info
    
    def __getitem__(self, name):
        # type: (str|FileSystemInfoFields) -> str
        key = name.value if isinstance(name, FileSystemInfoFields) else name
        if not self.__info:
            self.__info = self._load()
        if key not in FileSystemInfoFields._value2member_map_:
            raise KeyError("No such field: %s" % name)
        return self.__info.get(key, "")
    
    def __len__(self):
        if not self.__info:
            self.__info = self._load()
        return len(self.__info)

    def __str__(self):
        return "<block_device=%s, type=%s>" % (self.block_device, self[FileSystemInfoFields.TYPE])
    
    def __repr__(self):
        return self.__str__()
    
    def __hash__(self):
        return hash(self[FileSystemInfoFields.UUID])

class PoolCapacityInfo(object):
    total = None # type: int | None
    used = None # type: int | None
    available = None # type: int | None
    allocated = None # type: int | None
    dirty = None # type: int | None

    def __init__(self, total, used, available, allocated, dirty):
        # type: (str|int, str|int, str|int, str|int, str|int) -> None
        self.total = int(total)
        self.used = int(used)
        self.available = int(available)
        self.allocated = int(allocated)
        self.dirty = int(dirty)

class CacheCapacityInfo(object):
    virtual_size = None # type: int | None
    actual_size = None # type: int | None

    def __init__(self, virtual_size, actual_size):
        # type: (str|int, str|int) -> None
        self.virtual_size = int(virtual_size)
        self.actual_size = int(actual_size)

class MountPointInfo(object):
    __info = None # type: dict[str, str] | None

    filesystem_uuid = None # type: str
    mount_path = None # type: str

    def __init__(self, filesystem_uuid, mount_path):
        # type: (str, str) -> None
        self.filesystem_uuid = filesystem_uuid
        self.mount_path = mount_path
    
    def reload(self):
        # type: () -> None
        self.__info = None

    @property
    def capacity(self):
        # type: () -> PoolCapacityInfo
        if not self.__info:
            self.__info = self._load()
        qcow2_files = list(filter(lambda file_path: QemuImgCommandWrapper.get_img_fmt(file_path) == "qcow2",
                                  FileSystemCommandWrapper.get_all_files(self.mount_path)))
        allocated_size = 0
        dirty_size = 0
        if qcow2_files:
            allocated_size = reduce(lambda x, y: x + y, 
                                    map(lambda file_path: QemuImgCommandWrapper.get_qcow2_virtual_size(file_path),
                                        qcow2_files))
            dirty_size = reduce(lambda x, y: x + y, 
                                map(lambda file_path: QemuImgCommandWrapper.get_qcow2_actual_size(file_path),
                                    qcow2_files))
        return PoolCapacityInfo(total=self[MountPointInfoFields.SIZE],
                                used=self[MountPointInfoFields.USED],
                                available=self[MountPointInfoFields.AVAIL],
                                allocated=allocated_size,
                                dirty=dirty_size)

    def _load(self):
        # type: () -> dict[str, str]
        if not self.filesystem_uuid or not self.mount_path:
            raise Exception("Block device or mount path is not specified for MountPointInfo")
        info = FileSystemCommandWrapper.get_mount_point(self.filesystem_uuid, self.mount_path)
        if not info:
            raise Exception("No mount point found for device %s on mount path: %s" % (self.filesystem_uuid, self.mount_path))
        return info
    
    def __getitem__(self, name):
        # type: (str|MountPointInfoFields) -> str
        key = name.value if isinstance(name, MountPointInfoFields) else name
        if not self.__info:
            self.__info = self._load()
        if key not in MountPointInfoFields._value2member_map_:
            raise KeyError("No such field: %s" % name)
        return self.__info.get(key, "")
    
    def __len__(self):
        if not self.__info:
            self.__info = self._load()
        return len(self.__info)

    def __str__(self):
        return "<filesystem_uuid=%s, mount_path=%s>" % (self.filesystem_uuid, self.mount_path)
    
    def __repr__(self):
        return self.__str__()
    
    def __hash__(self):
        return hash("%s:%s" % (self.filesystem_uuid, self.mount_path))

class Qcow2FileInfo(object):

    file_path = None # type: str | None

    def __init__(self, file_path):
        # type: (str) -> None
        self.file_path = file_path
    
    @property
    def virtual_size(self):
        # type: () -> int
        assert self.file_path
        return QemuImgCommandWrapper.get_qcow2_virtual_size(self.file_path)
    
    @property
    def actual_size(self):
        # type: () -> int
        assert self.file_path
        return QemuImgCommandWrapper.get_qcow2_actual_size(self.file_path)
    
    @property
    def cluster_size(self):
        # type: () -> int
        assert self.file_path
        return QemuImgCommandWrapper.get_qcow2_cluster_size(self.file_path)

class PoolHealthInfo(object):
    pvs = None # type: dict[PVInfo, bool] | None
    vg = False # type: bool
    lv = False # type: bool
    filesystem = False # type: bool

    @property
    def is_healthy(self):
        # type: () -> bool
        all_pvs_healthy = all(self.pvs.values()) if self.pvs is not None else False
        return all([all_pvs_healthy, self.vg, self.lv, self.filesystem])

    def __init__(self, pvs, vg, lv, filesystem):
        # type: (dict[PVInfo, bool], bool, bool, bool) -> None
        self.pvs = pvs
        self.vg = vg
        self.lv = lv
        self.filesystem = filesystem
