# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch models and enums.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique


@unique
class BondType(Enum):
    """Bond interface type."""
    NormalIface = 0
    KernelBond = 1
    DpdkBond = 2
    OvsBond = 3
    VfLag = 4


@unique
class VNicType(Enum):
    """Virtual NIC type for DPDK."""
    vDPA = 0
    dpdkvhostuserclient = 1


@dataclass
class Bond:
    """DPDK/OVS bond configuration.

    Attributes:
        name: Bond interface name.
        policy: Transmission policy (for balance-xor mode).
        mode: Bond mode (0-6).
        slaves: List of slave interface names or BDFs.
        lacp: LACP setting ('off', 'active', 'passive').
        id: Bond ID number.
        options: Bond type ('dpdkBond', 'ovsBond', 'vfLag').
    """
    name: str = 'default'
    policy: str | None = None
    mode: int = 1
    slaves: list[str] = field(default_factory=list)
    lacp: str = 'off'
    id: int = 0
    options: str = 'dpdkBond'


@dataclass
class VHostAddOn:
    """vHost additional configuration.

    Attributes:
        queue_num: Number of queues.
    """
    queue_num: int | None = None


@dataclass
class NicBackend:
    """Virtual NIC backend configuration.

    Attributes:
        bridge_name: OVS bridge name.
        nic_internal_name: Internal name of the vNIC.
        physical_interface: Physical interface name.
        type: vNIC type ('vDPA', 'dpdkvhostuserclient', 'vNic').
        pci_device_address: PCI BDF for vDPA.
        vlan_id: VLAN tag (optional).
        vhost_addon: Additional vhost configuration.
    """
    bridge_name: str = ''
    nic_internal_name: str = ''
    physical_interface: str = ''
    type: str = 'vNic'
    pci_device_address: str = ''
    vlan_id: int | None = None
    vhost_addon: VHostAddOn | None = None


@dataclass
class OvsVersionInfo:
    """OVS version information.

    Attributes:
        ofed_ver: Mellanox OFED driver version.
        vswitch_ver: ovs-vswitchd version.
        dpdk_ver: DPDK version.
        ovsdb_ver: ovsdb-server version.
    """
    ofed_ver: str = 'unknown'
    vswitch_ver: str = 'unknown'
    dpdk_ver: str = 'unknown'
    ovsdb_ver: str = 'unknown'

    def is_dpdk_support(self) -> bool:
        """Check if DPDK is supported."""
        return self.dpdk_ver != 'unknown'

    def is_mellanox_support(self) -> bool:
        """Check if Mellanox OFED is available."""
        return self.ofed_ver != 'unknown'
