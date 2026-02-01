"""LVM functional domain module.

This module provides a clean, organized interface for LVM operations:
- pv: Physical Volume operations
- vg: Volume Group operations  
- lv: Logical Volume operations
- thin: Thin provisioning
- lock: Lock management (lvmlockd/sanlock)
- config: LVM configuration
- snapshot: Snapshot operations
- multipath: Multipath device handling
- models: Data classes and exceptions
"""

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

from zstacklib.storage.lvm import pv
from zstacklib.storage.lvm import vg
from zstacklib.storage.lvm import lv
from zstacklib.storage.lvm import thin
from zstacklib.storage.lvm import lock
from zstacklib.storage.lvm import config
from zstacklib.storage.lvm import snapshot
from zstacklib.storage.lvm import multipath

__all__ = [
    'VolumeProvisioningStrategy',
    'LvmLockType',
    'LvmError',
    'VgNotFoundError',
    'LvNotFoundError',
    'PvNotFoundError',
    'LvmLockError',
    'PhysicalVolume',
    'VolumeGroup',
    'LogicalVolume',
    'ThinPool',
    'BlockDevice',
    'pv',
    'vg',
    'lv',
    'thin',
    'lock',
    'config',
    'snapshot',
    'multipath',
]
