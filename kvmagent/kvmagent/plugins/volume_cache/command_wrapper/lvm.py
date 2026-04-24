from enum import Enum
import json

from zstacklib.utils import lvm, shell


class LvmObjectType(Enum):
    PV = "physical_volume"
    VG = "volume_group"
    LV = "logical_volume"

class LVType(Enum):
    LINEAR = "linear"
    STRIPED = "striped"
    RAID0 = "raid0"


class PVInfoFields(Enum):
    # Physical Volume Label Fields
    PV_FMT = "pv_fmt"
    PV_UUID = "pv_uuid"
    DEV_SIZE = "dev_size"
    PV_NAME = "pv_name"
    PV_MAJOR = "pv_major"
    PV_MINOR = "pv_minor"
    PV_MDA_FREE = "pv_mda_free"
    PV_MDA_SIZE = "pv_mda_size"
    PV_EXT_VSN = "pv_ext_vsn"

    # Physical Volume Fields
    PE_START = "pe_start"
    PV_SIZE = "pv_size"
    PV_FREE = "pv_free"
    PV_USED = "pv_used"
    PV_ATTR = "pv_attr"
    PV_ALLOCATABLE = "pv_allocatable"
    PV_EXPORTED = "pv_exported"
    PV_MISSING = "pv_missing"
    PV_PE_COUNT = "pv_pe_count"
    PV_PE_ALLOC_COUNT = "pv_pe_alloc_count"
    PV_TAGS = "pv_tags"
    PV_MDA_COUNT = "pv_mda_count"
    PV_MDA_USED_COUNT = "pv_mda_used_count"
    PV_BA_START = "pv_ba_start"
    PV_BA_SIZE = "pv_ba_size"
    PV_IN_USE = "pv_in_use"
    PV_DUPLICATE = "pv_duplicate"
    PV_DEVICE_ID = "pv_device_id"
    PV_DEVICE_ID_TYPE = "pv_device_id_type"

    #  Physical Volume Segment Fields
    PVSEG_START = "pvseg_start"
    PVSEG_SIZE = "pvseg_size"

class VGInfoFields(Enum):
    VG_FMT = "vg_fmt"
    VG_UUID = "vg_uuid"
    VG_NAME = "vg_name"
    VG_ATTR = "vg_attr"
    VG_PERMISSIONS = "vg_permissions"
    VG_EXTENDABLE = "vg_extendable"
    VG_EXPORTED = "vg_exported"
    VG_AUTOACTIVATION = "vg_autoactivation"
    VG_PARTIAL = "vg_partial"
    VG_ALLOCATION_POLICY = "vg_allocation_policy"
    VG_CLUSTERED = "vg_clustered"
    VG_SHARED = "vg_shared"
    VG_SIZE = "vg_size"
    VG_FREE = "vg_free"
    VG_SYSID = "vg_sysid"
    VG_SYSTEMID = "vg_systemid"
    VG_LOCK_TYPE = "vg_lock_type"
    VG_LOCK_ARGS = "vg_lock_args"
    VG_EXTENT_SIZE = "vg_extent_size"
    VG_EXTENT_COUNT = "vg_extent_count"
    VG_FREE_COUNT = "vg_free_count"
    VG_MAX_LV = "max_lv"
    VG_MAX_PV = "max_pv"
    VG_PV_COUNT = "pv_count"
    VG_MISSING_PV_COUNT = "vg_missing_pv_count"
    VG_LV_COUNT = "lv_count"
    VG_SNAP_COUNT = "snap_count"
    VG_SEQNO = "vg_seqno"
    VG_TAGS = "vg_tags"
    VG_PROFILE = "vg_profile"
    VG_MDA_COUNT = "vg_mda_count"
    VG_MDA_USED_COUNT = "vg_mda_used_count"
    VG_MDA_FREE = "vg_mda_free"
    VG_MDA_SIZE = "vg_mda_size"
    VG_MDA_COPIES = "vg_mda_copies"

