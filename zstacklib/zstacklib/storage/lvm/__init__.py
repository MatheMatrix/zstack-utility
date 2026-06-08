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
    """Lazy-load submodules on first access (PEP 562).

    Results are cached in globals() so __getattr__ runs only once per name.
    """
    _submodules = {
        'pv', 'vg', 'lv', 'thin', 'lock', 'config', 'snapshot', 'multipath',
    }
    if name in _submodules:
        import importlib
        mod = importlib.import_module(f'.{name}', __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'zstacklib.storage.lvm' has no attribute '{name}'")
