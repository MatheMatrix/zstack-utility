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


def __getattr__(name):
    if name == 'pv':
        from zstacklib.storage.lvm import pv
        return pv
    elif name == 'vg':
        from zstacklib.storage.lvm import vg
        return vg
    elif name == 'lv':
        from zstacklib.storage.lvm import lv
        return lv
    elif name == 'thin':
        from zstacklib.storage.lvm import thin
        return thin
    elif name == 'lock':
        from zstacklib.storage.lvm import lock
        return lock
    elif name == 'config':
        from zstacklib.storage.lvm import config
        return config
    elif name == 'snapshot':
        from zstacklib.storage.lvm import snapshot
        return snapshot
    elif name == 'multipath':
        from zstacklib.storage.lvm import multipath
        return multipath
    raise AttributeError(f"module 'zstacklib.storage.lvm' has no attribute '{name}'")
