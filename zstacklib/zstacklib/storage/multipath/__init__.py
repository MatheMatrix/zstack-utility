"""Multipath storage management module.

This module provides comprehensive multipath management functionality including:

- Device detection and management
- Configuration file management
- Service control (multipathd)

Example usage:

    from zstacklib.storage import multipath
    
    # Check if multipath is running
    if multipath.is_multipath_running():
        print("Multipath is active")
    
    # Check if device is a multipath path
    if multipath.is_slave_of_multipath('/dev/sdb'):
        print("Device is part of multipath")
    
    # Get multipath device name
    name = multipath.get_multipath_name('sdb')
    
    # Update multipath.conf with defaults
    multipath.update_config()
    
    # Enable multipath
    multipath.enable()

All operations are designed to be safe and idempotent.
"""

# Exceptions
from .exceptions import (
    MultipathError,
    MultipathNotRunningError,
    MultipathConfigError,
    DeviceNotFoundError,
    ServiceError,
)

# Data models
from .models import (
    MultipathPath,
    MultipathDevice,
    BlacklistEntry,
    DeviceConfig,
    DEFAULT_DEVICE_CONFIG,
)

# Configuration management
from .config import (
    parse_config,
    read_config,
    write_config,
    update_config,
    get_blacklist,
    add_blacklist_wwid,
    MULTIPATH_CONF_PATH,
)

# Device operations
from .device import (
    is_multipath_running,
    is_slave_of_multipath,
    is_slave_of_multipath_batch,
    get_slave_multipaths,
    is_multipath_device,
    get_multipath_dmname,
    get_multipath_name,
    get_dm_wwid,
    resize_map,
    reconfigure,
    flush_device,
    flush_all,
    list_multipaths,
    get_path_for_device,
)

# Service management
from .service import (
    is_running,
    is_enabled,
    start,
    stop,
    restart,
    reload,
    enable,
    disable,
    ensure_running,
    get_status,
)

__all__ = [
    # Exceptions
    "MultipathError",
    "MultipathNotRunningError",
    "MultipathConfigError",
    "DeviceNotFoundError",
    "ServiceError",
    # Models
    "MultipathPath",
    "MultipathDevice",
    "BlacklistEntry",
    "DeviceConfig",
    "DEFAULT_DEVICE_CONFIG",
    # Config
    "parse_config",
    "read_config",
    "write_config",
    "update_config",
    "get_blacklist",
    "add_blacklist_wwid",
    "MULTIPATH_CONF_PATH",
    # Device
    "is_multipath_running",
    "is_slave_of_multipath",
    "is_slave_of_multipath_batch",
    "get_slave_multipaths",
    "is_multipath_device",
    "get_multipath_dmname",
    "get_multipath_name",
    "get_dm_wwid",
    "resize_map",
    "reconfigure",
    "flush_device",
    "flush_all",
    "list_multipaths",
    "get_path_for_device",
    # Service
    "is_running",
    "is_enabled",
    "start",
    "stop",
    "restart",
    "reload",
    "enable",
    "disable",
    "ensure_running",
    "get_status",
]
