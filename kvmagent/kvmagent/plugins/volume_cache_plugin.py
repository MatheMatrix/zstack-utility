"""
VM Local Volume Cache Plugin
Manages local cache pool and cache volumes for VMs on compute nodes
"""
import functools
import json
import os
import traceback
from typing import Any, Callable, Type, TypeVar
from kvmagent import kvmagent
from zstacklib.utils import jsonobject
from zstacklib.utils import http
from zstacklib.utils import linux
from zstacklib.utils import log
from zstacklib.utils import plugin
from zstacklib.utils import qemu_img
from zstacklib.utils import report
from zstacklib.utils import traceable_shell
from zstacklib.utils import lvm
from zstacklib.utils import virsh
from zstacklib.utils.linux import FileSystemInfo, MountPointInfo
from zstacklib.utils.lvm import PVInfo, VGInfo, LVInfo
from zstacklib.utils.rollback import rollback, rollbackable

class PoolNotInitializedError(Exception):
    pass


class PoolNotFoundError(Exception):
    pass


class PoolOperationError(Exception):
    pass


class CacheNotInstantiatedError(Exception):
    pass


class CacheOperationError(Exception):
    pass


class UnsupportedDeviceTypeError(Exception):
    pass

class CacheTO(object):
    cacheUuid = None          # type: str | None
    poolUuid = None           # type: str | None
    installPath = None        # type: str | None
    cacheMode = None          # type: str | None


class VolumeTO(object):
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

def _collect_nested_types(cls):
    merged = {}
    for klass in reversed(cls.mro()):
        nt = klass.__dict__.get('_nested_types')
        if nt and isinstance(nt, dict):
            merged.update(nt)
    return merged


def _deserialize_nested(cls, json_object):
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

_T = TypeVar("_T", bound="VolumeCacheBaseCommand")

class VolumeCacheBaseCommand(kvmagent.AgentCommand):
    @classmethod
    def from_json(cls, json_object):
        # type: (Type[_T], jsonobject.JsonObject) -> _T
        return _deserialize_nested(cls, json_object)


class VolumeCacheBaseResponse(kvmagent.AgentResponse):
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

class BaseCmd(VolumeCacheBaseCommand):
    poolUuid = None # type: str

class PoolBaseCmd(BaseCmd):
    mountPoint = None # type: str
    force = False # type: bool


class CacheBaseCmd(BaseCmd):
    volume = None # type: VolumeTO

    _nested_types = {
        'volume': VolumeTO,
    }

class InitPoolCmd(PoolBaseCmd):
    devices = None # type: list[str]


class ConnectPoolCmd(PoolBaseCmd):
    pass


class ExtendPoolCmd(PoolBaseCmd):
    devices = None # type: list[str]


class DeletePoolCmd(PoolBaseCmd):
    pass


class CheckPoolCmd(PoolBaseCmd):
    pass


class GetPoolCapacityCmd(PoolBaseCmd):
    pass


class GcPoolCmd(PoolBaseCmd):
    inUseCacheUuids = None  # type: list[str] | None


class AllocateCacheCmd(CacheBaseCmd):
    pass


class DeleteCacheCmd(CacheBaseCmd):
    pass


class FlushCacheCmd(CacheBaseCmd):
    sendCommandUrl = None
    threadContext = None
    threadContextStack = None
    taskContext = None


class GetCacheCapacityCmd(CacheBaseCmd):
    pass


class PoolRsp(VolumeCacheBaseResponse):
    poolUuid = None # type: str | None
    mountPoint = None # type: str | None
    totalCapacity = None # type: int | None
    availableCapacity = None # type: int | None
    totalPhysicalCapacity = None # type: int | None
    availablePhysicalCapacity = None # type: int | None
    systemUsedCapacity = None # type: int | None


class PoolHealthRsp(VolumeCacheBaseResponse):
    poolUuid = None # type: str | None
    mountPoint = None # type: str | None
    healthy = None # type: bool | None
    reason = None # type: str | None


class CacheRsp(PoolRsp):
    installPath = None # type: str | None
    virtualSize = None # type: int | None
    actualSize = None # type: int | None


class GcPoolRsp(PoolRsp):
    gcFiles = None  # type: list[str] | None
    gcCount = None  # type: int | None


InitPoolRsp = ConnectPoolRsp = ExtendPoolRsp = PoolCapacityRsp = DeleteCacheRsp = PoolRsp
DeletePoolRsp = VolumeCacheBaseResponse


class PoolCapacityInfo(object):
    total = None # type: int | None
    available = None # type: int | None
    total_physical = None # type: int | None
    available_physical = None # type: int | None
    system_used = None # type: int | None

    def __init__(self, total, available, total_physical, available_physical, system_used):
        # type: (str|int, str|int, str|int, str|int, str|int) -> None
        self.total = int(total)
        self.available = int(available)
        self.total_physical = int(total_physical)
        self.available_physical = int(available_physical)
        self.system_used = int(system_used)

class CacheCapacityInfo(object):
    virtual_size = None # type: int | None
    actual_size = None # type: int | None

    def __init__(self, virtual_size, actual_size):
        # type: (str|int, str|int) -> None
        self.virtual_size = int(virtual_size)
        self.actual_size = int(actual_size)


def get_mount_point_capacity(mount_point):
    # type: (MountPointInfo) -> PoolCapacityInfo
    qcow2_files = [file_path for file_path in linux.list_all_file(mount_point.mount_path)
                   if linux.get_img_fmt(file_path) == "qcow2"]
    allocated_size = 0
    dirty_size = 0
    for file_path in qcow2_files:
        virtual_size, actual_size = linux.qcow2_size_and_actual_size(file_path)
        allocated_size += virtual_size or 0
        dirty_size += actual_size or 0
    total_physical_size = int(mount_point["size"])
    available_physical_size = int(mount_point["avail"])
    system_used_size = max(0, int(mount_point["used"]) - dirty_size)
    return PoolCapacityInfo(total=total_physical_size,
                            available=total_physical_size - allocated_size - system_used_size,
                            total_physical=total_physical_size,
                            available_physical=available_physical_size,
                            system_used=system_used_size)

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


DEFAULT_ZBS_CONF_PATH = "/etc/zbs/client.conf"
DEFAULT_ZBS_USER_NAME = "zbs"
PROTOCOL_CBD_PREFIX = "cbd:"

