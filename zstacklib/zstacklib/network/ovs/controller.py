# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch controllers.

Provides OvsBaseCtl, OvsDpdkCtl, and OvsKernelCtl for managing OVS bridges and ports.
"""

from __future__ import annotations

import logging
import os
import re
import shlex

from zstacklib.utils import iproute
from zstacklib.utils import linux
from zstacklib.utils import lock
from zstacklib.utils import shell

from .bond import get_bond_from_file
from .config import CONF_PATH, CTL_BIN, SOCK_PATH
from .daemon import Ovs
from .exceptions import OvsError, OvsBridgeError, OvsPortError
from .models import BondType
from .utils import (
    get_bdf_of_interface, get_interface_of_bdf, get_pci_id, is_bdf,
    read_sysfs, write_sysfs, confirm_write_sysfs, version_geq,
)
from .venv import OvsVenv


logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_.\-]+$')
_VALID_BOND_MODES = frozenset([
    'active-backup', 'balance-slb', 'balance-tcp',
])
_VALID_LACP_VALUES = frozenset(['off', 'active', 'passive'])


def _validate_name(name: str, kind: str = "name") -> str:
    """Validate that a bridge/port/interface name contains only safe characters.

    Args:
        name: The name to validate.
        kind: Description of the name for error messages.

    Returns:
        The validated name.

    Raises:
        OvsError: If the name contains unsafe characters.
    """
    if not _SAFE_NAME_RE.match(name):
        raise OvsError(f"Invalid {kind}: {name!r} contains unsafe characters")
    return name


def _check_ovs(func):
    """Decorator to ensure OVS is running before operations."""
    def wrapper(self, *args, **kw):
        """Wrapper."""
        if not self.ovs.is_ovs_proc_running():
            self.ovs.restart()
        return func(self, *args, **kw)
    return wrapper


class OvsBaseCtl:
    """Base OVS controller with common bridge/port operations."""

    def __init__(self):
        """Init."""
        self.ovs = Ovs()
        self.venv = self.ovs.venv
        self.dpdk_sup = self.venv.is_dpdk_support()
        self.dpdk_open = False

    def list_bridges(self) -> list[str]:
        """List all OVS bridges."""
        try:
            ret = shell.call(CTL_BIN + 'list-br')
        except shell.ShellError as err:
            logger.error(f'List ovs bridges failed. {err}')
            return []
        else:
            return ret.strip().splitlines()

    def create_bridge(self, br_name: str) -> None:
        """Create an OVS bridge."""
        _validate_name(br_name, "bridge name")
        brs = self.list_bridges()
        if br_name in brs:
            logger.debug(f'Bridge {br_name} already created')
            return

        try:
            shell.check_run(
                CTL_BIN + f'add-br {br_name} -- set Bridge {br_name} datapath_type=netdev'
            )
        except Exception as err:
            logger.error(f'Create ovs bridges {br_name} failed. {err}')
            raise OvsBridgeError(br_name, str(err))

    def delete_bridge(self, *br_names: str) -> None:
        """Delete one or more OVS bridges."""
        for br_name in br_names:
            _validate_name(br_name, "bridge name")
        try:
            brs = self.list_bridges()
            for br_name in br_names:
                if br_name in brs:
                    shell.call(CTL_BIN + f'--timeout=5 del-br {br_name}')
        except Exception as err:
            logger.error(f'delete bridge failed. {err}')
            raise OvsError(str(err))

    def delete_all_bridges(self) -> None:
        """Delete all OVS bridges."""
        try:
            brs = self.list_bridges()
            for br in brs:
                shell.call(CTL_BIN + f'--timeout=5 del-br {br}')
        except Exception as err:
            logger.error(f'delete bridges failed. {err}')
            raise OvsError(str(err))

    def list_interfaces(self, br_name: str) -> list[str]:
        """List interfaces on a bridge."""
        _validate_name(br_name, "bridge name")
        try:
            ret = shell.call(CTL_BIN + f'--timeout=5 list-ifaces {br_name}')
        except Exception as err:
            logger.error(f'List interface of bridge {br_name} failed. {err}')
            return []
        else:
            return ret.strip().splitlines()

    def list_ports(self, br_name: str) -> list[str]:
        """List ports on a bridge."""
        _validate_name(br_name, "bridge name")
        try:
            ret = shell.call(CTL_BIN + f'--timeout=5 list-ports {br_name}')
        except Exception as err:
            logger.error(f'List ports of bridge {br_name} failed. {err}')
            return []
        else:
            return ret.strip().splitlines()

    def add_port(self, br_name: str, port_name: str, port_type: str | None = None, *options: str) -> None:
        """Add a port to a bridge."""
        _validate_name(br_name, "bridge name")
        _validate_name(port_name, "port name")
        try:
            if port_type:
                _validate_name(port_type, "port type")
                cmd = CTL_BIN + f'add-port {br_name} {port_name} -- set Interface {port_name} type={port_type} '
                for opt in options:
                    _validate_name(opt.split('=')[0] if '=' in opt else opt, "option")
                    cmd += f'options:{opt} '
            else:
                cmd = CTL_BIN + f'add-port {br_name} {port_name}'
            shell.call(cmd)
        except Exception as err:
            logger.error(f'Add port for bridge {br_name} failed. {err}')
            self.del_port(br_name, port_name)
            raise OvsPortError(port_name, br_name, str(err))

    def del_port(self, br_name: str, port_name: str) -> None:
        """Delete a port from a bridge."""
        _validate_name(br_name, "bridge name")
        _validate_name(port_name, "port name")
        try:
            shell.call(CTL_BIN + f'del-port {br_name} {port_name}')
        except Exception as err:
            logger.error(f'Delete port of bridge {br_name} failed. {err}')
            raise OvsPortError(port_name, br_name, str(err))

    def del_port_no_wait(self, br_name: str, port_name: str) -> None:
        """Delete a port without waiting."""
        _validate_name(br_name, "bridge name")
        _validate_name(port_name, "port name")
        try:
            shell.call(CTL_BIN + f'--no-wait del-port {br_name} {port_name}')
        except Exception as err:
            logger.error(f'Delete port of bridge {br_name} failed. {err}')
            raise OvsPortError(port_name, br_name, str(err))

    def set_port(self, port_name: str, tag: int) -> None:
        """Set VLAN tag on a port."""
        _validate_name(port_name, "port name")
        try:
            shell.call(CTL_BIN + f'set Port {port_name} tag={tag} ')
        except Exception as err:
            logger.error(f'Set port {port_name} failed. {err}')
            raise OvsPortError(port_name, msg=str(err))

    def set_interface(self, if_name: str, *options: str) -> None:
        """Set interface options."""
        _validate_name(if_name, "interface name")
        try:
            cmd = CTL_BIN + f'set Interface {if_name} '
            for opt in options:
                cmd += shlex.quote(opt) + ' '
            shell.call(cmd)
        except Exception as err:
            logger.error(f'Set interface {if_name} failed. {err}')
            raise OvsError(str(err))

    def add_outer_to_bridge(self, br_name: str, outer_name: str) -> None:
        """Add an outer interface to a bridge."""
        if outer_name not in self.list_ports(br_name):
            self.add_port(br_name, outer_name)
        else:
            logger.debug(f'Port {outer_name} already existed before add to {br_name}.')

    def delete_outer_from_bridge(self, br_name: str, outer_name: str) -> None:
        """Remove an outer interface from a bridge."""
        if outer_name in self.list_ports(br_name):
            self.del_port(br_name, outer_name)
        else:
            logger.debug(f'Port {outer_name} do not existed in {br_name}.')

    @property
    def is_dpdk_ready(self) -> bool:
        """Check if DPDK is ready to use."""
        return self.dpdk_sup and self.dpdk_open

    def _get_bond_slaves(self, bond_name: str) -> list[str]:
        """Get slave interfaces of a bond."""
        slaves_p = f'/sys/class/net/{bond_name}/bonding/slaves'

        if os.path.exists(slaves_p):
            return read_sysfs(slaves_p).split()

        dpdk_bond = get_bond_from_file(bond_name)
        if dpdk_bond is not None:
            return dpdk_bond.slaves

        return []

    def _is_kernel_bond(self, name: str) -> bool:
        """Check if an interface is a kernel bond."""
        bond_list = read_sysfs('/sys/class/net/bonding_masters').strip().split()
        return name in bond_list

    def get_bond_type(self, name: str) -> BondType:
        """Get the type of a bond/interface."""
        bond = get_bond_from_file(name)
        if bond:
            if bond.options == 'dpdkBond':
                return BondType.DpdkBond
            elif bond.options == 'ovsBond':
                return BondType.OvsBond
            elif bond.options == 'vfLag':
                if self._is_kernel_bond(name):
                    return BondType.VfLag
            else:
                raise OvsError(f'Unexpected bond type {bond.options}.')

        if self._is_kernel_bond(name):
            return BondType.KernelBond

        iface_path = f'/sys/class/net/{name}'
        if os.path.exists(iface_path):
            return BondType.NormalIface

        raise OvsError(f'Can not find interface:{name}.')

    @linux.retry(times=3, sleep_time=1)
    def config_pmd_cpu_mask_for_ovs(self, cpu_mask: str | None) -> None:
        """Configure PMD CPU mask for OVS."""
        if cpu_mask is None:
            shell.run(CTL_BIN + '--no-wait remove Open_vSwitch . other_config pmd-cpu-mask')
        else:
            shell.run(CTL_BIN + f'--no-wait set Open_vSwitch . other_config:pmd-cpu-mask={cpu_mask}')
            if not self.ovs.check_ovs_configuration('pmd-cpu-mask', cpu_mask):
                raise OvsError('Config pmd cpu mask for ovs failed.')

    @linux.retry(times=3, sleep_time=1)
    def config_lacp_fallback_ab_for_ovs(self) -> None:
        """Configure LACP fallback for OVS."""
        shell.run(CTL_BIN + '--no-wait set Open_vSwitch . other_config:lacp-fallback-ab=true')
        if not self.ovs.check_ovs_configuration('lacp-fallback-ab', 'true'):
            raise OvsError('Config lacp fallback ab for ovs failed.')

    def clear_ovs_config(self) -> None:
        """Clear OVS configuration."""
        shell.run(CTL_BIN + '--no-wait clear Open_vSwitch . other_config')

    def add_normal_if_to_br(self, interface: str, bridge_name: str) -> None:
        """Add a normal interface to bridge."""
        raise OvsError('Not implemented')

    def add_vf_lag_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a VF-LAG bond to bridge."""
        raise OvsError('Not implemented')

    def add_dpdk_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a DPDK bond to bridge."""
        raise OvsError('Not implemented')

    def add_ovs_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add an OVS bond to bridge."""
        raise OvsError('Not implemented')

    def add_kernel_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a kernel bond to bridge."""
        raise OvsError('Not implemented')

    def _add_interface_to_bridge(self, interface: str, bridge_name: str) -> None:
        """Add an interface to bridge based on its type."""
        if_type = self.get_bond_type(interface)

        if if_type == BondType.NormalIface:
            self.add_normal_if_to_br(interface, bridge_name)
        elif if_type == BondType.KernelBond:
            self.add_kernel_bond_to_br(interface, bridge_name)
        elif if_type == BondType.DpdkBond:
            self.add_dpdk_bond_to_br(interface, bridge_name)
        elif if_type == BondType.OvsBond:
            self.add_ovs_bond_to_br(interface, bridge_name)
        elif if_type == BondType.VfLag:
            self.add_vf_lag_to_br(interface, bridge_name)
        else:
            raise OvsError('Unexpected bond type.')

    def is_interface_exist(self, interface: str, bridge_name: str) -> bool:
        """Check if an interface exists on a bridge."""
        if bridge_name not in self.list_bridges():
            return False
        if interface not in self.list_ports(bridge_name):
            return False
        return True

    @lock.lock('ovs_addBridge')
    def prepare_bridge(self, interface: str, bridge_name: str) -> None:
        """Prepare a bridge with an interface."""
        if self.is_interface_exist(interface, bridge_name):
            return
        self.add_bridge(interface, bridge_name)

    @_check_ovs
    def add_bridge(self, interface: str, bridge_name: str) -> None:
        """Add a bridge with an interface."""
        created_by_me = bridge_name not in self.list_bridges()
        try:
            self.create_bridge(bridge_name)
            self._add_interface_to_bridge(interface, bridge_name)
            self.ovs.restart_switch()
        except OvsError:
            if created_by_me:
                self.delete_bridge(bridge_name)
            raise

    def _nic_backend_gc(self) -> None:
        """Garbage collect NIC backends for non-existent VMs."""
        import json as _json
        try:
            raw_string = shell.call(
                CTL_BIN + " --format=json --columns=name,external_ids find interface external_ids!={}"
            )
            parsed = _json.loads(raw_string)
            nic_and_vm_uuid = {}
            for row in parsed.get("data", []):
                # OVS JSON format: each row is a list of column values
                # name is a string, external_ids is ["map", [[key, val], ...]]
                if len(row) < 2:
                    continue
                name = row[0]
                ext_ids = row[1]
                if isinstance(ext_ids, list) and len(ext_ids) == 2 and ext_ids[0] == "map":
                    for pair in ext_ids[1]:
                        if len(pair) == 2:
                            nic_and_vm_uuid[name] = pair[1]
                            break

            files = os.listdir('/var/run/libvirt/qemu/')
            running_vm_list = set(vm.split('.')[0] for vm in files)

            for d in nic_and_vm_uuid:
                if nic_and_vm_uuid[d] not in running_vm_list:
                    self.destroy_nic_backend_no_wait(nic_and_vm_uuid[d])
        except shell.ShellError as err:
            raise OvsError(str(err))
        except (OSError, _json.JSONDecodeError):
            pass

    def reconfig_ovs_bridge(self) -> None:
        """Reconfigure all OVS bridges."""
        brs = self.list_bridges()
        for b in brs:
            if b == '':
                continue
            if not b.startswith('br-') or len(b) <= 3:
                logger.warning("Skipping bridge %r: does not match 'br-<iface>' naming", b)
                continue
            self._add_interface_to_bridge(b[3:], b)

        if len(brs) == 0:
            self.ovs.stop()
        else:
            self._nic_backend_gc()
            self.ovs.start()

    def config_dpdk_for_ovs(self) -> None:
        """Configure DPDK for OVS."""
        pass

    def convert_ovs_config_by_version(self) -> None:
        """Convert OVS config for version compatibility."""
        pass

    @lock.lock('reconfigOvs')
    def reconfig_ovs(self) -> None:
        """Reconfigure OVS with current settings."""
        try:
            if not self.ovs.is_ovs_proc_running('ovsdb-server'):
                self.ovs.start_db()

            if self.is_dpdk_ready:
                self.config_dpdk_for_ovs()
                self.convert_ovs_config_by_version()
            else:
                logger.debug('ovs do not support dpdk.')

            self.config_lacp_fallback_ab_for_ovs()
            self.reconfig_ovs_bridge()
        except OvsError:
            self.delete_all_bridges()
            self.clear_ovs_config()
            raise
        except Exception as err:
            raise OvsError(str(err))

    @_check_ovs
    def create_nic_backend(self, vm_uuid, nic):
        """Create a NIC backend for a VM."""
        raise OvsError('Not implemented')

    @_check_ovs
    def destroy_nic_backend(self, vm_uuid, specific_nic=None):
        """Destroy NIC backend for a VM."""
        raise OvsError('Not implemented')

    @_check_ovs
    def destroy_nic_backend_no_wait(self, vm_uuid, specific_nic=None):
        """Destroy NIC backend without waiting."""
        raise OvsError('Not implemented')


class OvsKernelCtl(OvsBaseCtl):
    """OVS controller for kernel-mode operations."""

    def __init__(self):
        """Init."""
        super().__init__()

    def add_normal_if_to_br(self, interface: str, bridge_name: str) -> None:
        """Add a normal interface to bridge."""
        bdf = get_bdf_of_interface(interface)
        self._change_devlink_mode(bdf)

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if interface not in self.list_ports(bridge_name):
            self.add_port(bridge_name, interface)

    def _change_devlink_mode(self, bdf: str, mode: str = 'legacy') -> None:
        """Change devlink mode (for kernel mode, use legacy)."""
        pass

    def add_kernel_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a kernel bond to bridge."""
        slaves_path = f'/sys/class/net/{bond_name}/bonding/slaves'

        if not os.path.exists(slaves_path):
            raise OvsError(f'Can not find file:{slaves_path}, please check the bond settings.')

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if bond_name not in self.list_ports(bridge_name):
            self.add_port(bridge_name, bond_name)

    def add_ovs_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add an OVS bond to bridge."""
        bond = get_bond_from_file(bond_name)
        if not bond:
            raise OvsError(f'Bond {bond_name} not found in config.')

        slaves = self._get_bond_slaves(bond_name)

        if len(slaves) < 2:
            raise OvsError(f'Number of slaves in bond:{bond.name} should >=2')

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if bond.name in self.list_ports(bridge_name):
            return

        for slave in slaves:
            _validate_name(slave, "bond slave")
        _validate_name(bond.name, "bond name")
        bond_mode = str(bond.mode)
        if bond_mode not in _VALID_BOND_MODES:
            raise OvsError(f'Invalid bond mode: {bond_mode!r}')

        cmd = CTL_BIN + f'--no-wait add-bond {bridge_name} {bond.name} '
        pf_name = ' '.join(slave for slave in slaves)

        cmd += pf_name
        cmd += f' bond_mode={bond_mode} '
        if bond_mode == 'balance-tcp':
            lacp = str(bond.lacp)
            if lacp not in _VALID_LACP_VALUES:
                raise OvsError(f'Invalid LACP value: {lacp!r}')
            cmd += f'lacp={lacp} '

        shell.call(cmd)

    def create_nic_backend(self, vm_uuid, nic):
        """Not implemented for kernel mode."""
        raise OvsError('Not implemented')

    def destroy_nic_backend(self, vm_uuid, specific_nic=None):
        """Not implemented for kernel mode."""
        raise OvsError('Not implemented')


def get_ovs_ctl(with_dpdk: bool | None = None) -> OvsBaseCtl:
    """Get the appropriate OVS controller.

    Args:
        with_dpdk: If True, return DPDK controller. If False or None, return kernel controller.

    Returns:
        OVS controller instance.
    """
    try:
        if with_dpdk:
            from .dpdk import OvsDpdkCtl
            return OvsDpdkCtl()
        else:
            return OvsKernelCtl()
    except OvsError as err:
        logger.error(f'Get Ovs controller failed. {err}')
        raise


def is_vm_use_openvswitch(vm_uuid: str) -> bool:
    """Check if a VM is using Open vSwitch."""
    import re as _re
    if not _re.match(r'^[0-9a-fA-F-]+$', vm_uuid):
        raise OvsError(f'Invalid vm_uuid: {vm_uuid}')
    try:
        vm_interface_list = shell.call(f'virsh domiflist {shlex.quote(vm_uuid)}').strip()
        if 'vhostuser' in vm_interface_list:
            return True
        return False
    except shell.ShellError:
        raise OvsError(f'Failed to check if vm {vm_uuid} attached with OpenvSwitch.')
