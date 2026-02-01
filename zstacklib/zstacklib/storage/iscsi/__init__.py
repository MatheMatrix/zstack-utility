"""iSCSI storage management module.

This module provides comprehensive iSCSI management functionality including:

- Target discovery
- Session login/logout
- CHAP authentication
- Configuration management
- Disk enumeration utilities

Example usage:

    from zstacklib.storage import iscsi
    
    # Discover targets on a portal
    targets = iscsi.discover_targets('192.168.1.100', 3260)
    
    # Login to a target
    session = iscsi.login(
        ip='192.168.1.100',
        iqn='iqn.2020-01.com.example:storage',
        chap_username='user',
        chap_password='secret'
    )
    
    # List disks after login
    disks = iscsi.list_iscsi_disks('192.168.1.100', 'iqn.2020-01.com.example:storage')
    
    # Logout from target
    iscsi.logout('192.168.1.100', 'iqn.2020-01.com.example:storage')

All operations are thread-safe with appropriate locking via @lock.lock('iscsiadm').
"""

# Exceptions
from .exceptions import (
    IscsiError,
    DiscoveryError,
    LoginError,
    LogoutError,
    SessionNotFoundError,
    TargetNotFoundError,
    ChapAuthError,
    TimeoutError,
    RescanError,
    NodeDeleteError,
)

# Data models
from .models import (
    IscsiPortal,
    IscsiTarget,
    IscsiLun,
    IscsiSession,
    ChapCredentials,
    DiscoveryResult,
    LoginResult,
)

# Discovery operations
from .discovery import (
    discover_targets,
    discover_targets_safe,
    parse_discovery_output,
    get_discovered_iqns,
    find_target_by_iqn,
)

# Session management
from .session import (
    login,
    logout,
    list_sessions,
    get_session,
    get_session_id,
    is_logged_in,
    rescan_session,
    rescan_all_sessions,
    get_host_number,
    get_session_luns,
)

# Configuration management
from .config import (
    check_iscsid_conf,
    clean_cache,
    clean_all_cache,
    get_node_config,
    set_node_param,
    set_node_startup,
    is_iscsid_running,
    start_iscsid,
    ensure_iscsid_running,
    ISCSID_CONF_PATH,
    ISCSI_NODES_PATH,
)

# Utility functions
from .utils import (
    list_iscsi_disks,
    get_disk_realpath,
    wait_for_disks,
    refresh_multipath,
    is_multipath_device,
    rescan_scsi_bus,
    delete_scsi_device,
    get_iscsi_initiator_name,
    set_iscsi_initiator_name,
    parse_iscsi_disk_path,
    DEV_DISK_BY_PATH,
)

__all__ = [
    # Exceptions
    "IscsiError",
    "DiscoveryError",
    "LoginError",
    "LogoutError",
    "SessionNotFoundError",
    "TargetNotFoundError",
    "ChapAuthError",
    "TimeoutError",
    "RescanError",
    "NodeDeleteError",
    # Models
    "IscsiPortal",
    "IscsiTarget",
    "IscsiLun",
    "IscsiSession",
    "ChapCredentials",
    "DiscoveryResult",
    "LoginResult",
    # Discovery
    "discover_targets",
    "discover_targets_safe",
    "parse_discovery_output",
    "get_discovered_iqns",
    "find_target_by_iqn",
    # Session
    "login",
    "logout",
    "list_sessions",
    "get_session",
    "get_session_id",
    "is_logged_in",
    "rescan_session",
    "rescan_all_sessions",
    "get_host_number",
    "get_session_luns",
    # Config
    "check_iscsid_conf",
    "clean_cache",
    "clean_all_cache",
    "get_node_config",
    "set_node_param",
    "set_node_startup",
    "is_iscsid_running",
    "start_iscsid",
    "ensure_iscsid_running",
    "ISCSID_CONF_PATH",
    "ISCSI_NODES_PATH",
    # Utils
    "list_iscsi_disks",
    "get_disk_realpath",
    "wait_for_disks",
    "refresh_multipath",
    "is_multipath_device",
    "rescan_scsi_bus",
    "delete_scsi_device",
    "get_iscsi_initiator_name",
    "set_iscsi_initiator_name",
    "parse_iscsi_disk_path",
    "DEV_DISK_BY_PATH",
]