class LVInfoFields(Enum):
    # Logical Volume Fields
    LV_UUID = "lv_uuid"
    LV_NAME = "lv_name"
    LV_FULL_NAME = "lv_full_name"
    LV_PATH = "lv_path"
    LV_DM_PATH = "lv_dm_path"
    LV_PARENT = "lv_parent"
    LV_LAYOUT = "lv_layout"
    LV_ROLE = "lv_role"
    LV_INITIAL_IMAGE_SYNC = "lv_initial_image_sync"
    LV_IMAGE_SYNCED = "lv_image_synced"
    LV_MERGING = "lv_merging"
    LV_CONVERTING = "lv_converting"
    LV_ALLOCATION_POLICY = "lv_allocation_policy"
    LV_ALLOCATION_LOCKED = "lv_allocation_locked"
    LV_FIXED_MINOR = "lv_fixed_minor"
    LV_SKIP_ACTIVATION = "lv_skip_activation"
    LV_AUTOACTIVATION = "lv_autoactivation"
    LV_WHEN_FULL = "lv_when_full"
    LV_ACTIVE = "lv_active"
    LV_ACTIVE_LOCALLY = "lv_active_locally"
    LV_ACTIVE_REMOTELY = "lv_active_remotely"
    LV_ACTIVE_EXCLUSIVELY = "lv_active_exclusively"
    LV_MAJOR = "lv_major"
    LV_MINOR = "lv_minor"
    LV_READ_AHEAD = "lv_read_ahead"
    LV_SIZE = "lv_size"
    LV_METADATA_SIZE = "lv_metadata_size"
    SEG_COUNT = "seg_count"
    ORIGIN = "origin"
    ORIGIN_UUID = "origin_uuid"
    ORIGIN_SIZE = "origin_size"
    LV_ANCESTORS = "lv_ancestors"
    LV_FULL_ANCESTORS = "lv_full_ancestors"
    LV_DESCENDANTS = "lv_descendants"
    LV_FULL_DESCENDANTS = "lv_full_descendants"
    RAID_MISMATCH_COUNT = "raid_mismatch_count"
    RAID_SYNC_ACTION = "raid_sync_action"
    RAID_WRITE_BEHIND = "raid_write_behind"
    RAID_MIN_RECOVERY_RATE = "raid_min_recovery_rate"
    RAID_MAX_RECOVERY_RATE = "raid_max_recovery_rate"
    RAIDINTEGRITYMODE = "raidintegritymode"
    RAIDINTEGRITYBLOCKSIZE = "raidintegrityblocksize"
    INTEGRITYMISMATCHES = "integritymismatches"
    MOVE_PV = "move_pv"
    MOVE_PV_UUID = "move_pv_uuid"
    CONVERT_LV = "convert_lv"
    CONVERT_LV_UUID = "convert_lv_uuid"
    MIRROR_LOG = "mirror_log"
    MIRROR_LOG_UUID = "mirror_log_uuid"
    DATA_LV = "data_lv"
    DATA_LV_UUID = "data_lv_uuid"
    METADATA_LV = "metadata_lv"
    METADATA_LV_UUID = "metadata_lv_uuid"
    POOL_LV = "pool_lv"
    POOL_LV_UUID = "pool_lv_uuid"
    LV_TAGS = "lv_tags"
    LV_PROFILE = "lv_profile"
    LV_LOCKARGS = "lv_lockargs"
    LV_TIME = "lv_time"
    LV_TIME_REMOVED = "lv_time_removed"
    LV_HOST = "lv_host"
    LV_MODULES = "lv_modules"
    LV_HISTORICAL = "lv_historical"
   
    # Logical Volume Device Info Fields
    LV_KERNEL_MAJOR = "lv_kernel_major"
    LV_KERNEL_MINOR = "lv_kernel_minor"
    LV_KERNEL_READ_AHEAD = "lv_kernel_read_ahead"
    LV_PERMISSIONS = "lv_permissions"
    LV_SUSPENDED = "lv_suspended"
    LV_LIVE_TABLE = "lv_live_table"
    LV_INACTIVE_TABLE = "lv_inactive_table"
    LV_DEVICE_OPEN = "lv_device_open"

    # Logical Volume Device Status Fields
    DATA_PERCENT = "data_percent"
    SNAP_PERCENT = "snap_percent"
    METADATA_PERCENT = "metadata_percent"
    COPY_PERCENT = "copy_percent"
    SYNC_PERCENT = "sync_percent"
    CACHE_TOTAL_BLOCKS = "cache_total_blocks"
    CACHE_USED_BLOCKS = "cache_used_blocks"
    CACHE_DIRTY_BLOCKS = "cache_dirty_blocks"
    CACHE_READ_HITS = "cache_read_hits"
    CACHE_READ_MISSES = "cache_read_misses"
    CACHE_WRITE_HITS = "cache_write_hits"
    CACHE_WRITE_MISSES = "cache_write_misses"
    KERNEL_CACHE_SETTINGS = "kernel_cache_settings"
    KERNEL_CACHE_POLICY = "kernel_cache_policy"
    KERNEL_METADATA_FORMAT = "kernel_metadata_format"
    LV_HEALTH_STATUS = "lv_health_status"
    LV_KERNEL_DISCARDS = "kernel_discards"
    LV_CHECK_NEEDED = "lv_check_needed"
    LV_MERGE_FAILED = "lv_merge_failed"
    LV_SNAPSHOT_INVALID = "lv_snapshot_invalid"
    VDO_OPERATING_MODE = "vdo_operating_mode"
    VDO_COMPRESSION_STATE = "vdo_compression_state"
    VDO_INDEX_STATE = "vdo_index_state"
    VDO_USED_SIZE = "vdo_used_size"
    VDO_SAVING_PERCENT = "vdo_saving_percent"
    WRITECACHE_TOTAL_BLOCKS = "writecache_total_blocks"
    WRITECACHE_FREE_BLOCKS = "writecache_free_blocks"
    WRITECACHE_WRITEBACK_BLOCKS = "writecache_writeback_blocks"
    WRITECACHE_ERROR = "writecache_error"
    LV_ATTR = "lv_attr"

    # Logical Volume Segment Fields
    SEGTYPE = "segtype"
    STRIPES = "stripes"
    DATA_STRIPES = "data_stripes"
    RESHAPE_LEN = "reshape_len"
    RESHAPE_LEN_LE = "reshape_len_le"
    DATA_COPIES = "data_copies"
    DATA_OFFSET = "data_offset"
    NEW_DATA_OFFSET = "new_data_offset"
    PARITY_CHUNKS = "parity_chunks"
    STRIPE_SIZE = "stripe_size"
    REGION_SIZE = "region_size"
    CHUNK_SIZE = "chunk_size"
    THIN_COUNT = "thin_count"
    DISCARDS = "discards"
    CACHE_METADATA_FORMAT = "cache_metadata_format"
    CACHE_MODE = "cache_mode"
    ZERO = "zero"
    TRANSACTION_ID = "transaction_id"
    THIN_ID = "thin_id"
    SEG_START = "seg_start"
    SEG_START_PE = "seg_start_pe"
    SEG_SIZE = "seg_size"
    SEG_SIZE_PE = "seg_size_pe"
    SEG_TAGS = "seg_tags"
    SEG_PE_RANGES = "seg_pe_ranges"
    SEG_LE_RANGES = "seg_le_ranges"
    SEG_METADATA_LE_RANGES = "seg_metadata_le_ranges"
    DEVICES = "devices"
    METADATA_DEVICES = "metadata_devices"
    SEG_MONITOR = "seg_monitor"
    CACHE_POLICY = "cache_policy"
    CACHE_SETTINGS = "cache_settings"
    VDO_COMPRESSION = "vdo_compression"
    VDO_DEDUPLICATION = "vdo_deduplication"
    VDO_USE_METADATA_HINTS = "vdo_use_metadata_hints"
    VDO_MINIMUM_IO_SIZE = "vdo_minimum_io_size"
    VDO_BLOCK_MAP_CACHE_SIZE = "vdo_block_map_cache_size"
    VDO_BLOCK_MAP_ERA_LENGTH = "vdo_block_map_era_length"
    VDO_USE_SPARSE_INDEX = "vdo_use_sparse_index"
    VDO_INDEX_MEMORY_SIZE = "vdo_index_memory_size"
    VDO_SLAB_SIZE = "vdo_slab_size"
    VDO_ACK_THREADS = "vdo_ack_threads"
    VDO_BIO_THREADS = "vdo_bio_threads"
    VDO_BIO_ROTATION = "vdo_bio_rotation"
    VDO_CPU_THREADS = "vdo_cpu_threads"
    VDO_HASH_ZONE_THREADS = "vdo_hash_zone_threads"
    VDO_LOGICAL_THREADS = "vdo_logical_threads"
    VDO_PHYSICAL_THREADS = "vdo_physical_threads"
    VDO_MAX_DISCARD = "vdo_max_discard"
    VDO_WRITE_POLICY = "vdo_write_policy"
    VDO_HEADER_SIZE = "vdo_header_size"

