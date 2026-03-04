"""iSCSI storage management module.

This module provides comprehensive iSCSI management functionality including:

- Target discovery
- Session login/logout
- CHAP authentication
- Configuration management
- Disk enumeration utilities
"""

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

from .models import (
    IscsiPortal,
    IscsiTarget,
    IscsiLun,
    IscsiSession,
    ChapCredentials,
    DiscoveryResult,
    LoginResult,
)

__all__ = [
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
    "IscsiPortal",
    "IscsiTarget",
    "IscsiLun",
    "IscsiSession",
    "ChapCredentials",
    "DiscoveryResult",
    "LoginResult",
    "discover_targets",
    "discover_targets_safe",
    "parse_discovery_output",
    "get_discovered_iqns",
    "find_target_by_iqn",
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


def __getattr__(name):
    """Getattr."""
    if name in ('discover_targets', 'discover_targets_safe', 'parse_discovery_output',
                'get_discovered_iqns', 'find_target_by_iqn'):
        from . import discovery
        val = getattr(discovery, name)
        globals()[name] = val
        return val
    elif name in ('login', 'logout', 'list_sessions', 'get_session', 'get_session_id',
                  'is_logged_in', 'rescan_session', 'rescan_all_sessions',
                  'get_host_number', 'get_session_luns'):
        from . import session
        val = getattr(session, name)
        globals()[name] = val
        return val
    elif name in ('check_iscsid_conf', 'clean_cache', 'clean_all_cache', 'get_node_config',
                  'set_node_param', 'set_node_startup', 'is_iscsid_running', 'start_iscsid',
                  'ensure_iscsid_running', 'ISCSID_CONF_PATH', 'ISCSI_NODES_PATH'):
        from . import config
        val = getattr(config, name)
        globals()[name] = val
        return val
    elif name in ('list_iscsi_disks', 'get_disk_realpath', 'wait_for_disks', 'refresh_multipath',
                  'is_multipath_device', 'rescan_scsi_bus', 'delete_scsi_device',
                  'get_iscsi_initiator_name', 'set_iscsi_initiator_name', 'parse_iscsi_disk_path',
                  'DEV_DISK_BY_PATH'):
        from . import utils
        val = getattr(utils, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module 'zstacklib.storage.iscsi' has no attribute '{name}'")
