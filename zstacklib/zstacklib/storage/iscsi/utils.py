"""iSCSI utility functions.

This module provides utility functions for iSCSI operations:

- list_iscsi_disks(): List disk devices for an iSCSI session
- get_disk_by_path(): Get disk info by /dev/disk/by-path path
- wait_for_disks(): Wait for disks to appear after login
- refresh_multipath(): Refresh multipath for iSCSI disks
"""

import logging
import os
import time
from typing import List, Optional, Callable

from zstacklib.utils import bash, linux, shell


logger = logging.getLogger(__name__)

# Device paths
DEV_DISK_BY_PATH = "/dev/disk/by-path"


def list_iscsi_disks(
    ip: str,
    iqn: str,
    port: int = 3260
) -> List[str]:
    """List disk devices for an iSCSI session.
    
    Scans /dev/disk/by-path for devices matching the portal and target.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        
    Returns:
        List of device paths in /dev/disk/by-path/
        
    Example:
        >>> disks = list_iscsi_disks('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> print(disks)
        ['ip-192.168.1.100:3260-iscsi-iqn.2020-01.com.example:storage-lun-0']
    """
    portal_str = "{}:{}".format(ip, port)
    
    if not os.path.exists(DEV_DISK_BY_PATH):
        return []
    
    try:
        disks = []
        for f in os.listdir(DEV_DISK_BY_PATH):
            if portal_str in f and iqn in f:
                disks.append(f)
        return disks
    except OSError as e:
        logger.warning("Failed to list %s: %s", DEV_DISK_BY_PATH, e)
        return []


def get_disk_realpath(disk_by_path: str) -> Optional[str]:
    """Get the real device path for a disk-by-path entry.
    
    Args:
        disk_by_path: Device name in /dev/disk/by-path/
        
    Returns:
        Real device path (e.g., /dev/sdb), or None if not found
        
    Example:
        >>> get_disk_realpath('ip-192.168.1.100:3260-iscsi-iqn.2020-01.com.example:storage-lun-0')
        '/dev/sdb'
    """
    path = os.path.join(DEV_DISK_BY_PATH, disk_by_path)
    if not os.path.exists(path):
        return None
    
    try:
        return os.path.realpath(path)
    except OSError:
        return None


def wait_for_disks(
    ip: str,
    iqn: str,
    port: int = 3260,
    expected_count: Optional[int] = None,
    timeout: int = 60,
    interval: float = 1.0
) -> List[str]:
    """Wait for iSCSI disks to appear after login.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port
        expected_count: Expected number of disks (if known)
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds
        
    Returns:
        List of disk paths found
        
    Raises:
        TimeoutError: If timeout reached before disks appear
    """
    start_time = time.time()
    
    while True:
        disks = list_iscsi_disks(ip, iqn, port)
        
        if expected_count is not None:
            if len(disks) >= expected_count:
                return disks
        elif len(disks) > 0:
            return disks
        
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            if disks:
                return disks
            raise TimeoutError(
                "Timeout waiting for iSCSI disks: portal={}:{}, target={}".format(
                    ip, port, iqn
                )
            )
        
        time.sleep(interval)


def refresh_multipath(disk_paths: List[str]) -> None:
    """Refresh multipath devices for iSCSI disks.
    
    Args:
        disk_paths: List of disk paths in /dev/disk/by-path/
        
    Example:
        >>> disks = list_iscsi_disks('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> refresh_multipath(disks)
    """
    devpaths = []
    for disk_path in disk_paths:
        full_path = os.path.join(DEV_DISK_BY_PATH, disk_path)
        if os.path.exists(full_path):
            devpaths.append(os.path.realpath(full_path))
    
    # Find multipath devices
    mpaths = set()
    for devpath in devpaths:
        r, o = bash.bash_ro("multipath -l -v1 {}".format(devpath))
        if r == 0 and o.strip():
            mpaths.add(o.strip())
    
    # Resize multipath devices
    for mpath in mpaths:
        if mpath:
            shell.run("multipathd resize map {}".format(mpath))
            logger.debug("Resized multipath device: %s", mpath)


def is_multipath_device(devpath: str) -> bool:
    """Check if a device is a slave of a multipath device.
    
    Args:
        devpath: Device path (e.g., /dev/sdb)
        
    Returns:
        True if device is part of a multipath device
    """
    # Get the real path
    if not os.path.exists(devpath):
        return False
    
    real_path = os.path.realpath(devpath)
    dev_name = os.path.basename(real_path)
    
    # Check if device is listed as a multipath path
    r, o = bash.bash_ro("multipath -l -v1 {}".format(real_path))
    return r == 0 and o.strip() != ""