class BackingVolume(object):
    volume = None # type: JsonObject | None

    @property
    def volume_format(self):
        assert self.volume, "volume must be set"
        volume_format_str = self.volume.format # type: str | None
        if not volume_format_str:
            return "raw"
        return volume_format_str

    @property
    def output_format(self):
        raise NotImplementedError("output_format is not implemented for base BackingVolume class")

    @property
    def source_path(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"
        return self.volume.installPath # type: str

    def __init__(self, volume):
        # type: (JsonObject) -> None
        self.volume = volume

class IscsiBackingVolume(BackingVolume):
    target = None # type: str | None
    lun = None # type: str | None
    server_hostname = None # type: str | None
    server_port = None # type: str | None
    chap_username = None # type: str | None
    chap_password = None # type: str | None

    @property
    def volume_format(self):
        return "raw"

    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat.ISCSI

    @property
    def source_path(self):
        base_url = "iscsi://%s:%s/%s/%s" % (
            self.server_hostname, self.server_port, self.target, self.lun)
        if self.chap_username and self.chap_password:
            return "%s?chapUsername=%s&chapPassword=%s" % (
                base_url, self.chap_username, self.chap_password)
        return base_url

    def __init__(self, volume):
        super(IscsiBackingVolume, self).__init__(volume)
        self.__parse_iscsi_url()

    def __parse_iscsi_url(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"

        url = self.volume.installPath # type: str
        portal, self.target, self.lun = url.replace("iscsi://", "").split("/")
        self.server_hostname, self.server_port = portal.split(":")
        self.chap_username = self.volume.chapUsername
        self.chap_password = self.volume.chapPassword

class FileBackingVolume(BackingVolume):
    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat(self.volume_format)

class CephBackingVolume(BackingVolume):
    pool = None # type: str | None
    image = None # type: str | None
    secret_uuid = None # type: str | None
    secret_key = None # type: str | None
    mon_infos = None # type: list[tuple[str, int]] | None

    @property
    def volume_format(self):
        return "raw"

    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat.RBD

    @property
    def source_path(self):
        assert self.volume, "volume must be set"
        assert self.mon_infos, "mon_infos must be set"

        portal_str = "rbd"
        img_info_str = "%s/%s" % (self.pool, self.image)
        mon_host_str = "mon_host=%s" % "\\;".join(["%s\\:%s" % (host, port) for host, port in self.mon_infos])
        if self.secret_uuid and self.secret_key:
            auth_str = "id=%s:key=%s:auth_supported=cephx\\;none" % ("zstack", self.secret_key)
            return ":".join([portal_str, img_info_str, auth_str, mon_host_str])
        return ":".join([portal_str, img_info_str, mon_host_str])


    def __init__(self, volume):
        super(CephBackingVolume, self).__init__(volume)
        self.__parse_ceph_url()

    def __parse_ceph_url(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"

        url = self.volume.installPath # type: str
        self.pool, self.image = url.replace("ceph://", "").split("/")
        self.secret_uuid = self.volume.secretUuid
        self.secret_key = self.__get_secret_key() if self.secret_uuid else None
        self.mon_infos = self.__get_mon_info()

    def __get_mon_info(self):
        assert self.volume, "volume must be set"
        assert self.volume.monInfo, "volume.monInfo must be set"
        mon_infos = [(mon_info.hostname, mon_info.port) for mon_info in self.volume.monInfo] # type: list[tuple[str, int]]
        return mon_infos

    def __get_secret_key(self):
        assert self.secret_uuid, "secret_uuid must be set"
        return virsh.get_secret_value(self.secret_uuid)

class ScsiLunBackingVolume(BackingVolume):
    @property
    def volume_format(self):
        return "raw"

    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat.RAW

class BlockBackingVolume(BackingVolume):
    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat(self.volume_format)

class SpoolBackingVolume(BackingVolume):
    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat(self.volume_format)

class CbdBackingVolume(BackingVolume):
    def make_cbd_conf(self, install_path):
        # type: (str) -> str
        return PROTOCOL_CBD_PREFIX + install_path[len(PROTOCOL_CBD_PREFIX):] + "_" + DEFAULT_ZBS_USER_NAME + "_:" + DEFAULT_ZBS_CONF_PATH

    @property
    def volume_format(self):
        return "raw"

    @property
    def output_format(self):
        return qemu_img.QemuImgOutputFormat.CBD

    @property
    def source_path(self):
        return self.make_cbd_conf(super(CbdBackingVolume, self).source_path)

supported_backing_volume_classes = {
    VolumeTO.ISCSI: IscsiBackingVolume,
    VolumeTO.FILE: FileBackingVolume,
    VolumeTO.CEPH: CephBackingVolume,
    VolumeTO.SCSILUN: ScsiLunBackingVolume,
    VolumeTO.BLOCK: BlockBackingVolume,
    "spool": SpoolBackingVolume,
    VolumeTO.CBD: CbdBackingVolume
} # type: dict[str, type[BackingVolume]]


logger = log.get_logger(__name__)


def _remove_lvm_filter_devices_best_effort(devices, pool_uuid):
    if not devices:
        return
    try:
        lvm.remove_lvm_filter_devices(devices)
    except Exception:
        logger.warn("failed to remove host cache store devices from LVM filter for pool %s: %s" %
                    (pool_uuid, traceback.format_exc()))


def ensure_pool_initialized(func):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        self = args[0] # type: PoolProcessor
        if not self.is_initialized:
            raise PoolNotInitializedError("Pool %s is not initialized" % self.pool_uuid)
        return func(*args, **kwargs)
    return wrap

class PoolProcessor(object):
    VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX = "zs::volume_cache_pool"
    VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG = "%s::%s" % (VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "managed")
    VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX = "%s::%s" % (VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "pool_uuid")
    VM_LOCAL_VOLUME_CACHE_POOL_MOUNT_PATH_LVM_TAG_PREFIX = "%s::%s" % (VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "mount_path")

    # Legacy (pre-rename) LVM tag prefix constants. Kept for read/scan
    # compatibility so that hosts upgraded from older releases -- where VG/PV/LV
    # metadata is still tagged with the old ``zs::vm_local_volume_cache_pool*``
    # prefix -- remain discoverable. All write paths (create/add-tag/remove-tag)
    # must continue to use the canonical new prefix above.
    LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX = "zs::vm_local_volume_cache_pool"
    LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG = "%s::%s" % (LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "managed")
    LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX = "%s::%s" % (LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "pool_uuid")
    LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_MOUNT_PATH_LVM_TAG_PREFIX = "%s::%s" % (LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_LVM_TAG_PREFIX, "mount_path")

    VM_LOCAL_VOLUME_CACHE_POOL_LVM_NAME_PREFIX = "vlvc_pool"
    HEARTBEAT_FILE_RELATIVE_PATH = ".heartbeat"

    pool_uuid = None  # type: str
    mount_path = None  # type: str

    pvs = None  # type: list[PVInfo] | None
    vg = None  # type: VGInfo | None
    lv = None  # type: LVInfo | None
    fs = None  # type: FileSystemInfo | None
    mount_point = None  # type: MountPointInfo | None

    @property
    def pool_tag(self):
        # type: () -> str
        return "%s::%s" % (self.VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX, self.pool_uuid)

    @property
    def legacy_pool_tag(self):
        # type: () -> str
        return "%s::%s" % (self.LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX, self.pool_uuid)

    @property
    def mount_path_tag(self):
        # type: () -> str
        return "%s::%s" % (self.VM_LOCAL_VOLUME_CACHE_POOL_MOUNT_PATH_LVM_TAG_PREFIX, self.mount_path)

    @property
    def vg_name(self):
        return "%s_vg_%s" % (self.VM_LOCAL_VOLUME_CACHE_POOL_LVM_NAME_PREFIX, self.pool_uuid)

    @property
    def lv_name(self):
        return "%s_lv_%s" % (self.VM_LOCAL_VOLUME_CACHE_POOL_LVM_NAME_PREFIX, self.pool_uuid)

    @property
    def vg_metadata_size(self):
        # type: () -> str
        if not self.vg:
            return "512M"
        return self.vg["vg_mda_size"]

    @property
    def heartbeat_file_path(self):
        # type: () -> str
        return os.path.join(self.mount_path, self.HEARTBEAT_FILE_RELATIVE_PATH)

    @property
    def is_initialized(self):
        # type: () -> bool
        return all([self.pvs, self.vg, self.lv, self.fs, self.mount_point])

    def __init__(self, pool_uuid, mount_path):
        # type: (str, str) -> None
        self.pool_uuid = pool_uuid
        self.mount_path = mount_path

    @classmethod
    def discover_local_pool(cls, pool_uuid):
        # type: (str) -> PoolProcessor|None
        lvm.rescan_lvm()

        lv_objects_by_uuid = {}
        for pool_uuid_tag in (cls.VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX + "::" + pool_uuid,
                              cls.LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_UUID_LVM_TAG_PREFIX + "::" + pool_uuid):
            found = lvm.get_lvm_objects(
                "logical_volume", tag=pool_uuid_tag,
                fields=["lv_uuid", "lv_name", "lv_tags", "vg_name"])
            if not found:
                continue
            for lv_object in found:
                if not cls._is_managed_lv_object(lv_object):
                    continue
                lv_objects_by_uuid.setdefault(lv_object["lv_uuid"], lv_object)

        if not lv_objects_by_uuid:
            return None
        if len(lv_objects_by_uuid) > 1:
            raise PoolOperationError("Multiple local volume cache LVs found for pool UUID %s" % pool_uuid)

        lv_object = list(lv_objects_by_uuid.values())[0]
        mount_path_tag = cls._get_mount_path_tag_from_lv_object(lv_object)
        if not mount_path_tag:
            raise PoolOperationError("LV %s in VG %s is tagged for pool UUID %s but missing mount path tag" % (
                lv_object["lv_name"], lv_object["vg_name"], pool_uuid))

        return cls(pool_uuid, mount_path_tag.split("::", 3)[-1])

    @classmethod
    def _get_mount_path_tag_from_lv_object(cls, lv_object):
        # type: (dict[str, Any]) -> str|None
        lv_tags = lv_object["lv_tags"].split(",")
        mount_path_prefixes = (cls.VM_LOCAL_VOLUME_CACHE_POOL_MOUNT_PATH_LVM_TAG_PREFIX,
                               cls.LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_MOUNT_PATH_LVM_TAG_PREFIX)
        return next((tag for prefix in mount_path_prefixes for tag in lv_tags if tag.startswith(prefix + "::")), None)

    @classmethod
    def _is_managed_lv_object(cls, lv_object):
        # type: (dict[str, Any]) -> bool
        lv_tags = lv_object["lv_tags"].split(",")
        managed_tags = (cls.VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG,
                        cls.LEGACY_VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG)
        return any(tag in lv_tags for tag in managed_tags)

    def __create_pvs(self, device_paths, metadata_size=None, force=False):
        # type: (list[str], str|None, bool) -> list[PVInfo]
        metadata_size = metadata_size or "512M"
        created_pvs = []
        for device_path in device_paths:
            linux.wipe_block_device_superblock(device_path, force=force)
            pv_uuid = lvm.create_pv(device_path, metadata_size=metadata_size, force=force)
            logger.info("Created PV %s on device %s" % (pv_uuid, device_path))
            created_pvs.append(PVInfo(pv_uuid))

        return created_pvs

    def __remove_pvs(self, device_paths, force=False, is_exception=False):
        # type: (list[str], bool, bool) -> None
        for device_path in device_paths:
            try:
                lvm.remove_pv(device_path, force=force)
                logger.info("Removed PV %s" % device_path)
            except Exception as e:
                logger.error("Failed to remove PV %s : %s" % (device_path, str(e)))
                logger.error(traceback.format_exc())
                if is_exception:
                    raise PoolOperationError("Failed to remove PV %s : %s" % (device_path, str(e)))

    def __create_vg(self, pvs):
        # type: (list[PVInfo]) -> VGInfo
        if not pvs:
            raise Exception("No physical volumes to create VG")
        pv_names = [pv["pv_name"] for pv in pvs]  # type: list[str]
        vg_uuid = lvm.create_vg(
            vg_name=self.vg_name,
            pv_names=pv_names,
            metadata_size="512M")
        for tag in [self.pool_tag, self.mount_path_tag, self.VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG]:
            lvm.add_vg_tag(self.vg_name, tag)
        for pv_name in pv_names:
            for tag in [self.pool_tag, self.mount_path_tag, self.VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG]:
                lvm.add_pv_tag(pv_name, tag)
        return VGInfo(vg_uuid)

    def __remove_vg(self, force=False, is_exception=False):
        # type: (bool, bool) -> None
        try:
            lvm.remove_vg(self.vg_name, force=force)
            logger.info("Removed VG %s" % self.vg_name)
        except Exception as e:
            logger.error("Failed to remove VG %s: %s" % (self.vg_name, str(e)))
            logger.error(traceback.format_exc())
            if is_exception:
                raise PoolOperationError("Failed to remove VG %s: %s" % (self.vg_name, str(e)))

    def __create_lv(self, vg):
        # type: (VGInfo) -> LVInfo
        if not vg:
            raise Exception("Volume group is not created")

        lv_path = "/dev/%s/%s" % (self.vg_name, self.lv_name)
        _, vg_free = lvm.get_vg_size(self.vg_name)
        vg_free = int(float(vg_free or 0))
        if vg_free <= 0:
            raise Exception("No free capacity in VG %s to create LV %s" % (self.vg_name, self.lv_name))
        lvm.create_lv_from_absolute_path(lv_path, vg_free, tag=self.pool_tag, lock=False, exact_size=True)
        for tag in [self.mount_path_tag, self.VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG]:
            lvm.add_lv_tag(lv_path, tag)
        lvm.active_lv(lv_path)
        lv_uuid = lvm.lv_uuid(lv_path)
        if not lv_uuid:
            raise Exception("Failed to create LV %s on VG %s" % (self.lv_name, self.vg_name))
        return LVInfo(lv_uuid)

    def __extend_lv_full_size(self, lv):
        # type: (LVInfo) -> LVInfo
        if not lv:
            raise Exception("Logical volume is not created")
        _, vg_free = lvm.get_vg_size(self.vg_name)
        vg_free = int(float(vg_free or 0))
        if vg_free <= 0:
            return lv
        target_size = lvm.getOriginalSize(int(float(lvm.get_lv_size(lv["lv_path"]))) + vg_free)
        lvm.extend_lv(lv["lv_path"], target_size)  # type: ignore
        lv.reload()
        return lv

    def __remove_lv(self, force=False, is_exception=False):
        # type: (bool, bool) -> None
        try:
            lvm.delete_lv("/dev/%s/%s" % (self.vg_name, self.lv_name), raise_exception=True)
            logger.info("Removed LV %s" % self.lv_name)
        except Exception as e:
            logger.error("Failed to remove LV %s: %s" % (self.lv_name, str(e)))
            logger.error(traceback.format_exc())
            if is_exception:
                raise PoolOperationError("Failed to remove LV %s: %s" % (self.lv_name, str(e)))

    def __make_filesystem(self, lv, force=False):
        # type: (LVInfo, bool) -> FileSystemInfo
        if not lv:
            raise Exception("Logical volume is not created")
        _device_path = lv["lv_path"]  # type: str
        device_path = linux.create_xfs_filesystem(_device_path, force=force)
        return FileSystemInfo(device_path)

    def __extend_filesystem(self, fs):
        # type: (FileSystemInfo) -> FileSystemInfo
        if not fs:
            raise Exception("Filesystem is not created")
        linux.extend_xfs_filesystem(fs.block_device)
        fs.reload()
        return fs

    def __wipe_filesystem(self, force=False, is_exception=False):
        # type: (bool, bool) -> None
        assert self.lv and self.lv["lv_path"], "Logical volume is not available to wipe filesystem signatures"
        block_device = self.lv["lv_path"]
        try:
            linux.wipe_block_device_superblock(
                block_device, force=force)
            logger.info("Wiped filesystem signatures on device %s" % block_device)
        except Exception as e:
            logger.error("Failed to wipe filesystem signatures on device %s: %s"
                         % (block_device, str(e)))
            logger.error(traceback.format_exc())
            if is_exception:
                raise PoolOperationError("Failed to wipe filesystem signatures on device %s: %s"
                                % (block_device, str(e)))

    def __mount_filesystem(self, fs, mount_path):
        # type: (FileSystemInfo, str) -> MountPointInfo
        if not fs:
            raise Exception("Filesystem is not created")
        mounted_source = linux.get_mount_url(mount_path)
        if not mounted_source:
            linux.mount("UUID=%s" % fs["uuid"], mount_path)
        elif os.path.realpath(mounted_source) != os.path.realpath("/dev/disk/by-uuid/%s" % fs["uuid"]):
            raise Exception("Mount path %s is already used by another filesystem" % mount_path)
        return MountPointInfo(fs["uuid"], mount_path)

    def __umount_filesystem(self, mount_path, is_exception=False):
        # type: (str, bool) -> None
        try:
            if linux.is_mounted(path=mount_path):
                linux.umount(mount_path, is_exception=is_exception)
            logger.info("Unmounted filesystem from mount path %s" % mount_path)
        except Exception as e:
            logger.error("Failed to unmount filesystem from mount path %s: %s" % (mount_path, str(e)))
            logger.error(traceback.format_exc())
            if is_exception:
                raise PoolOperationError("Failed to unmount filesystem from mount path %s: %s" % (mount_path, str(e)))

    def __load_pvs(self):
        # type: () -> list[PVInfo]
        pvs = self.__get_lvm_objects_by_pool_tag(
            "physical_volume", ["pv_uuid"])
        if not pvs:
            raise Exception("No PVs found for pool %s" % self.pool_uuid)
        # type: ignore
        return [PVInfo(pv["pv_uuid"]) for pv in pvs]

    def __load_vg(self):
        # type: () -> VGInfo
        vgs = self.__get_lvm_objects_by_pool_tag(
            "volume_group", ["vg_uuid"])
        if not vgs:
            raise Exception("No VG found for pool %s" % self.pool_uuid)
        if len(vgs) > 1:
            raise Exception("Multiple VGs found for pool %s: %s" % (
                self.pool_uuid, ','.join([vg["vg_uuid"] for vg in vgs])))
        return VGInfo(vgs.pop()["vg_uuid"])

    def __load_lv(self):
        # type: () -> LVInfo
        lvs = self.__get_lvm_objects_by_pool_tag(
            "logical_volume",
            ["lv_uuid", "lv_name", "lv_path",
             "lv_active", "vg_name"])
        if not lvs:
            raise Exception("No LV found for pool %s" % self.pool_uuid)
        if len(lvs) > 1:
            raise Exception("Multiple LVs found for pool %s: %s" % (
                self.pool_uuid, ','.join([lv["lv_uuid"] for lv in lvs])))
        lv = lvs.pop()
        if lv["lv_active"] != "active":
            lvm.active_lv(lv["lv_path"])
        return LVInfo(lv["lv_uuid"])

    def __get_lvm_objects_by_pool_tag(self, object_type, fields):
        # type: (str, list) -> list[dict[str, str]]
        primary_field = fields[0]
        merged = {}
        for tag in (self.pool_tag, self.legacy_pool_tag):
            found = lvm.get_lvm_objects(object_type, fields=fields, tag=tag)
            if not found:
                continue
            for obj in found:
                key = obj.get(primary_field)
                if key is None:
                    continue
                merged.setdefault(key, obj)
        return list(merged.values())

    def __load_filesystem(self):
        # type: () -> FileSystemInfo
        if not self.lv or not self.lv["lv_path"]:
            raise Exception("Logical volume is not loaded")
        return FileSystemInfo(self.lv["lv_path"])

    def __load_mount_point(self):
        # type: () -> MountPointInfo
        if not self.fs or not self.fs["uuid"]:
            raise Exception("Filesystem is not loaded")
        return self.__mount_filesystem(fs=self.fs, mount_path=self.mount_path)

    def __check_pvs(self):
        # type: () -> list[PVInfo] | None
        unhealthy_pvs = []
        if not self.pvs:
            raise Exception("Physical volumes are not loaded")
        for pv in self.pvs:
            if not lvm.check_pv(pv["pv_name"]):
                unhealthy_pvs.append(pv)
        if unhealthy_pvs:
            logger.warning("Unhealthy PVs found for pool %s: %s"
                           % (self.pool_uuid, ','.join([pv["pv_name"] for pv in unhealthy_pvs])))
            return unhealthy_pvs
        return None

    def __check_vg(self):
        # type: () -> VGInfo| None
        if not self.vg:
            raise Exception("Volume group is not loaded")
        if lvm.vgck(self.vg["vg_name"], 5)[0] != 0:
            logger.warning("Unhealthy VG found for pool %s: %s"
                           % (self.pool_uuid, self.vg["vg_name"]))
            return self.vg

        return None

    def __check_lv(self):
        # type: () -> LVInfo | None
        if not self.lv:
            raise Exception("Logical volume is not loaded")
        if lvm.get_lv_attr(self.lv["lv_path"], "lv_active").get("lv_active") != "active":
            logger.warning("Unhealthy LV found for pool %s: %s"
                           % (self.pool_uuid, self.lv["lv_name"]))
            return self.lv
        return None

    def __check_filesystem(self):
        # type: () -> MountPointInfo | None
        if not self.fs:
            raise Exception("Filesystem is not loaded")
        if not self.mount_point:
            raise Exception("Mount point is not loaded")

        if not linux.check_filesystem(self.mount_path, self.heartbeat_file_path):
            logger.warning("Unhealthy filesystem found for pool %s on device %s"
                           % (self.pool_uuid, self.fs.block_device))
            return self.mount_point
        return None

    @rollback
    def init_pool(self, device_paths, force=False):
        # type: (list[str], bool) -> None
        rollback_create_pvs = rollbackable(lambda: self.__remove_pvs(device_paths=device_paths, force=True, is_exception=False))
        rollback_create_vg = rollbackable(lambda: self.__remove_vg(force=True, is_exception=False))
        rollback_create_lv = rollbackable(lambda: self.__remove_lv(force=True, is_exception=False))
        rollback_make_fs = rollbackable(lambda: self.__wipe_filesystem(force=True, is_exception=False))
        rollback_mount_fs = rollbackable(lambda: self.__umount_filesystem(self.mount_path, is_exception=False))

        rollback_create_pvs()
        pvs = self.__create_pvs(device_paths=device_paths,
                                force=force)

        rollback_create_vg()
        vg = self.__create_vg(pvs=pvs)

        rollback_create_lv()
        lv = self.__create_lv(vg=vg)

        rollback_make_fs()
        fs = self.__make_filesystem(lv=lv, force=force)

        rollback_mount_fs()
        self.__mount_filesystem(fs=fs, mount_path=self.mount_path)

        self.connect_pool()


    def connect_pool(self):
        # type: () -> None
        lvm.rescan_lvm()
        try:
            self.pvs = self.__load_pvs()
            self.vg = self.__load_vg()
            self.lv = self.__load_lv()
            self.fs = self.__load_filesystem()
            self.mount_point = self.__load_mount_point()
            if self.__check_filesystem():
                raise PoolOperationError("Filesystem check failed for pool %s on mount path %s" % (
                    self.pool_uuid, self.mount_path))
        except Exception as e:
            logger.error("Failed to connect pool %s on mount path %s: %s" % (
                self.pool_uuid, self.mount_path, str(e)))
            logger.error(traceback.format_exc())
            raise PoolOperationError("Failed to connect pool %s on mount path %s: %s" % (
                self.pool_uuid, self.mount_path, str(e)))

    @ensure_pool_initialized
    @rollback
    def extend_pool(self, additional_device_paths, force=False):
        # type: (list[str], bool) -> None
        assert self.pvs and self.vg and self.lv and self.fs and self.mount_point
        rollback_create_pvs = rollbackable(lambda: self.__remove_pvs(
            device_paths=additional_device_paths, force=True, is_exception=False))
        rollback_create_pvs()
        additional_pvs = self.__create_pvs(device_paths=additional_device_paths,
                                            metadata_size=self.vg_metadata_size,
                                            force=force)

        for pv in additional_pvs:
            lvm.add_pv(self.vg["vg_name"], pv["pv_name"], self.vg_metadata_size)
            for tag in [self.pool_tag, self.mount_path_tag, self.VM_LOCAL_VOLUME_CACHE_POOL_MANAGED_LVM_TAG]:
                lvm.add_pv_tag(pv["pv_name"], tag)
            pv.reload()
        self.vg.reload()
        self.__extend_lv_full_size(self.lv)
        self.__extend_filesystem(self.fs)
        logger.info("Extended VG %s with additional PVs: %s"
                    % (self.vg["vg_name"],
                        ",".join([pv["pv_name"] for pv in additional_pvs])))

    @ensure_pool_initialized
    def delete_pool(self):
        # type: () -> None
        assert self.mount_point and self.pvs
        try:
            self.__umount_filesystem(self.mount_path, is_exception=True)
            self.__wipe_filesystem(force=True, is_exception=True)
            self.__remove_lv(force=True, is_exception=True)
            self.__remove_vg(force=True, is_exception=True)
            self.__remove_pvs([pv["pv_name"] for pv in self.pvs], force=True, is_exception=True)
        except Exception as e:
            logger.error("Failed to delete pool %s: %s" % (self.pool_uuid, str(e)))
            logger.error(traceback.format_exc())
            raise PoolOperationError("Failed to delete pool %s: %s" % (self.pool_uuid, str(e)))

    @ensure_pool_initialized
    def check_pool(self):
        assert self.pvs
        unhealthy_pvs = self.__check_pvs()
        unhealthy_vg = self.__check_vg()
        unhealthy_lv = self.__check_lv()
        unhealthy_filesystem = self.__check_filesystem()
        return PoolHealthInfo(
            pvs={pv:(pv not in unhealthy_pvs) if unhealthy_pvs else True for pv in self.pvs},
            vg=not unhealthy_vg,
            lv=not unhealthy_lv,
            filesystem=not unhealthy_filesystem
        )

    @ensure_pool_initialized
    def get_capacity(self):
        # type: () -> PoolCapacityInfo
        assert self.mount_point
        self.mount_point.reload()
        return get_mount_point_capacity(self.mount_point)

    @ensure_pool_initialized
    def gc_pool(self, volume_uuids):
        # type: (list[str]) -> list[str]
        assert self.mount_point
        mount_path = self.mount_point["target"]

        expected_files = set()
        expected_files.add(os.path.join(mount_path, self.HEARTBEAT_FILE_RELATIVE_PATH))
        for vol_uuid in volume_uuids:
            cache_name = "%s_%s" % (CacheProcessor.CACHE_FILE_NAME_PREFIX, vol_uuid)
            expected_files.add(os.path.join(mount_path, cache_name))

        all_files = list(linux.list_all_file(mount_path))
        unexpected_files = [f for f in all_files if f not in expected_files]

        reserved_dirs = {"lost+found"}
        expected_dir_names = reserved_dirs
        unexpected_dirs = []
        for entry in os.listdir(mount_path):
            entry_path = os.path.join(mount_path, entry)
            if os.path.isdir(entry_path) and entry not in expected_dir_names:
                unexpected_dirs.append(entry_path)

        gc_files = []
        for path in unexpected_files:
            logger.info("GC pool %s: removing unexpected file %s" % (self.pool_uuid, path))
            if self.__remove_gc_path(path):
                gc_files.append(path)
            else:
                logger.warning("GC pool %s: failed to remove file %s" % (self.pool_uuid, path))

        for path in unexpected_dirs:
            logger.info("GC pool %s: removing unexpected directory %s" % (self.pool_uuid, path))
            if self.__remove_gc_path(path):
                gc_files.append(path)
            else:
                logger.warning("GC pool %s: failed to remove directory %s" % (self.pool_uuid, path))

        return gc_files

    @staticmethod
    def __remove_gc_path(path):
        try:
            linux.rm_dir_force(path)
            return True
        except Exception:
            return False

    @ensure_pool_initialized
    def init_cache(self, volume):
        # type: (VolumeTO | jsonobject.JsonObject) -> CacheProcessor
        return CacheProcessor(self, volume)

class CacheProcessor(object):
    CACHE_FILE_NAME_PREFIX = "cache_for_volume"
    BITMAP_NAME = "block-cache"

    __pool = None  # type: PoolProcessor
    __backing_volume = None  # type: BackingVolume

    volume = None # type: VolumeTO | jsonobject.JsonObject

    @property
    def pool(self):
        return self.__pool

    @property
    def backing_volume(self):
        return self.__backing_volume

    @property
    def install_path(self):
        assert self.pool and self.pool.mount_point
        return os.path.join(self.pool.mount_point["target"],
                            "%s_%s" % (self.CACHE_FILE_NAME_PREFIX, self.volume.volumeUuid))

    @property
    def is_instantiated(self):
        return os.path.isfile(self.install_path) and linux.get_img_fmt(self.install_path) == "qcow2"

    def __init__(self, pool_processor, volume, auto_create=True):
        # type: (PoolProcessor, VolumeTO | jsonobject.JsonObject, bool) -> None
        if not pool_processor or not pool_processor.is_initialized:
            raise PoolNotInitializedError("PoolProcessor is not initialized, cannot create CacheProcessor")

        self.__pool = pool_processor
        self.volume = volume

        backing_volume_class = supported_backing_volume_classes.get(
            self.volume.deviceType) # type: type[BackingVolume] | None

        if not backing_volume_class:
            raise UnsupportedDeviceTypeError("Unsupported backing volume device type %s for volume %s"
                            % (self.volume.deviceType, self.volume.volumeUuid))

        self.__backing_volume = backing_volume_class(self.volume)

        if auto_create and (not self.is_instantiated):
            logger.info("Cache file does not exist at path %s, creating new cache file" % self.install_path)
            self.create()

    def __create_cache_file(self, size):
        # type: (int) -> None
        if self.is_instantiated:
            raise CacheOperationError("Cache file already exists at path %s" % self.install_path)
        linux.qcow2_create_with_option(self.install_path, size, opt="-o cluster_size=128k,extended_l2=on")

    def __remove_cache_file(self, is_exception=False):
        # type: (bool) -> None
        if not self.is_instantiated:
            logger.warning("Cache file does not exist at path %s, nothing to remove" % self.install_path)
            return
        try:
            os.remove(self.install_path)
            logger.info("Removed cache file at path %s" % self.install_path)
        except Exception as e:
            logger.error("Failed to remove cache file %s: %s" % (self.install_path, str(e)))
            logger.error(traceback.format_exc())
            if is_exception:
                raise CacheOperationError("Failed to remove cache file %s: %s" % (self.install_path, str(e)))

    def __get_capacity(self):
        # type: () -> tuple[int, int]
        if not self.is_instantiated:
            raise CacheNotInstantiatedError("Cache file is not instantiated at path %s, cannot get capacity" % self.install_path)
        virtual_size, actual_size = linux.qcow2_size_and_actual_size(self.install_path)
        return virtual_size or 0, actual_size

    @rollback
    def create(self):
        # type: () -> None
        if not self.pool or not self.pool.is_initialized or not self.pool.check_pool().is_healthy:
            raise PoolOperationError("PoolProcessor is not healthy, cannot create cache volume")
        rollback_create_cache_file = rollbackable(lambda: self.__remove_cache_file(is_exception=False))
        rollback_create_cache_file()
        assert self.volume.size
        self.__create_cache_file(self.volume.size)

    def delete(self):
        self.__remove_cache_file(is_exception=True)

    def flush(self, shell=None, progress_output=None):
        if not self.is_instantiated:
            raise CacheNotInstantiatedError("Cache file is not instantiated at path %s, cannot flush" % self.install_path)

        bitmap_name = self.BITMAP_NAME
        bitmaps = qemu_img.get_qcow2_bitmaps(self.install_path)

        if list(filter(lambda b: b["name"] == bitmap_name, bitmaps)):
            # Found existing bitmap with the same name, try to flush the bitmap to backing volume
            logger.info("Found existing bitmap with name %s in cache file %s, try to flush bitmap to backing volume %s"
                        % (bitmap_name, self.install_path, self.backing_volume.source_path))
        else:
            # Degraded flush will flush full cache file to backing volume without bitmap optimization
            logger.info("No existing bitmap with name %s found in cache file %s, degraded flush will be performed without bitmap optimization"
                        % (bitmap_name, self.install_path))
            bitmap_name = None

        try:
            output_format = getattr(self.backing_volume.output_format, "value", self.backing_volume.output_format)
            linux.qcow2_convert(self.install_path,
                                self.backing_volume.source_path,
                                dst_format=output_format,
                                shell=shell,
                                progress_output=progress_output,
                                opts="-W -n",
                                bitmap=bitmap_name)
        except Exception as e:
            raise CacheOperationError("Failed to flush cache file %s to backing volume %s: %s"
                                      % (self.install_path, self.backing_volume.source_path, str(e)))

    def get_capacity(self):
        # type: () -> CacheCapacityInfo
        virtual_size, actual_size = self.__get_capacity()
        return CacheCapacityInfo(virtual_size=virtual_size, actual_size=actual_size)

class FlushCacheTaskDaemon(plugin.TaskDaemon):
    def __init__(self, task_spec, cache):
        # type: (object, CacheProcessor) -> None
        super(FlushCacheTaskDaemon, self).__init__(task_spec, "FlushVolumeCache")
        self.task_spec = task_spec
        self.cache = cache
        self.progress = 0
        self.progress_file = linux.create_temp_file()

    def _cancel(self):
        traceable_shell.cancel_job_by_api(self.api_id)
        self.result.fail("cache flush task cancelled")

    def _get_percent(self):
        # type: () -> int
        if self.progress == 100:
            return report.get_exact_percent(100, self.stage)

        p = linux.tail_1(self.progress_file, split=b"\r")
        if not p or "%" not in p:
            return None

        percent = float(p.strip().lstrip("(").split("/")[0])
        return report.get_exact_percent(min(99, percent), self.stage)

    def _get_detail(self):
        # type: () -> jsonobject.JsonObject
        return jsonobject.loads(json.dumps({
            "volumeUuid": self.cache.volume.volumeUuid,
            "cacheInstallPath": self.cache.install_path
        }))

    def _exit(self, exc_type, exc_val, exc_tb):
        linux.rm_file_force(self.progress_file)

    def _raise_if_cancelled(self):
        if not self.result.success:
            raise Exception(self.result.error)

    def flush(self):
        try:
            self.cache.flush(shell=traceable_shell.get_shell(self.task_spec),
                             progress_output=self.progress_file)
        except Exception:
            self._raise_if_cancelled()
            raise
        self._raise_if_cancelled()
        self.progress = 100

T_Cmd = TypeVar("T_Cmd", bound="BaseCmd")
T_Rsp = TypeVar("T_Rsp", bound="VolumeCacheBaseResponse")

def auto_serialize(cmd_type, rsp_type):
    # type: (type[T_Cmd], type[T_Rsp]) -> Callable[[Callable[[VolumeCachePlugin, T_Cmd], T_Rsp]], Callable[[VolumeCachePlugin, dict[str, Any]], str]]
    def decorator(func):
        # type: (Callable[[VolumeCachePlugin, T_Cmd], T_Rsp]) -> Callable[[VolumeCachePlugin, dict[str, Any]], str]
        @functools.wraps(func)
        def wrapper(self, req):
            # type: (VolumeCachePlugin, dict[str, Any]) -> str
            try:
                cmd = cmd_type.from_json(jsonobject.loads(req[http.REQUEST_BODY])) # type: BaseCmd
                rsp_obj = func(self, cmd)
                assert isinstance(rsp_obj, rsp_type), "Response object must be instance of %s" % rsp_type.__name__
                return jsonobject.dumps(rsp_obj)
            except Exception as e:
                logger.error(traceback.format_exc())
                raise e
        return wrapper
    return decorator

def ensure_pool(initialized=False):
    # type: (bool) -> Callable[[Callable[[VolumeCachePlugin, T_Cmd, PoolProcessor], T_Rsp]], Callable[[VolumeCachePlugin, T_Cmd], T_Rsp]]
    def decorator(func):
        # type: (Callable[[VolumeCachePlugin, T_Cmd, PoolProcessor], T_Rsp]) -> Callable[[VolumeCachePlugin, T_Cmd], T_Rsp]
        @functools.wraps(func)
        def wrapper(self, cmd):
            # type: (VolumeCachePlugin, T_Cmd) -> T_Rsp
            pool_processor = self.pool_processors.get(cmd.poolUuid)
            if not pool_processor:
                pool_processor = self._load_pool_on_demand(cmd.poolUuid)
            if initialized and not pool_processor.is_initialized:
                raise PoolNotInitializedError("Pool processor for pool UUID %s is not initialized" % cmd.poolUuid)
            return func(self, cmd, pool_processor)
        return wrapper
    return decorator

class VolumeCachePlugin(kvmagent.KvmAgent):
    pool_processors = None  # type: dict[str, PoolProcessor]

    INIT_POOL_PATH = "/hostcachestore/init"
    CONNECT_POOL_PATH = "/hostcachestore/connect"
    EXTEND_POOL_PATH = "/hostcachestore/extend"
    DELETE_POOL_PATH = "/hostcachestore/delete"
    CHECK_POOL_PATH = "/hostcachestore/check"
    GET_POOL_CAPACITY_PATH = "/hostcachestore/getcapacity"
    GC_POOL_PATH = "/hostcachestore/gc"

    CREATE_CACHE_PATH = "/volumecache/create"
    DELETE_CACHE_PATH = "/volumecache/delete"
    FLUSH_CACHE_PATH = "/volumecache/flush"
    GET_CACHE_CAPACITY_PATH = "/volumecache/getcapacity"

    # Legacy HTTP path aliases (pre-rename). Registered alongside the new
    # routes above so that older management-node builds -- which still target
    # ``/localvolumecache/*`` during rolling upgrades -- keep working. Each
    # alias maps 1:1 to its corresponding new path handler.
    LEGACY_INIT_POOL_PATH = "/localvolumecache/pool/init"
    LEGACY_CONNECT_POOL_PATH = "/localvolumecache/pool/connect"
    LEGACY_EXTEND_POOL_PATH = "/localvolumecache/pool/extend"
    LEGACY_DELETE_POOL_PATH = "/localvolumecache/pool/delete"
    LEGACY_CHECK_POOL_PATH = "/localvolumecache/pool/check"
    LEGACY_GET_POOL_CAPACITY_PATH = "/localvolumecache/pool/getcapacity"
    LEGACY_GC_POOL_PATH = "/localvolumecache/pool/gc"

    LEGACY_CREATE_CACHE_PATH = "/localvolumecache/create"
    LEGACY_DELETE_CACHE_PATH = "/localvolumecache/delete"
    LEGACY_FLUSH_CACHE_PATH = "/localvolumecache/flush"
    LEGACY_GET_CACHE_CAPACITY_PATH = "/localvolumecache/getcapacity"

    def __init__(self):
        super(VolumeCachePlugin, self).__init__()
        self.pool_processors = {}

    def _load_pool_on_demand(self, pool_uuid):
        # type: (str) -> PoolProcessor
        pool = self.pool_processors.get(pool_uuid)
        if pool:
            return pool

        pool = PoolProcessor.discover_local_pool(pool_uuid)
        if not pool:
            raise PoolNotFoundError("No local volume cache pool found for pool UUID %s" % pool_uuid)

        pool.connect_pool()
        self.pool_processors[pool_uuid] = pool
        logger.info("Connected local volume cache pool %s on mount path %s" % (
            pool.pool_uuid, pool.mount_path))
        return pool

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.INIT_POOL_PATH, self.init_pool)
        http_server.register_async_uri(self.CONNECT_POOL_PATH, self.connect_pool)
        http_server.register_async_uri(self.EXTEND_POOL_PATH, self.extend_pool)
        http_server.register_async_uri(self.DELETE_POOL_PATH, self.delete_pool)
        http_server.register_async_uri(self.CHECK_POOL_PATH, self.check_pool)
        http_server.register_async_uri(self.GET_POOL_CAPACITY_PATH, self.get_pool_capacity)
        http_server.register_async_uri(self.GC_POOL_PATH, self.gc_pool)

        http_server.register_async_uri(self.CREATE_CACHE_PATH, self.create_cache)
        http_server.register_async_uri(self.DELETE_CACHE_PATH, self.delete_cache)
        http_server.register_async_uri(self.FLUSH_CACHE_PATH, self.flush_cache)
        http_server.register_async_uri(self.GET_CACHE_CAPACITY_PATH, self.get_cache_capacity)

        # Register legacy ``/localvolumecache/*`` aliases so that rolling
        # upgrades -- where the management node may still be on an older
        # release that targets the pre-rename URLs -- continue to reach the
        # same handlers.
        http_server.register_async_uri(self.LEGACY_INIT_POOL_PATH, self.init_pool)
        http_server.register_async_uri(self.LEGACY_CONNECT_POOL_PATH, self.connect_pool)
        http_server.register_async_uri(self.LEGACY_EXTEND_POOL_PATH, self.extend_pool)
        http_server.register_async_uri(self.LEGACY_DELETE_POOL_PATH, self.delete_pool)
        http_server.register_async_uri(self.LEGACY_CHECK_POOL_PATH, self.check_pool)
        http_server.register_async_uri(self.LEGACY_GET_POOL_CAPACITY_PATH, self.get_pool_capacity)
        http_server.register_async_uri(self.LEGACY_GC_POOL_PATH, self.gc_pool)

        http_server.register_async_uri(self.LEGACY_CREATE_CACHE_PATH, self.create_cache)
        http_server.register_async_uri(self.LEGACY_DELETE_CACHE_PATH, self.delete_cache)
        http_server.register_async_uri(self.LEGACY_FLUSH_CACHE_PATH, self.flush_cache)
        http_server.register_async_uri(self.LEGACY_GET_CACHE_CAPACITY_PATH, self.get_cache_capacity)

    def stop(self):
        pass

    def _to_pool_rsp(self, pool):
        # type: (PoolProcessor) -> PoolRsp
        rsp = PoolRsp()
        self._fill_pool_rsp(rsp, pool)
        return rsp

    def _fill_pool_rsp(self, rsp, pool):
        # type: (PoolRsp, PoolProcessor) -> None
        self._fill_pool_identity(rsp, pool)
        try:
            self._fill_pool_capacity(rsp, pool.get_capacity())
        except Exception as e:
            logger.warning("Failed to read capacity for pool %s: %s" % (pool.pool_uuid, str(e)))

    def _fill_pool_identity(self, rsp, pool):
        # type: (PoolRsp, PoolProcessor) -> None
        assert pool.mount_point
        rsp.poolUuid = pool.pool_uuid
        rsp.mountPoint = pool.mount_point["target"]

    def _fill_pool_capacity(self, rsp, capacity):
        # type: (PoolRsp, PoolCapacityInfo) -> None
        rsp.totalCapacity = capacity.total
        rsp.availableCapacity = capacity.available
        rsp.totalPhysicalCapacity = capacity.total_physical
        rsp.availablePhysicalCapacity = capacity.available_physical
        rsp.systemUsedCapacity = capacity.system_used

    def _to_pool_health_rsp(self, pool, pool_health_info):
        # type: (PoolProcessor, PoolHealthInfo) -> PoolHealthRsp
        rsp = PoolHealthRsp()
        self._fill_pool_identity(rsp, pool)
        rsp.healthy = pool_health_info.is_healthy
        if not pool_health_info.is_healthy:
            # aggregate failure reason: first unhealthy layer wins
            reasons = []
            unhealthy_pvs = [pv["pv_name"] for pv, healthy in pool_health_info.pvs.items() if not healthy]
            if unhealthy_pvs:
                reasons.append("unhealthy pvs: %s" % ",".join(unhealthy_pvs))
            if pool_health_info.vg is False:
                reasons.append("vg unhealthy")
            if pool_health_info.lv is False:
                reasons.append("lv unhealthy")
            if pool_health_info.filesystem is False:
                reasons.append("filesystem unhealthy")
            rsp.reason = "; ".join(reasons) if reasons else "unhealthy"
        return rsp

    def _to_pool_capacity_rsp(self, pool, capacity):
        # type: (PoolProcessor, PoolCapacityInfo) -> PoolCapacityRsp
        rsp = PoolCapacityRsp()
        self._fill_pool_identity(rsp, pool)
        self._fill_pool_capacity(rsp, capacity)
        return rsp

    def _to_cache_rsp(self, cache):
        # type: (CacheProcessor) -> CacheRsp
        rsp = CacheRsp()
        self._fill_pool_rsp(rsp, cache.pool)
        rsp.installPath = cache.install_path
        capacity = cache.get_capacity()
        rsp.virtualSize = capacity.virtual_size
        rsp.actualSize = capacity.actual_size
        return rsp

    def _to_delete_cache_rsp(self, pool):
        # type: (PoolProcessor) -> DeleteCacheRsp
        rsp = DeleteCacheRsp()
        self._fill_pool_rsp(rsp, pool)
        return rsp

    @kvmagent.replyerror
    @auto_serialize(InitPoolCmd, InitPoolRsp)
    @rollback
    def init_pool(self, cmd):
        # type: (InitPoolCmd) -> InitPoolRsp
        added_devices = lvm.append_lvm_filter_devices(cmd.devices)
        rollback_remove_filter = rollbackable(
            lambda: _remove_lvm_filter_devices_best_effort(added_devices, cmd.poolUuid))
        rollback_remove_filter()

        pool = self.pool_processors.get(cmd.poolUuid)
        if pool:
            if pool.is_initialized:
                return self._to_pool_rsp(pool)
            pool.connect_pool()
            return self._to_pool_rsp(pool)

        pool = PoolProcessor(cmd.poolUuid, cmd.mountPoint)
        pool.init_pool(
            device_paths=cmd.devices,
            force=bool(cmd.force)
        )
        self.pool_processors[cmd.poolUuid] = pool
        return self._to_pool_rsp(pool)

    @kvmagent.replyerror
    @auto_serialize(ConnectPoolCmd, ConnectPoolRsp)
    def connect_pool(self, cmd):
        # type: (ConnectPoolCmd) -> ConnectPoolRsp
        pool = self.pool_processors.get(cmd.poolUuid)
        if pool:
            pool.connect_pool()
        else:
            pool = self._load_pool_on_demand(cmd.poolUuid)
        return self._to_pool_rsp(pool)

    @kvmagent.replyerror
    @auto_serialize(ExtendPoolCmd, ExtendPoolRsp)
    @ensure_pool(initialized=True)
    @rollback
    def extend_pool(self, cmd, pool):
        # type: (ExtendPoolCmd, PoolProcessor) -> ExtendPoolRsp
        added_devices = lvm.append_lvm_filter_devices(cmd.devices)
        rollback_remove_filter = rollbackable(
            lambda: _remove_lvm_filter_devices_best_effort(added_devices, cmd.poolUuid))
        rollback_remove_filter()

        pool.extend_pool(additional_device_paths=cmd.devices, force=bool(cmd.force))
        pool.connect_pool()

        return self._to_pool_rsp(pool)

    @kvmagent.replyerror
    @auto_serialize(DeletePoolCmd, DeletePoolRsp)
    @ensure_pool(initialized=True)
    def delete_pool(self, cmd, pool):
        # type: (DeletePoolCmd, PoolProcessor) -> DeletePoolRsp
        devices = [pv["pv_name"] for pv in pool.pvs]
        pool.delete_pool()
        _remove_lvm_filter_devices_best_effort(devices, cmd.poolUuid)
        self.pool_processors.pop(cmd.poolUuid, None)
        return DeletePoolRsp()

    @kvmagent.replyerror
    @auto_serialize(CheckPoolCmd, PoolHealthRsp)
    @ensure_pool(initialized=True)
    def check_pool(self, cmd, pool):
        # type: (CheckPoolCmd, PoolProcessor) -> PoolHealthRsp
        pool_health = pool.check_pool()
        return self._to_pool_health_rsp(pool, pool_health)

    @kvmagent.replyerror
    @auto_serialize(GetPoolCapacityCmd, PoolCapacityRsp)
    @ensure_pool(initialized=True)
    def get_pool_capacity(self, cmd, pool):
        # type: (GetPoolCapacityCmd, PoolProcessor) -> PoolCapacityRsp
        capacity = pool.get_capacity()
        return self._to_pool_capacity_rsp(pool, capacity)

    @kvmagent.replyerror
    @auto_serialize(AllocateCacheCmd, CacheRsp)
    @ensure_pool(initialized=True)
    def create_cache(self, cmd, pool):
        # type: (AllocateCacheCmd, PoolProcessor) -> CacheRsp

        cache = pool.init_cache(volume=cmd.volume)
        return self._to_cache_rsp(cache)

    @kvmagent.replyerror
    @auto_serialize(DeleteCacheCmd, DeleteCacheRsp)
    @ensure_pool(initialized=True)
    def delete_cache(self, cmd, pool):
        # type: (DeleteCacheCmd, PoolProcessor) -> DeleteCacheRsp
        cache = pool.init_cache(volume=cmd.volume)
        cache.delete()
        return self._to_delete_cache_rsp(pool)

    @kvmagent.replyerror
    @auto_serialize(FlushCacheCmd, CacheRsp)
    @ensure_pool(initialized=True)
    def flush_cache(self, cmd, pool):
        # type: (FlushCacheCmd, PoolProcessor) -> CacheRsp
        cache = pool.init_cache(volume=cmd.volume)
        with FlushCacheTaskDaemon(cmd, cache) as daemon:
            daemon.flush()

        return self._to_cache_rsp(cache)

    @kvmagent.replyerror
    @auto_serialize(GcPoolCmd, GcPoolRsp)
    @ensure_pool(initialized=True)
    def gc_pool(self, cmd, pool):
        # type: (GcPoolCmd, PoolProcessor) -> GcPoolRsp
        volume_uuids = cmd.inUseCacheUuids if cmd.inUseCacheUuids else []
        gc_files = pool.gc_pool(volume_uuids)

        rsp = GcPoolRsp()
        self._fill_pool_rsp(rsp, pool)
        rsp.gcFiles = gc_files
        rsp.gcCount = len(gc_files)
        return rsp

    @kvmagent.replyerror
    @auto_serialize(GetCacheCapacityCmd, CacheRsp)
    @ensure_pool(initialized=True)
    def get_cache_capacity(self, cmd, pool):
        # type: (GetCacheCapacityCmd, PoolProcessor) -> CacheRsp
        cache = CacheProcessor(pool, cmd.volume, auto_create=False)
        return self._to_cache_rsp(cache)
