"""Multipath device detection and management.

This module provides functions for multipath device operations:

- is_multipath_running(): Check if multipathd is running
- is_multipath_device(): Check if device is a multipath device
- is_slave_of_multipath(): Check if device is a path of multipath
- get_multipath_name(): Get multipath device name
- get_dm_wwid(): Get WWID for a DM device
- resize_map(): Resize a multipath device
"""

import logging
import os
from typing import Optional, List

from zstacklib.utils import bash, linux, shell

from .exceptions import MultipathNotRunningError, DeviceNotFoundError


logger = logging.getLogger(__name__)


def is_multipath_running() -> bool:
    """Check if multipathd daemon is running.
    
    Returns:
        True if multipath is configured and multipathd is running
        
    Example:
        >>> if is_multipath_running():
        ...     print("Multipath is active")
    """
    # Check if multipath command works
    r = bash.bash_r("multipath -t > /dev/null 2>&1")
    if r != 0:
        return False
    
    # Check if daemon is running
    r = bash.bash_r("pgrep multipathd > /dev/null 2>&1")
    return r == 0


def is_slave_of_multipath(dev_path: str) -> bool:
    """Check if device is a path of a multipath device.
    
    Args:
        dev_path: Device path (e.g., /dev/sdb)
        
    Returns:
        True if device is part of a multipath device
        
    Example:
        >>> is_slave_of_multipath('/dev/sdb')
        True
    """
    if not is_multipath_running():
        return False
    
    r = bash.bash_r("multipath -c {} 2>/dev/null".format(dev_path))
    return r == 0


def is_slave_of_multipath_batch(
    dev_path: str,
    slave_multipaths: List[str],
    multipath_running: bool
) -> bool:
    """Check if device is a multipath slave using cached data.
    
    This is an optimized version for batch checking.
    
    Args:
        dev_path: Device path
        slave_multipaths: Pre-fetched list of slave device names
        multipath_running: Pre-checked multipath running status
        
    Returns:
        True if device is a multipath slave
    """
    if not multipath_running:
        return False
    
    dev_name = dev_path.split("/")[-1]
    return dev_name in slave_multipaths


def get_slave_multipaths() -> List[str]:
    """Get list of all devices that are multipath paths.
    
    Returns:
        List of device names (e.g., ['sda', 'sdb'])
    """
    if not is_multipath_running():
        return []
    
    cmd = "multipath -l | grep -A 1 policy | grep -v policy | awk -F - '{print $2}' | awk '{print $2}'"
    output = shell.call(cmd).strip()
    
    return [s for s in output.splitlines() if s.strip()]


def is_multipath_device(dev_name: str) -> bool:
    """Check if device is a multipath device (not a path).
    
    Args:
        dev_name: Device name (e.g., dm-0, mpath0)
        
    Returns:
        True if device is a multipath device
        
    Example:
        >>> is_multipath_device('dm-0')
        True
    """
    if not is_multipath_running():
        return False
    
    # Check with multipath command
    r = bash.bash_r("multipath /dev/{} -l 2>/dev/null | grep -q policy".format(dev_name))
    if r == 0:
        return True
    
    # Check for slaves (multipath devices have paths as slaves)
    slaves_path = "/sys/class/block/{}/slaves/".format(dev_name)
    slaves = linux.listdir(slaves_path)
    
    if slaves and len(slaves) > 0:
        # Filter empty strings
        slaves = [s for s in slaves if s.strip()]
        return len(slaves) > 0
    
    return False


def get_multipath_dmname(dev_name: str) -> Optional[str]:
    """Get the DM device name for a multipath device.
    
    If dev_name is a multipath device, returns it.
    If dev_name is a path, returns the multipath device it belongs to.
    
    Args:
        dev_name: Device name
        
    Returns:
        DM device name (e.g., dm-0) or None if not multipath
        
    Example:
        >>> get_multipath_dmname('sdb')  # sdb is a path
        'dm-0'
        >>> get_multipath_dmname('dm-0')  # dm-0 is multipath device
        'dm-0'
    """
    # Check if device has slaves (is multipath device)
    slaves_path = "/sys/class/block/{}/slaves/".format(dev_name)
    slaves = linux.listdir(slaves_path)
    
    if slaves and len(slaves) > 0:
        slaves = [s for s in slaves if s.strip()]
        if slaves:
            return dev_name
    
    # Check if it's a path of a multipath device
    r = bash.bash_r("multipath /dev/{} -l 2>/dev/null | grep -q policy".format(dev_name))
    if r != 0:
        return None
    
    # Get the DM device
    dm = bash.bash_o(
        "multipath -l /dev/{} 2>/dev/null | head -n1 | grep -Eo 'dm-[0-9]+'".format(dev_name)
    ).strip()
    
    return dm if dm else None