class LvmCommandWrapper:
    """Wrapper for LVM commands"""

    @staticmethod
    def parse_lvm_output(raw_json):
        # type: (str) -> list[dict[str, str]] | None
        if not raw_json.strip():
            return None
        output_json = json.loads(raw_json.strip()) # type: dict[str, list[dict[str, list[dict[str, str]]]]]
        reports = output_json.get("report") # type: list[dict[str, list[dict[str, str]]]] | None
        if not reports or len(reports) == 0:
            return None
        objects = reports.pop().popitem()[1] # type: list[dict[str, str]]
        if not objects:
            return None
        return objects

    @staticmethod
    def get_lvm_object_by_uuid(object_type, object_uuid, fields=None):
        # type: (LvmObjectType, str, list[PVInfoFields|VGInfoFields|LVInfoFields]|None) -> dict[str, str] | None

        if fields is None:
            _fields = ["all"]
        else:
            _fields = [field.value for field in fields]

        if object_type == LvmObjectType.PV:
            subcmd = lvm.subcmd("pvs")
        elif object_type == LvmObjectType.VG:
            subcmd = lvm.subcmd("vgs")
        elif object_type == LvmObjectType.LV:
            subcmd = lvm.subcmd("lvs")
        else:
            raise Exception("Unsupported LVM object type: %s" % object_type)

        cmd = shell.ShellCmd("%s --select uuid=%s --units B --options %s --reportformat json" % (subcmd, object_uuid, ','.join(_fields)))
        cmd(is_exception=False)
        objects = LvmCommandWrapper.parse_lvm_output(cmd.stdout)
        if not objects:
            return None
        return objects.pop()

    @staticmethod
    def get_lvm_object_by_name(object_type, object_name, fields=None):
        # type: (LvmObjectType, str, list[PVInfoFields|VGInfoFields|LVInfoFields]|None) -> dict[str, str] | None

        if fields is None:
            _fields = ["all"]
        else:
            _fields = [field.value for field in fields]

        if object_type == LvmObjectType.PV:
            subcmd = lvm.subcmd("pvs")
        elif object_type == LvmObjectType.VG:
            subcmd = lvm.subcmd("vgs")
        elif object_type == LvmObjectType.LV:
            subcmd = lvm.subcmd("lvs")
        else:
            raise Exception("Unsupported LVM object type: %s" % object_type)

        cmd = shell.ShellCmd("%s --units B --options %s --reportformat json %s" % (subcmd, ','.join(_fields), object_name))
        cmd(is_exception=False)
        objects = LvmCommandWrapper.parse_lvm_output(cmd.stdout)
        if not objects:
            return None
        return objects.pop()

    @staticmethod
    def get_lvm_objects_by_tag(object_type, tag, fields=None):
        # type: (LvmObjectType, str, list[PVInfoFields|VGInfoFields|LVInfoFields]|None) -> list[dict[str, str]]|None

        if fields is None:
            _fields = ["all"]
        else:
            _fields = [field.value for field in fields]

        if object_type == LvmObjectType.PV:
            subcmd = lvm.subcmd("pvs")
        elif object_type == LvmObjectType.VG:
            subcmd = lvm.subcmd("vgs")
        elif object_type == LvmObjectType.LV:
            subcmd = lvm.subcmd("lvs")
        else:
            raise Exception("Unsupported LVM object type: %s" % object_type)

        cmd = shell.ShellCmd("%s --select 'tags=%s' --units B --options %s --reportformat json" % (subcmd, tag, ','.join(_fields)))
        cmd(is_exception=False)
        objects = LvmCommandWrapper.parse_lvm_output(cmd.stdout)
        return objects

    @staticmethod
    def tag_lvm_object(object_type, object_name, tags):
        # type: (LvmObjectType, str, list[str]) -> None
        if object_type == LvmObjectType.PV:
            subcmd = lvm.subcmd("pvchange")
        elif object_type == LvmObjectType.VG:
            subcmd = lvm.subcmd("vgchange")
        elif object_type == LvmObjectType.LV:
            subcmd = lvm.subcmd("lvchange")
        else:
            raise Exception("Unsupported LVM object type: %s" % object_type)
        for tag in tags:
            args = ["-qq", "--addtag", tag, object_name]
            cmd = shell.ShellCmd("%s %s" % (subcmd, ' '.join(args)))
            cmd(is_exception=True)

    @staticmethod
    def create_pv(device_path, metadata_size=None, force=True):
        # type: (str, str|None, bool) -> str
        args = ["-qq", "--yes"]
        if metadata_size is not None:
            args.extend(["--metadatasize", metadata_size])
        if force:
            args.append("--force")
        args.append(device_path)

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("pvcreate"), ' '.join(args)))
        cmd(is_exception=True)
        pv_created = LvmCommandWrapper.get_lvm_object_by_name(LvmObjectType.PV, device_path, [PVInfoFields.PV_UUID])
        if pv_created is None:
            raise Exception("Failed to create PV on device %s" % device_path)
        return pv_created.get(PVInfoFields.PV_UUID.value) # type: ignore

    @staticmethod
    def remove_pv(pv_name, force=True):
        # type: (str, bool) -> None
        args = ["-qq", "--yes"]
        if force:
            args.append("--force")
        args.append(pv_name)

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("pvremove"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def rescan_pv(pv_name=None):
        args = ["--cache", "-qq", "--yes"]
        if pv_name:
            args.append(pv_name)
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("pvscan"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def check_pv(pv_name):
        # type: (str) -> bool
        args = ["-qq", "--yes", pv_name]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("pvck", timeout=5), ' '.join(args)))
        cmd(is_exception=False)
        if cmd.return_code != 0:
            return False
        return True

    @staticmethod
    def create_vg(vg_name, pv_names, tags=None, metadata_size=None):
        # type: (str, list[str], list[str]|None, str|None) -> str
        args = ["-qq", "--yes"]
        if metadata_size is not None:
            args.extend(["--metadatasize", metadata_size])
        args.append(vg_name)
        args.extend(pv_names)

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("vgcreate"), ' '.join(args)))
        cmd(is_exception=True)
        vg_created = LvmCommandWrapper.get_lvm_object_by_name(LvmObjectType.VG, vg_name, [VGInfoFields.VG_UUID])
        if vg_created is None:
            raise Exception("Failed to create VG %s on PVs %s" % (vg_name, ','.join(pv_names)))
        if tags:
            LvmCommandWrapper.tag_lvm_object(LvmObjectType.VG, vg_name, tags)
        return vg_created.get(VGInfoFields.VG_UUID.value) # type: ignore
    
    @staticmethod
    def extend_vg(vg_name, pv_names, metadata_size=None):
        # type: (str, list[str], str|None) -> None
        _metadata_size = metadata_size
        for pv_name in pv_names:
            if not metadata_size:
                _metadata_size = LvmCommandWrapper.get_lvm_object_by_name(
                    LvmObjectType.PV, pv_name, [PVInfoFields.PV_MDA_SIZE]).get(
                        PVInfoFields.PV_MDA_SIZE.value)
            lvm.add_pv(vg_name, pv_name, _metadata_size)

    @staticmethod
    def remove_vg(vg_name, force=True):
        # type: (str, bool) -> None
        args = ["-qq", "--yes"]
        if force:
            args.append("--force")
        args.append(vg_name)

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("vgremove"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def rescan_vg():
        args = ["-qq", "--yes", "--ignorelockingfailure"]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("vgscan"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def check_vg(vg_name):
        # type: (str) -> bool
        args = ["-qq", "--yes", vg_name]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("vgck", timeout=5), ' '.join(args)))
        cmd(is_exception=False)
        if cmd.return_code != 0:
            return False
        return True

    @staticmethod
    def create_lv(lv_name, vg_name, type=None, stripes=None, stripesize=None, size=None, extents=None, tags=None):
        # type: (str, str, LVType|None, str|None, str|None, str|None, str|None, list[str]|None) -> str
        args = ["-qq", "--wipesignatures", "y", "--yes", "--activate", "y"]
        if not size and not extents:
            raise Exception("Either size or extents must be specified when creating LV")
        if type:
            args.extend(["--type", type.value])
        if stripes:
            args.extend(["--stripes", stripes])
        if stripesize:
            args.extend(["--stripesize", stripesize])
        if size:
            args.extend(["--size", size])
        if extents:
            args.extend(["--extents", extents])

        args.extend(["--name", lv_name])
        args.append(vg_name)

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvcreate"), ' '.join(args)))
        cmd(is_exception=True)

        lv_created = LvmCommandWrapper.get_lvm_object_by_name(LvmObjectType.LV, "%s/%s" % (vg_name, lv_name), [LVInfoFields.LV_UUID])
        if lv_created is None:
            raise Exception("Failed to create LV %s on VG %s" % (lv_name, vg_name))
        if tags:
            LvmCommandWrapper.tag_lvm_object(LvmObjectType.LV, "%s/%s" % (vg_name, lv_name), tags)

        return lv_created.get(LVInfoFields.LV_UUID.value) # type: ignore

    @staticmethod
    def active_lv(lv_name, vg_name):
        args = ["-qq", "--yes", "--activate", "y", "%s/%s" % (vg_name, lv_name)]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvchange"), ' '.join(args)))
        cmd(is_exception=True)
    
    @staticmethod
    def deactive_lv(lv_name, vg_name):
        args = ["-qq", "--yes", "--activate", "n", "%s/%s" % (vg_name, lv_name)]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvchange"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def check_lv(lv_name, vg_name):
        # type: (str, str) -> bool
        lv = LvmCommandWrapper.get_lvm_object_by_name(LvmObjectType.LV, "%s/%s" % (vg_name, lv_name), [LVInfoFields.LV_ACTIVE]) # check if LV exists
        if not lv:
            return False
        is_active = lv.get(LVInfoFields.LV_ACTIVE.value, "")
        if is_active != "active":
            return False
        return True

    @staticmethod
    def extend_lv(lv_name, vg_name, size=None, extents=None):
        # type: (str, str, str|None, str|None) -> None
        args = ["-qq", "--yes"]
        if not size and not extents:
            raise Exception("Either size or extents must be specified when extending LV")
        if size:
            args.extend(["--size", size])
        if extents:
            args.extend(["--extents", extents])
        args.append("%s/%s" % (vg_name, lv_name))

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvextend"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def remove_lv(lv_name, vg_name, force=True):
        # type: (str, str, bool) -> None
        args = ["-qq", "--yes"]
        if force:
            args.append("--force")
        args.append("%s/%s" % (vg_name, lv_name))

        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvremove"), ' '.join(args)))
        cmd(is_exception=True)

    @staticmethod
    def rescan_lv():
        args = ["-qq", "--yes", "--ignorelockingfailure", "--all"]
        cmd = shell.ShellCmd("%s %s" % (lvm.subcmd("lvscan"), ' '.join(args)))
        cmd(is_exception=True)

