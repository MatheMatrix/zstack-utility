# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch utility functions.

Provides helper functions for sysfs operations, BDF handling, and version comparison.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import yaml

from zstacklib.utils import shell

from .config import CONF_PATH, SMART_NIC_CONFIG_FILE
from .exceptions import OvsError


logger = logging.getLogger(__name__)


# Sysfs operations

def write_sysfs(path: str, value: str, suppress_raise: bool = False) -> None:
    """Write a value to a sysfs file.

    Args:
        path: Path to the sysfs file.
        value: Value to write.
        suppress_raise: If True, log warning instead of raising.

    Raises:
        OvsError: If write fails and suppress_raise is False.
    """
    try:
        with open(path, 'w') as f:
            f.write(str(value))
    except Exception as e:
        logger.warning(str(e))
        if not suppress_raise:
            raise OvsError(str(e))


def read_sysfs(path: str, suppress_raise: bool = False) -> str | None:
    """Read a value from a sysfs file.

    Args:
        path: Path to the sysfs file.
        suppress_raise: If True, return None instead of raising.

    Returns:
        Content of the file, or None if read fails and suppress_raise is True.

    Raises:
        OvsError: If read fails and suppress_raise is False.
    """
    ret = None
    try:
        with open(path, 'r') as f:
            ret = f.read().rstrip()
    except Exception as e:
        logger.warning(str(e))
        if not suppress_raise:
            raise OvsError(str(e))
    return ret


def confirm_write_sysfs(path: str, value: str, retries: int = 10, sleep_time: float = 5) -> None:
    """Write to sysfs and verify the write succeeded.

    Args:
        path: Path to the sysfs file.
        value: Value to write.
        retries: Number of retry attempts.
        sleep_time: Sleep time between retries.

    Raises:
        OvsError: If write or verification fails after all retries.
    """
    from zstacklib.utils.linux import retry as linux_retry

    @linux_retry(times=retries, sleep_time=sleep_time)
    def _do_write():
        """Do write."""
        write_sysfs(path, value)
        if read_sysfs(path) != value:
            raise OvsError('write sysfs failed')

    _do_write()


# BDF (Bus Device Function) operations

def check_bdf_format(bdf_str: str) -> None:
    """Validate a PCI BDF (Bus:Device.Function) format.

    Args:
        bdf_str: BDF string like '0000:65:00.1'.

    Raises:
        OvsError: If format is invalid.
    """
    pattern = re.compile(r'\d{4}(:[0-9a-fA-F]{2}){2}.\d$')
    ret = re.match(pattern, bdf_str)
    if ret is not None:
        if ret.span()[1] == 12:
            return
    raise OvsError(f'BDF format error. bdf:{bdf_str}')


def is_bdf(bdf_str: str) -> bool:
    """Check if a string is a valid BDF format.

    Args:
        bdf_str: String to check.

    Returns:
        True if valid BDF format.
    """
    try:
        check_bdf_format(bdf_str)
        return True
    except OvsError:
        return False


def get_bdf_of_interface(if_name: str) -> str:
    """Get the PCI BDF of a network interface.

    Args:
        if_name: Network interface name.

    Returns:
        BDF string like '0000:65:00.1'.

    Raises:
        OvsError: If interface not found.
    """
    try:
        pci_path = f'/sys/class/net/{if_name}/device'
        if not os.path.exists(pci_path):
            raise OvsError(f'No such device:{pci_path}')
        bdf = os.path.realpath(pci_path).split('/')[-1]
        return bdf
    except Exception as err:
        raise OvsError(str(err))


def get_interface_of_bdf(bdf: str) -> str:
    """Get the network interface name for a PCI BDF.

    Args:
        bdf: PCI BDF string.

    Returns:
        Network interface name.

    Raises:
        OvsError: If interface not found.
    """
    try:
        check_bdf_format(bdf)
        net_path = f'/sys/bus/pci/devices/{bdf}/net'
        if_name = os.listdir(net_path)[0].split('_')[0]
        return if_name
    except Exception as err:
        raise OvsError(str(err))


def get_pci_id(bdf_or_if: str) -> str:
    """Get PCI ID (vendor:device) for a BDF or interface.

    Args:
        bdf_or_if: BDF string or interface name.

    Returns:
        PCI ID as 'vendordevice' (e.g., '15b3101d').
    """
    vendor_path = '/sys/class/net/{}/device/vendor'
    device_path = '/sys/class/net/{}/device/device'

    if is_bdf(bdf_or_if):
        vendor_path = '/sys/bus/pci/devices/{}/vendor'
        device_path = '/sys/bus/pci/devices/{}/device'

    vendor_id = read_sysfs(vendor_path.format(bdf_or_if))[2:6]
    device_id = read_sysfs(device_path.format(bdf_or_if))[2:6]

    return vendor_id + device_id


# Version comparison

def version_geq(v1: str, v2: str) -> bool:
    """Compare (dot-separated) version numbers.

    Args:
        v1: First version string.
        v2: Second version string.

    Returns:
        True if v1 >= v2.
    """
    v1_parts = v1.split('.')
    v2_parts = v2.split('.')
    v_len = min(len(v1_parts), len(v2_parts))

    for i in range(v_len):
        if int(v1_parts[i]) < int(v2_parts[i]):
            return False
        elif int(v1_parts[i]) > int(v2_parts[i]):
            return True
    return True


# OS and hardware info

def get_os_release_info() -> dict[str, str]:
    """Get OS release information from /etc/os-release.

    Returns:
        Dictionary with OS info (ID, VERSION_ID, etc.).
    """
    os_release = {}
    with open('/etc/os-release', 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('=')
            os_release[parts[0].strip()] = parts[1].strip('"')
    return os_release


def get_numa_nodes() -> int:
    """Get the number of NUMA nodes.

    Returns:
        Number of NUMA nodes.

    Raises:
        OvsError: If no NUMA nodes found.
    """
    numa_paths = glob.glob('/sys/devices/system/node/node*/')
    if len(numa_paths) < 1:
        raise OvsError('Get numa nodes failed.')
    return len(numa_paths)


def probe_module(module_name: str) -> None:
    """Load a kernel module.

    Args:
        module_name: Module name to load.

    Raises:
        OvsError: If module cannot be loaded.
    """
    ret = shell.run(f'modprobe {module_name}')
    if ret != 0:
        raise OvsError(f'Can not find module:{module_name}.')


def get_offload_status(interface_name: str) -> str | None:
    """Get the offload status for a network interface.

    Args:
        interface_name: Network interface name.

    Returns:
        Offload status string, or None if not available.
    """
    try:
        pci_id = get_pci_id(interface_name)
        offload_status = get_mlnx_smart_nic_offload_status()
        if pci_id in offload_status:
            return offload_status[pci_id]
        return None
    except Exception as err:
        logger.debug(f'Get offload status failed. {err}')
        return None


def get_mlnx_smart_nic_offload_status() -> dict[str, str]:
    """Get Mellanox SmartNIC offload status from config file.

    Returns:
        Dictionary mapping PCI ID to offload status.

    Raises:
        OvsError: If config file not found.
    """
    nic_info_path = os.path.join(CONF_PATH, SMART_NIC_CONFIG_FILE)
    if not os.path.exists(nic_info_path):
        raise OvsError(f'no such file:{nic_info_path}')

    with open(nic_info_path, 'r') as f:
        data = yaml.safe_load(f)

    offload_status = {}
    for i in data:
        offload_status[str(i['nic']['vendor_device'])] = '|'.join(
            str(x) for x in i['nic']['offloadstatus']
        )
    return offload_status
