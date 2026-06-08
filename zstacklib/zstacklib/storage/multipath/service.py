"""Multipath service management.

This module provides functions for managing multipathd service:

- enable(): Enable and start multipathd
- disable(): Disable and stop multipathd
- start(): Start multipathd
- stop(): Stop multipathd
- restart(): Restart multipathd
- is_running(): Check if multipathd is running
"""

import logging

from zstacklib.utils import bash, linux

from .exceptions import ServiceError, MultipathNotRunningError


logger = logging.getLogger(__name__)


def is_running() -> bool:
    """Check if multipathd service is running.
    
    Returns:
        True if multipathd is running
    """
    # Check if multipath command works
    r = bash.bash_r("multipath -t > /dev/null 2>&1")
    if r != 0:
        return False
    
    # Check if daemon is running
    r = bash.bash_r("pgrep multipathd > /dev/null 2>&1")
    return r == 0


def is_enabled() -> bool:
    """Check if multipathd service is enabled.
    
    Returns:
        True if multipathd is enabled to start on boot
    """
    r = bash.bash_r("systemctl is-enabled multipathd.service > /dev/null 2>&1")
    return r == 0


def start() -> bool:
    """Start multipathd service.
    
    Returns:
        True if successful
        
    Raises:
        ServiceError: If start fails
    """
    r, o, e = bash.bash_roe("systemctl start multipathd.service")
    if r != 0:
        raise ServiceError("start", "Failed to start multipathd: {}".format(e), r)
    
    logger.info("Started multipathd service")
    return True


def stop() -> bool:
    """Stop multipathd service.
    
    Returns:
        True if successful
        
    Raises:
        ServiceError: If stop fails
    """
    r, o, e = bash.bash_roe("systemctl stop multipathd.service")
    if r != 0:
        raise ServiceError("stop", "Failed to stop multipathd: {}".format(e), r)
    
    logger.info("Stopped multipathd service")
    return True


def restart() -> bool:
    """Restart multipathd service.
    
    Returns:
        True if successful
        
    Raises:
        ServiceError: If restart fails
    """
    r, o, e = bash.bash_roe("systemctl restart multipathd.service")
    if r != 0:
        raise ServiceError("restart", "Failed to restart multipathd: {}".format(e), r)
    
    logger.info("Restarted multipathd service")
    return True


def reload() -> bool:
    """Reload multipathd configuration.
    
    Returns:
        True if successful
    """
    r = bash.bash_r("multipathd reconfigure 2>/dev/null")
    if r == 0:
        logger.info("Reloaded multipathd configuration")
        return True
    
    logger.warning("Failed to reload multipathd configuration")
    return False


@bash.in_bash
@linux.retry(times=3, sleep_time=1)
def enable() -> bool:
    """Enable and start multipath.
    
    This function:
    1. Loads dm-multipath and dm-round-robin kernel modules
    2. Enables multipath via mpathconf
    3. Enables and starts multipathd service
    
    Returns:
        True if successful
        
    Raises:
        MultipathNotRunningError: If multipath fails to start after retries
    """
    # Load kernel modules
    bash.bash_roe("modprobe dm-multipath")
    bash.bash_roe("modprobe dm-round-robin")
    
    # Enable multipath
    bash.bash_roe("mpathconf --enable --with_multipathd y")
    
    # Enable service
    bash.bash_roe("systemctl enable multipathd.service")
    
    # Verify it's running
    if not is_running():
        raise MultipathNotRunningError("Multipath still not running after enable")
    
    logger.info("Enabled multipath")
    return True


@bash.in_bash
@linux.retry(times=3, sleep_time=1)
def disable() -> bool:
    """Disable and stop multipath.
    
    Returns:
        True if successful
        
    Raises:
        ServiceError: If multipath fails to stop after retries
    """
    # Disable service
    bash.bash_roe("systemctl disable multipathd.service")
    
    # Stop service
    bash.bash_roe("systemctl stop multipathd.service")
    
    # Verify it's stopped
    if is_running():
        raise ServiceError("disable", "Multipath is still running after disable")
    
    logger.info("Disabled multipath")
    return True


def ensure_running() -> bool:
    """Ensure multipathd is running, start if not.
    
    Returns:
        True if multipathd is running
    """
    if is_running():
        return True
    
    try:
        return start()
    except ServiceError:
        return False


def get_status() -> dict:
    """Get multipathd status information.
    
    Returns:
        Dict with status information
    """
    return {
        "running": is_running(),
        "enabled": is_enabled(),
    }
