"""Tests for storage.lvm module."""

import pytest

from zstacklib.storage.lvm.models import (
    VolumeProvisioningStrategy,
    LvmLockType,
    LvmError,
    VgNotFoundError,
    LvNotFoundError,
    PvNotFoundError,
    LvmLockError,
    PhysicalVolume,
    VolumeGroup,
    LogicalVolume,
    ThinPool,
    BlockDevice,
)


class TestVolumeProvisioningStrategy:
    def test_strategy_values(self):
        assert VolumeProvisioningStrategy.THIN.value == "ThinProvisioning"
        assert VolumeProvisioningStrategy.THICK.value == "ThickProvisioning"

    def test_strategy_is_string_enum(self):
        assert isinstance(VolumeProvisioningStrategy.THIN, str)
        assert VolumeProvisioningStrategy.THIN == "ThinProvisioning"


class TestLvmLockType:
    def test_lock_type_values(self):
        assert LvmLockType.NULL.value == 0
        assert LvmLockType.SHARE.value == 1
        assert LvmLockType.EXCLUSIVE.value == 2

    def test_from_abbr_share(self):
        assert LvmLockType.from_abbr("sh") == LvmLockType.SHARE

    def test_from_abbr_exclusive(self):
        assert LvmLockType.from_abbr("ex") == LvmLockType.EXCLUSIVE

    def test_from_abbr_null(self):
        assert LvmLockType.from_abbr("un") == LvmLockType.NULL
        assert LvmLockType.from_abbr("") == LvmLockType.NULL

    def test_from_abbr_with_whitespace(self):
        assert LvmLockType.from_abbr("  sh  ") == LvmLockType.SHARE

    def test_from_abbr_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown lock type"):
            LvmLockType.from_abbr("invalid")


class TestLvmExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(VgNotFoundError, LvmError)
        assert issubclass(LvNotFoundError, LvmError)
        assert issubclass(PvNotFoundError, LvmError)
        assert issubclass(LvmLockError, LvmError)

    def test_exception_message(self):
        err = LvmError("test error")
        assert str(err) == "test error"


class TestPhysicalVolume:
    def test_pv_creation(self):
        pv = PhysicalVolume(
            path="/dev/sda1",
            uuid="abc-123",
            vg_name="vg0",
            size=1024 * 1024 * 1024,  # 1 GiB
            free=512 * 1024 * 1024,   # 512 MiB
        )
        assert pv.path == "/dev/sda1"
        assert pv.uuid == "abc-123"
        assert pv.vg_name == "vg0"
        assert pv.size == 1024 * 1024 * 1024
        assert pv.free == 512 * 1024 * 1024

    def test_pv_used_property(self):
        pv = PhysicalVolume(
            path="/dev/sda1",
            uuid="abc-123",
            vg_name="vg0",
            size=1000,
            free=400,
        )
        assert pv.used == 600

    def test_pv_defaults(self):
        pv = PhysicalVolume(
            path="/dev/sda1",
            uuid="abc-123",
            vg_name="vg0",
            size=1000,
            free=500,
        )
        assert pv.format == "lvm2"
        assert pv.attrs == ""


class TestVolumeGroup:
    def test_vg_creation(self):
        vg = VolumeGroup(
            name="vg0",
            uuid="vg-uuid-123",
            size=10 * 1024 * 1024 * 1024,  # 10 GiB
            free=5 * 1024 * 1024 * 1024,   # 5 GiB
            pv_count=2,
            lv_count=3,
        )
        assert vg.name == "vg0"
        assert vg.uuid == "vg-uuid-123"
        assert vg.pv_count == 2
        assert vg.lv_count == 3

    def test_vg_used_property(self):
        vg = VolumeGroup(
            name="vg0",
            uuid="vg-uuid",
            size=1000,
            free=300,
            pv_count=1,
            lv_count=2,
        )
        assert vg.used == 700

    def test_vg_with_tags(self):
        vg = VolumeGroup(
            name="vg0",
            uuid="vg-uuid",
            size=1000,
            free=500,
            pv_count=1,
            lv_count=1,
            tags=["zstack", "shared"],
        )
        assert "zstack" in vg.tags
        assert "shared" in vg.tags


