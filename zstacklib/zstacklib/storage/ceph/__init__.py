# Copyright (c) ZStack.io, Inc.

"""
Ceph storage management module.

This module provides classes and functions for managing Ceph distributed
storage, including configuration, pool capacity queries, and NBD-based
block device access.

Example usage:
    from zstacklib.storage.ceph import (
        get_ceph_manufacturer,
        get_ceph_client_conf,
        get_pools_capacity,
        NbdRemoteStorage
    )
    
    # Check Ceph manufacturer
    manufacturer = get_ceph_manufacturer()
    print(f"Ceph: {manufacturer}")
    
    # Get client configuration
    conf_path, keyring_path, username = get_ceph_client_conf(ps_uuid)
    
    # Query pool capacity
    pools = get_pools_capacity()
    for pool in pools:
        print(f"Pool {pool.pool_name}: {pool.available_capacity} bytes available")
    
    # Mount RBD via NBD
    storage = NbdRemoteStorage("ceph://pool/image", "/mnt/volume", None, ps_uuid)
    device = storage.mount()
    # ... use device ...
    storage.umount()

Module structure:
    - exceptions: Exception classes (CephError, CephNbdError, etc.)
    - models: Data structures (CephPoolCapacity, CephOsdCapacity)
    - config: Client configuration management
    - utils: Utility functions (get_fsid, manufacturer detection)
    - pool: Pool capacity queries
    - nbd: NBD-based remote storage

Note:
    Third-party Ceph integrations (XSKY, etc.) are available in the
    thirdparty submodule (not included in this base module).
"""

# Exceptions
from .exceptions import (
    CephError,
    CephConnectionError,
    CephConfigError,
    CephPoolNotFoundError,
    CephNbdError,
    CephMountError,
)

# Models and constants
from .models import (
    CephPoolCapacity,
    CephOsdCapacity,
    CEPH_CONF_ROOT,
    CEPH_KEYRING_CONFIG_NAME,
    CEPH_CONF_FILENAME,
    QEMU_NBD_SOCKET_DIR,
    QEMU_NBD_SOCKET_PREFIX,
    NBD_DEV_PREFIX,
    MANUFACTURER_XSKY,
    MANUFACTURER_SANDSTONE,
    MANUFACTURER_OPENSOURCE,
)

# Configuration
from .config import (
    get_ceph_client_conf,
    update_ceph_client_access_conf,
    get_heartbeat_object_name,
)

# Utilities
from .utils import (
    get_fsid,
    is_xsky,
    is_sandstone,
    get_ceph_manufacturer,
    get_mon_addr,
    normalize_install_path,
)

# Pool operations
from .pool import (
    get_pools_capacity,
)

# NBD remote storage
from .nbd import (
    NbdRemoteStorage,
)

__all__ = [
    # Exceptions
    'CephError',
    'CephConnectionError',
    'CephConfigError',
    'CephPoolNotFoundError',
    'CephNbdError',
    'CephMountError',
    
    # Models and constants
    'CephPoolCapacity',
    'CephOsdCapacity',
    'CEPH_CONF_ROOT',
    'CEPH_KEYRING_CONFIG_NAME',
    'CEPH_CONF_FILENAME',
    'QEMU_NBD_SOCKET_DIR',
    'QEMU_NBD_SOCKET_PREFIX',
    'NBD_DEV_PREFIX',
    'MANUFACTURER_XSKY',
    'MANUFACTURER_SANDSTONE',
    'MANUFACTURER_OPENSOURCE',
    
    # Configuration
    'get_ceph_client_conf',
    'update_ceph_client_access_conf',
    'get_heartbeat_object_name',
    
    # Utilities
    'get_fsid',
    'is_xsky',
    'is_sandstone',
    'get_ceph_manufacturer',
    'get_mon_addr',
    'normalize_install_path',
    
    # Pool operations
    'get_pools_capacity',
    
    # NBD remote storage
    'NbdRemoteStorage',
]
