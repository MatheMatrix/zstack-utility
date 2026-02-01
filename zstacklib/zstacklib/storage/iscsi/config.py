"""iSCSI configuration management.

This module provides functions for managing iSCSI configuration:

- check_iscsid_conf(): Verify and fix iscsid.conf settings
- clean_cache(): Clean stale iSCSI cache configurations
- get_node_config(): Get node configuration for a target
- set_node_param(): Set a node parameter
"""

import logging
import os
import shutil
from typing import Optional

from zstacklib.utils import bash, linux, shell

from .models import IscsiPortal


logger = logging.getLogger(__name__)

# Default paths
ISCSID_CONF_PATH = "/etc/iscsi/iscsid.conf"
ISCSI_NODES_PATH = "/var/lib/iscsi/nodes"


def check_iscsid_conf(conf_path: str = ISCSID_CONF_PATH) -> None:
    """Check and fix iscsid.conf settings.
    
    This function ensures iscsid.conf has proper startup settings
    for systemd-based systems.
    
    Args:
        conf_path: Path to iscsid.conf (default /etc/iscsi/iscsid.conf)
        
    Example:
        >>> check_iscsid_conf()
    """
    if not os.path.exists(conf_path):
        logger.warning("iscsid.conf not found at %s", conf_path)
        return
    
    # Fix iscsid.startup setting for systemd
    shell.call(
        "sed -i 's/.*iscsid.startup.*=.*/iscsid.startup = \\/bin\\/systemctl start iscsid.socket iscsiuio.socket/' {}".format(conf_path),
        exception=False
    )
    logger.debug("Checked iscsid.conf at %s", conf_path)


def clean_cache(
    ip: str,
    port: int = 3260,
    nodes_path: str = ISCSI_NODES_PATH
) -> int:
    """Clean stale iSCSI cache configurations for a portal.
    
    This removes cached node configurations from /var/lib/iscsi/nodes/
    for the specified portal. This is useful before discovery to ensure
    fresh configuration.
    
    Args:
        ip: iSCSI portal IP address
        port: iSCSI portal port (default 3260)
        nodes_path: Path to iSCSI nodes directory
        
    Returns:
        Number of cache entries removed
        
    Example:
        >>> removed = clean_cache('192.168.1.100', 3260)
        >>> print(f"Removed {removed} cached entries")
    """
    if not os.path.exists(nodes_path):
        return 0
    
    portal_pattern = "{},{}".format(ip, port)
    removed_count = 0
    
    # Find and remove cache entries matching the portal
    cmd = "ls {}/*/ 2>/dev/null | grep {} | grep {}".format(
        nodes_path, ip, port
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0 or not o.strip():
        return 0
    
    results = o.strip().splitlines()
    for result in results:
        result = result.strip()
        if not result:
            continue
        
        # Find directories containing this cache file
        cmd = "dirname {}/*/{} 2>/dev/null".format(nodes_path, result)
        r, dpaths, e = bash.bash_roe(cmd)
        
        if r != 0 or not dpaths.strip():
            continue
        
        for dpath in dpaths.strip().splitlines():
            dpath = dpath.strip()
            if not dpath:
                continue
            
            ipath = os.path.join(dpath, result)
            if os.path.isdir(ipath):
                try:
                    linux.rm_dir_force(ipath)
                    removed_count += 1
                    logger.debug("Removed cache directory: %s", ipath)
                except Exception as e:
                    logger.warning("Failed to remove cache directory %s: %s", ipath, e)
            elif os.path.isfile(ipath):
                try:
                    linux.rm_file_force(ipath)
                    removed_count += 1
                    logger.debug("Removed cache file: %s", ipath)
                except Exception as e:
                    logger.warning("Failed to remove cache file %s: %s", ipath, e)
    
    if removed_count > 0:
        logger.info("Cleaned %d iSCSI cache entries for portal %s:%s", 
                   removed_count, ip, port)
    
    return removed_count


def clean_all_cache(nodes_path: str = ISCSI_NODES_PATH) -> int:
    """Clean all iSCSI cache configurations.
    
    WARNING: This removes all cached iSCSI node configurations.
    
    Args:
        nodes_path: Path to iSCSI nodes directory
        
    Returns:
        Number of target directories removed
    """
    if not os.path.exists(nodes_path):
        return 0
    
    removed_count = 0
    
    try:
        for entry in os.listdir(nodes_path):
            entry_path = os.path.join(nodes_path, entry)
            if os.path.isdir(entry_path):
                try:
                    shutil.rmtree(entry_path)
                    removed_count += 1
                except Exception as e:
                    logger.warning("Failed to remove %s: %s", entry_path, e)
    except Exception as e:
        logger.error("Failed to list nodes directory: %s", e)
    
    if removed_count > 0:
        logger.info("Cleaned %d iSCSI cache entries from %s", removed_count, nodes_path)
    
    return removed_count


def get_node_config(
    ip: str,
    iqn: str,
    port: int = 3260
) -> Optional[str]:
    """Get node configuration for a target.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port
        
    Returns:
        Node configuration output, or None if not found
    """
    portal_str = "{}:{}".format(ip, port)
    cmd = 'iscsiadm -m node -T "{}" -p {} 2>/dev/null'.format(iqn, portal_str)
    
    r, o, e = bash.bash_roe(cmd)
    if r != 0:
        return None
    
    return o


def set_node_param(
    ip: str,
    iqn: str,
    param_name: str,
    param_value: str,
    port: int = 3260
) -> bool:
    """Set a node parameter.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        param_name: Parameter name (e.g., 'node.session.auth.authmethod')
        param_value: Parameter value
        port: iSCSI portal port
        
    Returns:
        True if successful, False otherwise
        
    Example:
        >>> set_node_param('192.168.1.100', 'iqn.2020-01.com.example:storage',
        ...                'node.startup', 'automatic')
        True
    """
    portal_str = "{}:{}".format(ip, port)
    cmd = 'iscsiadm -m node -T "{}" -p {} -o update -n {} -v {}'.format(
        iqn, portal_str, param_name, param_value
    )
    
    r, o, e = bash.bash_roe(cmd)
    if r != 0:
        logger.error("Failed to set node param %s=%s: %s", param_name, param_value, e)
        return False
    
    logger.debug("Set node param %s=%s for %s", param_name, param_value, iqn)
    return True


def set_node_startup(
    ip: str,
    iqn: str,
    startup: str = "automatic",
    port: int = 3260
) -> bool:
    """Set node startup mode.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        startup: Startup mode ('automatic', 'manual', 'onboot')
        port: iSCSI portal port
        
    Returns:
        True if successful
    """
    return set_node_param(ip, iqn, "node.startup", startup, port)


def is_iscsid_running() -> bool:
    """Check if iscsid daemon is running.
    
    Returns:
        True if iscsid is running
    """
    r = bash.bash_r("systemctl is-active iscsid.service >/dev/null 2>&1")
    return r == 0


def start_iscsid() -> bool:
    """Start iscsid daemon.
    
    Returns:
        True if started successfully
    """
    r = bash.bash_r("systemctl start iscsid.service")
    if r == 0:
        logger.info("Started iscsid service")
        return True
    
    logger.error("Failed to start iscsid service")
    return False


def ensure_iscsid_running() -> bool:
    """Ensure iscsid daemon is running, start if not.
    
    Returns:
        True if iscsid is running
    """
    if is_iscsid_running():
        return True
    return start_iscsid()