def get_multipath_name(dev_name: str) -> Optional[str]:
    """Get the multipath device name (alias/wwid).
    
    Args:
        dev_name: Device name
        
    Returns:
        Multipath name (e.g., mpath0, 360000...) or None
        
    Example:
        >>> get_multipath_name('sdb')
        'mpath0'
    """
    name = bash.bash_o("multipath /dev/{} -l -v1 2>/dev/null".format(dev_name)).strip()
    return name if name else None


def get_dm_wwid(dm: str) -> Optional[str]:
    """Get the WWID for a device-mapper device.
    
    Args:
        dm: DM device name (e.g., dm-0) or path
        
    Returns:
        WWID string or None
        
    Example:
        >>> get_dm_wwid('dm-0')
        '360000000000000001'
    """
    try:
        cmd = "udevadm info -n {} 2>/dev/null | grep -o 'dm-uuid-mpath-\\S*' | awk -F '-' '{{print $NF; exit}}'".format(dm)
        output = shell.call("set -o pipefail; " + cmd).strip().strip("()")
        return output if output else None
    except Exception as e:
        logger.debug("Failed to get WWID for %s: %s", dm, e)
        return None


def resize_map(mpath_name: str) -> bool:
    """Resize a multipath device map.
    
    Args:
        mpath_name: Multipath device name
        
    Returns:
        True if successful
        
    Example:
        >>> resize_map('mpath0')
        True
    """
    r = bash.bash_r("multipathd resize map {} 2>/dev/null".format(mpath_name))
    if r == 0:
        logger.debug("Resized multipath map: %s", mpath_name)
        return True
    
    logger.warning("Failed to resize multipath map: %s", mpath_name)
    return False


def reconfigure() -> bool:
    """Reconfigure multipathd.
    
    Returns:
        True if successful
    """
    r = bash.bash_r("multipathd reconfigure 2>/dev/null")
    if r == 0:
        logger.info("Reconfigured multipathd")
        return True
    
    logger.warning("Failed to reconfigure multipathd")
    return False


def flush_device(dev_name: str) -> bool:
    """Flush a multipath device.
    
    Args:
        dev_name: Device name to flush
        
    Returns:
        True if successful
    """
    r = bash.bash_r("multipath -f {} 2>/dev/null".format(dev_name))
    if r == 0:
        logger.debug("Flushed multipath device: %s", dev_name)
        return True
    
    logger.warning("Failed to flush multipath device: %s", dev_name)
    return False


def flush_all() -> bool:
    """Flush all unused multipath devices.
    
    Returns:
        True if successful
    """
    r = bash.bash_r("multipath -F 2>/dev/null")
    if r == 0:
        logger.info("Flushed all unused multipath devices")
        return True
    
    logger.warning("Failed to flush multipath devices")
    return False


def list_multipaths() -> List[str]:
    """List all multipath device names.
    
    Returns:
        List of multipath device names
    """
    if not is_multipath_running():
        return []
    
    output = bash.bash_o("multipath -l -v1 2>/dev/null").strip()
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_path_for_device(dev_path: str) -> List[str]:
    """Get all paths for a multipath device.
    
    Args:
        dev_path: Device path (e.g., /dev/mapper/mpath0)
        
    Returns:
        List of path device names
    """
    real_path = os.path.realpath(dev_path)
    dev_name = os.path.basename(real_path)
    
    slaves_path = "/sys/class/block/{}/slaves/".format(dev_name)
    slaves = linux.listdir(slaves_path)
    
    if slaves:
        return [s for s in slaves if s.strip()]
    
    return []
