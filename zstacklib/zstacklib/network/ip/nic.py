# Copyright (c) ZStack.io, Inc.

"""
Network Interface Card (NIC) utility functions.

Provides functions for querying NIC information, detecting SR-IOV,
SmartNIC representors, and other hardware-related functionality.
"""

import os
import shlex
from typing import List, Optional

from zstacklib.utils import bash


def is_sriov_vf_nic(nic):
    # type: (str) -> bool
    """
    Check if a NIC is an SR-IOV Virtual Function.
    
    Args:
        nic: Network interface name
    
    Returns:
        True if the NIC is an SR-IOV VF, False otherwise
    """
    return os.path.exists("/sys/class/net/%s/device/physfn/" % nic)


def get_nic_supported_max_speed(nic):
    # type: (str) -> int
    """
    Get the maximum supported speed for a NIC.
    
    Args:
        nic: Network interface name
    
    Returns:
        Maximum speed in Mbps, or 0 if not determinable
    """
    # virtio_net doesn't report meaningful speed
    if get_nic_driver_type(nic) == "virtio_net":
        return 0
    
    # SR-IOV VFs don't report meaningful speed
    if is_sriov_vf_nic(nic):
        return 0
    
    import re
    
    r, o = bash.bash_ro("ethtool %s" % shlex.quote(nic))
    if r != 0:
        return 0
    
    in_speed = False
    speed = 0
    for line in o.strip().splitlines():
        if "supported link modes" in line.lower():
            in_speed = True
        if in_speed is True and ":" in line and "supported link modes" not in line.lower():
            break
        if in_speed:
            nums = re.findall(r"\d+\.?\d*", line)
            if len(nums) == 0:
                continue
            max_num = max([int(float(n)) for n in nums])
            if max_num > speed:
                speed = max_num
    
    if speed == 0:
        # Fall back to reading current speed from sysfs
        try:
            speed_path = "/sys/class/net/%s/speed" % nic
            if os.path.exists(speed_path):
                with open(speed_path, 'r') as f:
                    speed_str = f.read().strip()
                    speed = int(speed_str)
        except (IOError, ValueError):
            speed = 0
    
    if speed < 0:
        speed = 0
    
    return speed


def get_nic_driver_type(nic):
    # type: (str) -> str
    """
    Get the driver type for a NIC.
    
    Args:
        nic: Network interface name
    
    Returns:
        Driver name (e.g., 'virtio_net', 'ixgbe'), or empty string if not determinable
    """
    r, o = bash.bash_ro("ethtool -i %s" % shlex.quote(nic))
    if r != 0:
        return ""
    
    driver_info = None
    driver = ""
    for line in o.strip().splitlines():
        if "driver:" in line.lower():
            driver_info = line
            break
    
    if driver_info:
        parts = driver_info.split(":")
        if len(parts) == 2:
            driver = parts[1].strip()
    
    return driver


def get_namespace_id(namespace_name):
    # type: (str) -> int
    """
    Get the ID for a network namespace.
    
    Args:
        namespace_name: Name of the network namespace
    
    Returns:
        Namespace ID (int)
    """
    NAMESPACE_NAME = namespace_name
    out = bash.bash_errorout(
        "ip netns list-id | grep -w {{NAMESPACE_NAME}} | awk '{print $2}'"
    ).strip()
    
    if not out:
        out = bash.bash_errorout("ip netns list-id | awk 'END{print $2}'").strip()
        if not out:
            return 0
        return int(out) + 1
    
    return int(out)


def get_smart_nic_pcis():
    # type: () -> List[str]
    """
    Get PCI addresses of SmartNIC devices (e.g., Mellanox).
    
    Returns:
        List of PCI addresses
    """
    nic_pcis = []  # type: List[str]
    pci_devices = bash.bash_o(
        "lspci -D -m | grep Mellanox | grep -v Virtual"
    ).splitlines()
    
    for pci_device in pci_devices:
        pci_info = pci_device.split(" ")
        if pci_info:
            nic_pcis.append(pci_info[0])
    
    return nic_pcis


