# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch DPDK controller.

Provides OvsDpdkCtl for DPDK-specific OVS operations.
"""

from __future__ import annotations

import logging
import os
import time

from zstacklib.utils import iproute
from zstacklib.utils import linux
from zstacklib.utils import lock
from zstacklib.utils import shell

from .bond import get_bond_from_file
from .config import CONF_PATH, CTL_BIN, SOCK_PATH
from .controller import OvsBaseCtl, _check_ovs
from .exceptions import OvsError, OvsBridgeError, OvsDpdkError
from .utils import (
    get_bdf_of_interface, get_interface_of_bdf, get_pci_id, is_bdf,
    read_sysfs, write_sysfs, confirm_write_sysfs, probe_module, version_geq,
)


logger = logging.getLogger(__name__)


class OvsDpdkCtl(OvsBaseCtl):
    """OVS controller for DPDK mode operations.

    Handles DPDK-specific functionality including:
    - vDPA and dpdkvhostuserclient backends
    - SR-IOV VF management
    - Devlink mode switching
    - DPDK bond configuration
    """

    def __init__(self):
        super().__init__()
        self.dpdk_open = True
        self._init_dpdk()

    def _init_dpdk(self) -> None:
        """Initialize DPDK if not already done."""
        if self.ovs._get_dpdk_init_states():
            return
        self._start_openvswitch_database()
        self._config_openvswitch_if_ready()

    def _start_openvswitch_database(self) -> None:
        """Start ovsdb-server if not running."""
        if not self.ovs.is_ovs_proc_running('ovsdb-server'):
            self.ovs.start_db()

    def _config_openvswitch_if_ready(self) -> None:
        """Configure DPDK if ready."""
        if self.is_dpdk_ready:
            self.config_dpdk_for_ovs()
            self.convert_ovs_config_by_version()

    # SR-IOV operations

    def _clear_sriov_vfs(self, bdf: str) -> None:
        """Clear all SR-IOV VFs for a device."""
        numvfs = f'/sys/bus/pci/devices/{bdf}/sriov_numvfs'
        confirm_write_sysfs(numvfs, '0')

    def _split_sriov_to_max(self, bdf: str) -> None:
        """Create maximum number of SR-IOV VFs."""
        numvfs = f'/sys/bus/pci/devices/{bdf}/sriov_numvfs'
        totalvfs = read_sysfs(f'/sys/bus/pci/devices/{bdf}/sriov_totalvfs')
        confirm_write_sysfs(numvfs, totalvfs)

    @linux.retry(times=3, sleep_time=3)
    def _resplit_vfs(self, bdf: str) -> None:
        """Resplit VFs (clear and recreate)."""
        try:
            self._clear_sriov_vfs(bdf)
            self._split_sriov_to_max(bdf)
        except OvsError as err:
            raise OvsError(f'resplit vfs failed. {err}')

    def _get_vf_to_bdf_map(self, bdf: str) -> dict[str, str]:
        """Get mapping of virtfnX to BDF."""
        device_path = f'/sys/bus/pci/devices/{bdf}/'
        vf_to_bdf = {}

        for vf in os.listdir(device_path):
            if vf.startswith('virtfn'):
                vf_bdf = os.path.realpath(device_path + vf).split('/')[-1]
                vf_to_bdf[vf] = vf_bdf

        return vf_to_bdf

    def _unbind_vfs(self, pf_bdf: str) -> None:
        """Unbind all VFs from their driver."""
        device_path = f'/sys/bus/pci/devices/{pf_bdf}/'
        unbind_path = f'/sys/bus/pci/devices/{pf_bdf}/driver/unbind'

        vf_to_bdf = self._get_vf_to_bdf_map(pf_bdf)
        for vf in vf_to_bdf:
            write_sysfs(unbind_path, vf_to_bdf[vf])
            # Wait for unbind to complete
            for _ in range(5):
                if os.path.exists(os.path.join(device_path, vf, 'driver')):
                    time.sleep(0.5)

    def _bind_vfs(self, pf_bdf: str) -> None:
        """Bind all VFs to their driver."""
        device_path = f'/sys/bus/pci/devices/{pf_bdf}/'
        bind_path = f'/sys/bus/pci/devices/{pf_bdf}/driver/bind'

        vf_to_bdf = self._get_vf_to_bdf_map(pf_bdf)
        for vf in vf_to_bdf:
            if not os.path.exists(os.path.join(device_path, vf, 'driver')):
                write_sysfs(bind_path, vf_to_bdf[vf], True)
            # Wait for bind to complete
            for _ in range(5):
                if not os.path.exists(os.path.join(device_path, vf, 'driver')):
                    time.sleep(0.5)

    def _change_devlink_mode(self, bdf: str, mode: str = 'switchdev') -> None:
        """Change devlink eswitch mode."""
        try:
            devlink_mode = 'legacy'
            ret = shell.call(f'devlink dev eswitch show pci/{bdf}')
            if 'switchdev' in ret:
                devlink_mode = 'switchdev'

            numvfs = f'/sys/bus/pci/devices/{bdf}/sriov_numvfs'
            totalvfs = read_sysfs(f'/sys/bus/pci/devices/{bdf}/sriov_totalvfs')

            if devlink_mode == mode and read_sysfs(numvfs, True) == totalvfs:
                return

            if_name = get_interface_of_bdf(bdf)
            iproute.set_link_down_no_error(if_name)

            # Unbind VFs before changing devlink mode
            self._unbind_vfs(bdf)
            shell.call(f'devlink dev eswitch set pci/{bdf} mode {mode}')
            ret = shell.call(f'devlink dev eswitch show pci/{bdf}')
            if mode not in ret:
                raise OvsDpdkError(f'devlink dev set eswitch mode {mode} for {bdf} failed.')

            self._bind_vfs(bdf)
            iproute.set_link_up_no_error(if_name)
            logger.debug(f'set {mode} for {bdf} success.')
        except OvsError:
            logger.error(f'Change devlink mode for device bdf:{bdf} failed.')
            raise

    # DPDK configuration

    def _get_ovs_dpdk_extra(self) -> str:
        """Get current DPDK extra options."""
        try:
            dpdk_extra = shell.call(
                CTL_BIN + 'get Open_vSwitch . other_config:dpdk-extra'
            ).strip().strip('\n').strip('"')
            return dpdk_extra
        except Exception:
            return ''

    def _config_dpdk_extra_for_ovs(self, bdf: str) -> None:
        """Configure DPDK extra options for a device."""
        try:
            dpdk_extra = self._get_ovs_dpdk_extra()
            if bdf in dpdk_extra:
                return

            if version_geq(self.venv.version_info.dpdk_ver, '20.11'):
                dpdk_extra += f'-a {bdf},representor=[0-127],dv_flow_en=1,dv_esw_en=1 '
            else:
                dpdk_extra += f'-w {bdf},representor=[0-127],dv_flow_en=1,dv_esw_en=1 '

            shell.run(
                CTL_BIN + f'--no-wait set Open_vSwitch . other_config:dpdk-extra="{dpdk_extra}"'
            )
        except shell.ShellError as err:
            raise OvsDpdkError(f'Set dpdk white list for pci:{bdf} failed, {err}')

    # Interface operations

    def add_normal_if_to_br(self, interface: str, bridge_name: str) -> None:
        """Add a normal interface to bridge with DPDK."""
        bdf = get_bdf_of_interface(interface)
        self._change_devlink_mode(bdf)
        self._config_dpdk_extra_for_ovs(bdf)

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if interface not in self.list_ports(bridge_name):
            self.add_port(bridge_name, interface, 'dpdk', f'dpdk-devargs={bdf}')

    def add_vf_lag_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a VF-LAG bond to bridge."""
        slaves_path = f'/sys/class/net/{bond_name}/bonding/slaves'

        if not os.path.exists(slaves_path):
            raise OvsError(f'Can not find file:{slaves_path}, please check the bond settings.')

        interfaces = self._get_bond_slaves(bond_name)
        interface_bdfs = [get_bdf_of_interface(i) for i in interfaces]
        interface_bds = set()
        interface_pci_ids = set()

        for bdf in interface_bdfs:
            interface_bds.add(bdf.split('.')[0])
            interface_pci_ids.add(get_pci_id(bdf))

        if len(interface_pci_ids) != 1 or len(interface_bds) != 1:
            raise OvsError('The pfs under vflag should come from the same nic.')

        pci_id = list(interface_pci_ids)[0]
        if pci_id not in self.venv.offload_status:
            raise OvsError(f'Device:{pci_id} not in support vf lag list.')

        for bdf in interface_bdfs:
            self._change_devlink_mode(bdf)
            self._config_dpdk_extra_for_ovs(bdf)

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if bond_name not in self.list_ports(bridge_name):
            self.add_port(
                bridge_name, bond_name, 'dpdk',
                f'dpdk-devargs={interface_bdfs[0]}',
                'dpdklsc-interrupt=true'
            )

    def _bind_dpdk_driver_to_device(self, pci_num: str, drv_name: str | None = None) -> None:
        """Bind DPDK driver to a PCI device."""
        if drv_name is None:
            drv_name = 'vfio-pci'

        bind_path = f'/sys/bus/pci/drivers/{drv_name}/bind'
        unbind_path = f'/sys/bus/pci/devices/{pci_num}/driver/unbind'
        override_path = f'/sys/bus/pci/devices/{pci_num}/driver_override'
        newid_path = f'/sys/bus/pci/drivers/{drv_name}/new_id'
        device_driver_path = f'/sys/bus/pci/drivers/{drv_name}/{pci_num}'

        # Check if driver module exists
        if not os.path.exists(bind_path):
            probe_module(drv_name)
            if not os.path.exists(bind_path):
                logger.warn(f'can not probe module {drv_name}.')

        # Already using driver
        if os.path.exists(device_driver_path):
            return

        # Unbind old driver if exists
        if os.path.exists(unbind_path):
            write_sysfs(unbind_path, str(pci_num))
            time.sleep(0.5)

        # Use driver_override for kernel >= 3.15
        if os.path.exists(override_path):
            write_sysfs(override_path, str(drv_name))
        else:
            vd = get_pci_id(pci_num)
            write_sysfs(newid_path, vd[:4] + ' ' + vd[4:])

        # Do the bind
        for _ in range(3):
            if not os.path.exists(device_driver_path):
                write_sysfs(bind_path, str(pci_num))
            else:
                break

        # Clear override
        if os.path.exists(override_path):
            write_sysfs(override_path, '\00')

    def _prepare_slaves(self, slaves: list[str]) -> None:
        """Prepare slave devices for DPDK."""
        for bdf in slaves:
            if get_pci_id(bdf) not in self.venv.offload_status:
                self._bind_dpdk_driver_to_device(bdf)
            else:
                self._change_devlink_mode(bdf)
            self._config_dpdk_extra_for_ovs(bdf)

    def _convert_if_to_bdf(self, raw_slaves: list[str]) -> list[str]:
        """Convert interface names to BDFs."""
        slaves = []
        for i in raw_slaves:
            if not is_bdf(i):
                slaves.append(get_bdf_of_interface(i))
            else:
                slaves.append(i)
        return slaves

    def add_dpdk_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add a DPDK bond to bridge."""
        bond = get_bond_from_file(bond_name)
        if not bond:
            raise OvsError(f'Bond {bond_name} not found in config.')

        slaves = self._convert_if_to_bdf(bond.slaves)

        if len(slaves) < 2:
            raise OvsError(f'Number of slaves in dpdk bond:{bond.name} should >=2')

        self._prepare_slaves(slaves)

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if bond.name in self.list_ports(bridge_name):
            return

        # Build DPDK devargs for bond
        dpdk_devargs = f'eth_bond{bond.id},mode={bond.mode}'
        for pci in bond.slaves:
            dpdk_devargs += f',slave={pci}'

        # Add xmit_policy for balance-xor mode
        if bond.mode == 2 and bond.policy is not None:
            dpdk_devargs += f',xmit_policy={bond.policy}'

        self.add_port(bridge_name, bond.name, 'dpdk', f'dpdk-devargs={dpdk_devargs}')

    def add_ovs_bond_to_br(self, bond_name: str, bridge_name: str) -> None:
        """Add an OVS bond to bridge."""
        bond = get_bond_from_file(bond_name)
        if not bond:
            raise OvsError(f'Bond {bond_name} not found in config.')

        slaves = self._convert_if_to_bdf(bond.slaves)

        if len(slaves) < 2:
            raise OvsError(f'Number of slaves in dpdk bond:{bond.name} should >=2')

        self._prepare_slaves(slaves)

        if bridge_name not in self.list_bridges():
            raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

        if bond.name in self.list_ports(bridge_name):
            return

        # Build command
        cmd = CTL_BIN + f'--no-wait add-bond {bridge_name} {bond.name} '

        pf_name = ''
        ifce_set = ''
        count = 0
        for pci in slaves:
            pf_name += f'{bond.name}_pf{count} '
            ifce_set += f'-- set Interface {bond.name}_pf{count} type=dpdk options:dpdk-devargs={pci} '
            count += 1

        cmd += pf_name
        cmd += f'bond_mode={bond.mode} '
        if bond.mode == 'balance-tcp':
            cmd += f'lacp={bond.lacp} '
        cmd += ifce_set

        shell.call(cmd)

    @linux.retry(times=3, sleep_time=1)
    def config_dpdk_for_ovs(self) -> None:
        """Configure DPDK for OVS."""
        if not self.dpdk_sup:
            raise OvsDpdkError('This openvswitch do not support dpdk.')

        shell.run(CTL_BIN + '--no-wait set Open_vSwitch . other_config:hw-offload=true')
        shell.run(CTL_BIN + '--no-wait set Open_vSwitch . other_config:dpdk-init=true')

        # Allocate socket memory
        mem_size = self.venv.nr_hugepages * self.venv.hugepage_size // 1024  # MB
        dpdk_socket_mem = ','.join([str(mem_size) for _ in range(self.venv.numa_nodes)])

        cmd = f'--no-wait set Open_vSwitch . other_config:dpdk-socket-mem={dpdk_socket_mem}'
        shell.run(CTL_BIN + cmd)

        if not self.ovs.check_ovs_configuration('hw-offload', 'true') or \
           not self.ovs.check_ovs_configuration('dpdk-init', 'true') or \
           not self.ovs.check_ovs_configuration('dpdk-socket-mem', dpdk_socket_mem):
            raise OvsDpdkError('Config dpdk for ovs failed.')

    @linux.retry(times=3, sleep_time=1)
    def convert_ovs_config_by_version(self, version: str | None = None) -> None:
        """Convert OVS config for version compatibility."""
        if version is None:
            version = self.venv.version_info.dpdk_ver

        dpdk_extra = self._get_ovs_dpdk_extra()

        if dpdk_extra == '':
            return

        if version_geq(version, '20.11'):
            dpdk_extra = dpdk_extra.replace('-w', '-a')
            dpdk_extra = dpdk_extra.replace('dv_xmeta_en=1', '')
        else:
            dpdk_extra = dpdk_extra.replace('-a', '-w')

        ret = shell.run(
            CTL_BIN + f'--no-wait set Open_vSwitch . other_config:dpdk-extra="{dpdk_extra}"'
        )
        if ret != 0:
            raise OvsDpdkError(f'Convert ovs configuration by version failed. version:{version}')

        if not self.ovs.check_ovs_configuration('dpdk-extra', dpdk_extra):
            raise OvsDpdkError('Set ovs dpdk-extra configuration failed.')

    # vNIC backend operations

    def _clean_socket(self, sock_path: str) -> None:
        """Clean up a socket file."""
        try:
            os.remove(sock_path)
        except OSError:
            if not os.path.exists(sock_path):
                return
            raise

    def create_vdpa(self, nic, sock_path: str) -> None:
        """Create a vDPA port."""
        bridge_name = nic.bridge_name
        nic_internal_name = nic.nic_internal_name
        vf_pci = nic.pci_device_address
        queue_num = str(nic.vhost_addon.queue_num) if nic.vhost_addon and nic.vhost_addon.queue_num else '1'

        pf_sysinfo = f'/sys/bus/pci/devices/{vf_pci}/physfn'
        pf_pci = os.path.realpath(pf_sysinfo).split('/')[-1]

        try:
            representor = None
            tmp_list = os.listdir(pf_sysinfo)
            for vf in tmp_list:
                if vf.startswith('virtfn') and vf_pci == os.path.realpath(pf_sysinfo + '/' + vf).split('/')[-1]:
                    representor = vf[6:]

            if representor is None:
                raise OvsError(f'vf:{vf_pci} is not the virtual function of pf:{pf_pci}')

            # Check if VF is already in use
            escaped_vf_pci = vf_pci.replace(':', r'\:')
            s = shell.call(
                CTL_BIN + f"--columns=name find interface options:vdpa-accelerator-devargs='{escaped_vf_pci}'"
            )
            if 'name' in s:
                vnic_in_use = s.strip().strip('"')
                raise OvsError(f'vf:{vf_pci} was already used by vnic:{vnic_in_use}')

            self.add_port(
                bridge_name, nic_internal_name, 'dpdkvdpa',
                f'vdpa-socket-path={sock_path}',
                f'vdpa-accelerator-devargs={vf_pci}',
                f'dpdk-devargs={pf_pci},representor=[{representor}]',
                'vdpa-max-queues=8',
                f'n_rxq={queue_num}',
                'vdpa-sw=true'
            )
        except shell.ShellError as err:
            raise OvsError(str(err))

    def create_dpdk_vhostuser_client(self, nic, sock_path: str) -> None:
        """Create a dpdkvhostuserclient port."""
        bridge_name = nic.bridge_name
        nic_internal_name = nic.nic_internal_name
        self.add_port(bridge_name, nic_internal_name, 'dpdkvhostuserclient',
                      f'vhost-server-path={sock_path}')

    def _do_create_backend(self, vm_uuid: str, nic, sock_path: str) -> None:
        """Create NIC backend based on type."""
        vlan_id = nic.vlan_id
        vnic_name = nic.nic_internal_name
        nic_type = nic.type

        self._clean_socket(sock_path)

        if nic_type == 'vNic':
            self.add_port(nic.bridge_name, vnic_name)
        elif self.is_dpdk_ready:
            if nic_type == 'vDPA':
                self.create_vdpa(nic, sock_path)
            elif nic_type == 'dpdkvhostuserclient':
                self.create_dpdk_vhostuser_client(nic, sock_path)
            else:
                raise OvsError(f'Do not support vnic type:{nic_type}')
        else:
            raise OvsError(f'Do not support vnic type:{nic_type}')

        if vlan_id is not None:
            self.set_port(vnic_name, vlan_id)

        self.set_interface(vnic_name, f'external_ids:vm-id={vm_uuid}')

    @lock.lock('ovs-createNicBackend')
    def create_nic_backend(self, vm_uuid: str, nic) -> str:
        """Create a NIC backend for a VM."""
        bridge_name = nic.bridge_name
        pnic_name = nic.physical_interface
        nic_type = nic.type
        vnic_name = nic.nic_internal_name
        sock_dir_path = os.path.join(SOCK_PATH, nic_type.lower(), vm_uuid)
        sock_path = os.path.join(sock_dir_path, vnic_name)

        try:
            if bridge_name not in self.list_bridges():
                raise OvsBridgeError(bridge_name, 'Can not find bridge in ovs.')

            cur_ports = self.list_ports(bridge_name)
            if pnic_name not in cur_ports:
                raise OvsError(f'Port:{pnic_name} does not exist. Please create it first.')

            if not os.path.exists(sock_dir_path):
                os.makedirs(sock_dir_path, 0o755)

            if 'vDPA' in nic_type:
                options = 'vdpa-socket-path'
            elif 'dpdkvhostuserclient' in nic_type:
                options = 'vhost-server-path'
            else:
                raise OvsError(f'Unsupported vnic type:{nic_type}')

            if vnic_name in cur_ports:
                s = shell.call(
                    CTL_BIN + f'get Interface {vnic_name} options:{options}'
                ).strip()[1:-1]

                if s != '' and sock_path != s:
                    raise OvsError('same vnic in different vm.')
            else:
                self._do_create_backend(vm_uuid, nic, sock_path)

            return sock_path
        except shell.ShellError as err:
            raise OvsError(f'nic interface {vnic_name} maybe not a {nic_type} type. {err}')
        except OSError as err:
            raise OvsError(str(err))

    def _list_ifaces_by_vm_uuid(self, vm_uuid: str) -> list[str]:
        """List interfaces by VM UUID."""
        try:
            interfaces = shell.call(
                CTL_BIN + f"--columns=name find interface external_ids:vm-id={vm_uuid} | grep name | cut -d ':' -f2 | tr -d ' '"
            )
            return interfaces.strip().splitlines()
        except shell.ShellError as err:
            raise OvsError(f'Find interface by vm uuid:{vm_uuid} failed. {err}')

    def _get_interfaces_sock_by_name(self, nic_name: str) -> str:
        """Get socket path for an interface."""
        try:
            sock_path = ''
            nic_type = shell.call(CTL_BIN + f'get interface {nic_name} type').strip()

            if 'dpdkvdpa' in nic_type:
                options = 'vdpa-socket-path'
            elif 'dpdkvhostuserclient' in nic_type:
                options = 'vhost-server-path'
            else:
                return sock_path

            sock_path = shell.call(
                CTL_BIN + f'get interface {nic_name} options:{options}'
            ).strip().strip('"')
            return sock_path
        except shell.ShellError as err:
            raise OvsError(f'Get interface sock path by name:{nic_name} failed. {err}')

    @lock.lock('ovs-destoryNicBackend')
    def destroy_nic_backend(self, vm_uuid: str, specific_nic: str | None = None) -> str:
        """Destroy NIC backend for a VM."""
        sock_path = ''
        interface_list = []

        if specific_nic is not None:
            sock_path = self._get_interfaces_sock_by_name(specific_nic)
            interface_list.append(specific_nic)
        else:
            interface_list = self._list_ifaces_by_vm_uuid(vm_uuid)

        for br in self.list_bridges():
            tmp_list = []
            for intface in interface_list:
                if intface in self.list_interfaces(br):
                    self.del_port(br, intface)
                    tmp_list.append(intface)
            interface_list = list(set(interface_list).difference(set(tmp_list)))

        return sock_path

    @lock.lock('ovs-destoryNicBackend')
    def destroy_nic_backend_no_wait(self, vm_uuid: str, specific_nic: str | None = None) -> str:
        """Destroy NIC backend without waiting."""
        sock_path = ''
        interface_list = []

        if specific_nic is not None:
            sock_path = self._get_interfaces_sock_by_name(specific_nic)
            interface_list.append(specific_nic)
        else:
            interface_list = self._list_ifaces_by_vm_uuid(vm_uuid)

        for br in self.list_bridges():
            tmp_list = []
            for intface in interface_list:
                if intface in self.list_interfaces(br):
                    self.del_port_no_wait(br, intface)
                    tmp_list.append(intface)
            interface_list = list(set(interface_list).difference(set(tmp_list)))

        return sock_path