def rescan_scsi_bus(
    remove: bool = False,
    update: bool = True,
    add: bool = True,
    timeout: int = 120
) -> bool:
    """Rescan SCSI bus for new devices.
    
    Args:
        remove: Remove stale devices
        update: Update existing devices
        add: Add new devices
        timeout: Command timeout in seconds
        
    Returns:
        True if rescan completed successfully
    """
    flags = []
    if add:
        flags.append("-a")
    if remove:
        flags.append("-r")
    if update:
        flags.append("-u")
    
    flags_str = " ".join(flags) if flags else ""
    cmd = "timeout {} /usr/bin/rescan-scsi-bus.sh {} >/dev/null".format(
        timeout, flags_str
    )
    
    r = bash.bash_r(cmd)
    if r != 0:
        logger.warning("SCSI bus rescan returned error (may be normal)")
        return False
    
    logger.debug("SCSI bus rescan completed")
    return True


def delete_scsi_device(device_path: str) -> bool:
    """Delete a SCSI device by writing to its delete file.
    
    Args:
        device_path: Device path (e.g., /dev/sdb)
        
    Returns:
        True if deletion was successful
    """
    if not os.path.exists(device_path):
        return True  # Already gone
    
    real_path = os.path.realpath(device_path)
    dev_name = os.path.basename(real_path)
    
    delete_file = "/sys/block/{}/device/delete".format(dev_name)
    
    if not os.path.exists(delete_file):
        logger.warning("Delete file not found: %s", delete_file)
        return False
    
    try:
        linux.write_file(delete_file, "1")
        logger.debug("Deleted SCSI device: %s", device_path)
        return True
    except Exception as e:
        logger.error("Failed to delete SCSI device %s: %s", device_path, e)
        return False


def get_iscsi_initiator_name() -> Optional[str]:
    """Get the iSCSI initiator name.
    
    Returns:
        Initiator IQN or None if not configured
    """
    initiator_file = "/etc/iscsi/initiatorname.iscsi"
    
    if not os.path.exists(initiator_file):
        return None
    
    try:
        with open(initiator_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("InitiatorName="):
                    return line.split("=", 1)[1].strip()
    except Exception as e:
        logger.warning("Failed to read initiator name: %s", e)
    
    return None


def set_iscsi_initiator_name(iqn: str) -> bool:
    """Set the iSCSI initiator name.
    
    Args:
        iqn: Initiator IQN to set
        
    Returns:
        True if successful
    """
    initiator_file = "/etc/iscsi/initiatorname.iscsi"
    content = "InitiatorName={}\n".format(iqn)
    
    try:
        linux.write_file(initiator_file, content)
        logger.info("Set iSCSI initiator name to: %s", iqn)
        return True
    except Exception as e:
        logger.error("Failed to set initiator name: %s", e)
        return False


def parse_iscsi_disk_path(disk_path: str) -> Optional[dict]:
    """Parse an iSCSI disk path to extract components.
    
    Args:
        disk_path: Disk path like 'ip-192.168.1.100:3260-iscsi-iqn.xxx:target-lun-0'
        
    Returns:
        Dict with 'ip', 'port', 'iqn', 'lun' keys, or None if parsing fails
        
    Example:
        >>> info = parse_iscsi_disk_path('ip-192.168.1.100:3260-iscsi-iqn.2020-01.com.example:storage-lun-0')
        >>> print(info)
        {'ip': '192.168.1.100', 'port': 3260, 'iqn': 'iqn.2020-01.com.example:storage', 'lun': 0}
    """
    try:
        # Format: ip-<ip>:<port>-iscsi-<iqn>-lun-<lun>
        if not disk_path.startswith("ip-"):
            return None
        
        # Remove "ip-" prefix
        rest = disk_path[3:]
        
        # Split at "-iscsi-"
        parts = rest.split("-iscsi-")
        if len(parts) != 2:
            return None
        
        # Parse ip:port
        portal_part = parts[0]
        ip, port_str = portal_part.rsplit(":", 1)
        port = int(port_str)
        
        # Parse iqn and lun
        iqn_lun = parts[1]
        lun_idx = iqn_lun.rfind("-lun-")
        if lun_idx == -1:
            return None
        
        iqn = iqn_lun[:lun_idx]
        lun = int(iqn_lun[lun_idx + 5:])
        
        return {
            "ip": ip,
            "port": port,
            "iqn": iqn,
            "lun": lun
        }
    except (ValueError, IndexError):
        return None