def get_smart_nics_interfaces(nic_pcis=None):
    # type: (Optional[List[str]]) -> List[List[str]]
    """
    Get network interfaces for SmartNIC devices.
    
    Args:
        nic_pcis: List of PCI addresses (if None, auto-detect)
    
    Returns:
        List of interface lists, one per PCI device
    """
    nics_interfaces = []  # type: List[List[str]]
    
    if nic_pcis is None:
        nic_pcis = get_smart_nic_pcis()
    
    for nic_pci in nic_pcis:
        interface_path = os.path.join("/sys/bus/pci/devices/%s/net" % nic_pci)
        if not os.path.exists(interface_path):
            break
        interface_list = os.listdir(interface_path)
        nics_interfaces.append(interface_list)
    
    return nics_interfaces


def get_smart_nic_representors():
    # type: () -> List[str]
    """
    Get SmartNIC VF representor interfaces.
    
    Representors are virtual interfaces that represent VFs in hardware offload mode.
    
    Returns:
        List of representor interface names
    """
    def is_representor(interface_name, interfaces_number):
        # type: (str, int) -> bool
        """Check if an interface is a VF representor."""
        if interfaces_number == 1:
            # Special case for Mellanox ConnectX-5
            # If only one interface under the PCI device, it's not a representor
            return False
        
        # Check phys_port_name for "vf" prefix
        phy_name_path = "/sys/class/net/%s/phys_port_name" % interface_name
        if os.path.exists(phy_name_path):
            try:
                with open(phy_name_path, 'r') as f:
                    phys_port_name = f.read().strip()
                    if "vf" in phys_port_name:
                        return True
                    else:
                        return False
            except IOError:
                pass
        
        # Fall back to checking for phy_stats (physical interfaces have this)
        physical_interface_path = "/sys/class/net/%s/phy_stats" % interface_name
        if os.path.exists(physical_interface_path):
            return False
        return True
    
    nic_representors = []  # type: List[str]
    
    try:
        nics_interfaces = get_smart_nics_interfaces()
        for nic_interfaces in nics_interfaces:
            nic_interfaces_number = len(nic_interfaces)
            for nic_interface in nic_interfaces:
                if is_representor(nic_interface, nic_interfaces_number):
                    nic_representors.append(nic_interface)
    except Exception:
        return []
    
    return nic_representors


def get_host_physical_nics():
    # type: () -> List[str]
    """
    Get list of physical NICs on the host.
    
    Excludes:
    - Virtual interfaces
    - SR-IOV VF interfaces
    - USB interfaces
    - SmartNIC VF representors
    - Bridge interfaces
    - Virtual NIC interfaces (vnic*, outer*, br_*)
    
    Returns:
        List of physical NIC interface names
    """
    # Find all physical NICs (not virtual or USB)
    nic_all_physical = bash.bash_o(
        "find /sys/class/net -type l -not \\( -lname '*virtual*' -or -lname '*usb*' \\) -printf '%f\\n'"
    ).splitlines()
    
    if not nic_all_physical:
        return []
    
    # Exclude SR-IOV VF NICs
    nic_without_sriov = []  # type: List[str]
    for nic in nic_all_physical:
        if not is_sriov_vf_nic(nic):
            nic_without_sriov.append(nic)
    
    # Exclude virtual/management NICs
    nic_without_virtual = []  # type: List[str]
    for nic in nic_without_sriov:
        flag = True
        if 'vnic' in nic:
            flag = False
        if 'outer' in nic:
            flag = False
        if 'br_' in nic:
            flag = False
        if flag:
            nic_without_virtual.append(nic)
    
    # Exclude SmartNIC representors
    nic_without_smart_nic_representors = []  # type: List[str]
    smart_nic_representors = get_smart_nic_representors()
    for nic in nic_without_virtual:
        if nic not in smart_nic_representors:
            nic_without_smart_nic_representors.append(nic)
    
    return nic_without_smart_nic_representors


# Backward compatibility aliases
is_sriovVf_nic = is_sriov_vf_nic
get_host_physicl_nics = get_host_physical_nics
