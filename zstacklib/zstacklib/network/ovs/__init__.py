# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch management module.

Provides OVS bridge/port management, DPDK support, and vNIC backend operations.

Example usage:
    from zstacklib.network.ovs import get_ovs_ctl, OvsKernelCtl

    # Kernel mode
    ctl = OvsKernelCtl()
    ctl.create_bridge('br0')
    ctl.add_port('br0', 'eth0')

    # DPDK mode (auto-detect)
    ctl = get_ovs_ctl(with_dpdk=True)
    ctl.create_bridge('br-dpdk')
"""

from __future__ import annotations

# Pure data types (no external dependencies) - import immediately
from .exceptions import (
    OvsError,
    OvsBridgeError,
    OvsPortError,
    OvsDaemonError,
    OvsDpdkError,
    OvsBondError,
    OvsConfigError,
)

from .models import (
    Bond,
    NicBackend,
    VHostAddOn,
    BondType,
    VNicType,
    OvsVersionInfo,
)

from .config import (
    CTL_BIN,
    OVS_RUN_PATH,
    LOG_PATH,
    SOCK_PATH,
    CONF_PATH,
    CONF_DB,
    DB_SOCK,
    OVS_DPDK_SUPPORT_VNIC,
    OVS_DPDK_SUPPORT_BOND_TYPE,
    BOND_CONFIG_FILE,
    SMART_NIC_CONFIG_FILE,
)

# Operation modules are lazily imported
_UTILS_EXPORTS = {
    'write_sysfs', 'read_sysfs', 'confirm_write_sysfs', 'check_bdf_format',
    'is_bdf', 'get_bdf_of_interface', 'get_interface_of_bdf', 'get_pci_id',
    'version_geq', 'get_os_release_info', 'get_numa_nodes', 'probe_module',
    'get_offload_status', 'get_mlnx_smart_nic_offload_status',
}

_BOND_EXPORTS = {'get_bond_from_file', 'get_all_bonds_from_file'}

_CONTROLLER_EXPORTS = {'OvsBaseCtl', 'OvsKernelCtl', 'get_ovs_ctl', 'is_vm_use_openvswitch'}


def __getattr__(name: str):
    """Getattr."""
    if name in _UTILS_EXPORTS:
        from . import utils
        val = getattr(utils, name)
        globals()[name] = val
        return val
    elif name in _BOND_EXPORTS:
        from . import bond
        val = getattr(bond, name)
        globals()[name] = val
        return val
    elif name == 'OvsVenv':
        from .venv import OvsVenv
        globals()[name] = OvsVenv
        return OvsVenv
    elif name == 'Ovs':
        from .daemon import Ovs
        globals()[name] = Ovs
        return Ovs
    elif name in _CONTROLLER_EXPORTS:
        from . import controller
        val = getattr(controller, name)
        globals()[name] = val
        return val
    elif name == 'OvsDpdkCtl':
        from .dpdk import OvsDpdkCtl
        globals()[name] = OvsDpdkCtl
        return OvsDpdkCtl
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'OvsError',
    'OvsBridgeError',
    'OvsPortError',
    'OvsDaemonError',
    'OvsDpdkError',
    'OvsBondError',
    'OvsConfigError',
    'Bond',
    'NicBackend',
    'VHostAddOn',
    'BondType',
    'VNicType',
    'OvsVersionInfo',
    'CTL_BIN',
    'OVS_RUN_PATH',
    'LOG_PATH',
    'SOCK_PATH',
    'CONF_PATH',
    'CONF_DB',
    'DB_SOCK',
    'OVS_DPDK_SUPPORT_VNIC',
    'OVS_DPDK_SUPPORT_BOND_TYPE',
    'BOND_CONFIG_FILE',
    'SMART_NIC_CONFIG_FILE',
    'write_sysfs',
    'read_sysfs',
    'confirm_write_sysfs',
    'check_bdf_format',
    'is_bdf',
    'get_bdf_of_interface',
    'get_interface_of_bdf',
    'get_pci_id',
    'version_geq',
    'get_os_release_info',
    'get_numa_nodes',
    'probe_module',
    'get_offload_status',
    'get_mlnx_smart_nic_offload_status',
    'get_bond_from_file',
    'get_all_bonds_from_file',
    'OvsVenv',
    'Ovs',
    'OvsBaseCtl',
    'OvsKernelCtl',
    'OvsDpdkCtl',
    'get_ovs_ctl',
    'is_vm_use_openvswitch',
]