class TestLogicalVolume:
    def test_lv_creation(self):
        lv = LogicalVolume(
            name="lv0",
            vg_name="vg0",
            path="/dev/vg0/lv0",
            size=1024 * 1024 * 1024,
        )
        assert lv.name == "lv0"
        assert lv.vg_name == "vg0"
        assert lv.path == "/dev/vg0/lv0"

    def test_lv_is_active_property(self):
        # attrs format: Voltype|Permissions|Alloc|Fixed|State|Device|...
        # Position 4 is State: 'a' = active
        lv_active = LogicalVolume(
            name="lv0", vg_name="vg0", path="/dev/vg0/lv0",
            size=1000, attrs="-wi-a-----"
        )
        lv_inactive = LogicalVolume(
            name="lv1", vg_name="vg0", path="/dev/vg0/lv1",
            size=1000, attrs="-wi-------"
        )
        assert lv_active.is_active is True
        assert lv_inactive.is_active is False

    def test_lv_is_thin_property(self):
        lv_thin = LogicalVolume(
            name="lv0", vg_name="vg0", path="/dev/vg0/lv0",
            size=1000, attrs="Vwi-a-t---"
        )
        lv_normal = LogicalVolume(
            name="lv1", vg_name="vg0", path="/dev/vg0/lv1",
            size=1000, attrs="-wi-a-----"
        )
        assert lv_thin.is_thin is True
        assert lv_normal.is_thin is False

    def test_lv_is_snapshot_property(self):
        lv_snap = LogicalVolume(
            name="snap0", vg_name="vg0", path="/dev/vg0/snap0",
            size=1000, attrs="swi-a-s---"
        )
        lv_normal = LogicalVolume(
            name="lv0", vg_name="vg0", path="/dev/vg0/lv0",
            size=1000, attrs="-wi-a-----"
        )
        assert lv_snap.is_snapshot is True
        assert lv_normal.is_snapshot is False


class TestThinPool:
    def test_thin_pool_creation(self):
        pool = ThinPool(
            name="pool0",
            vg_name="vg0",
            size=100 * 1024 * 1024 * 1024,  # 100 GiB
            data_percent=50.0,
            metadata_percent=10.0,
        )
        assert pool.name == "pool0"
        assert pool.vg_name == "vg0"
        assert pool.data_percent == 50.0

    def test_thin_pool_path_property(self):
        pool = ThinPool(
            name="pool0", vg_name="vg0",
            size=1000, data_percent=0, metadata_percent=0
        )
        assert pool.path == "/dev/vg0/pool0"

    def test_thin_pool_used_property(self):
        pool = ThinPool(
            name="pool0", vg_name="vg0",
            size=1000, data_percent=25.0, metadata_percent=5.0
        )
        assert pool.used == 250  # 25% of 1000

    def test_thin_pool_free_property(self):
        pool = ThinPool(
            name="pool0", vg_name="vg0",
            size=1000, data_percent=25.0, metadata_percent=5.0
        )
        assert pool.free == 750  # 1000 - 250


class TestBlockDevice:
    def test_block_device_creation(self):
        dev = BlockDevice(
            path="/dev/sda",
            wwid="3600508b4000156d70001200000b60000",
            size=1024 * 1024 * 1024 * 100,  # 100 GiB
            vendor="HP",
            model="LOGICAL VOLUME",
        )
        assert dev.path == "/dev/sda"
        assert dev.wwid == "3600508b4000156d70001200000b60000"
        assert dev.vendor == "HP"

    def test_block_device_defaults(self):
        dev = BlockDevice(path="/dev/sdb")
        assert dev.wwid is None
        assert dev.wwn is None
        assert dev.serial is None
        assert dev.size == 0
        assert dev.type == ""
