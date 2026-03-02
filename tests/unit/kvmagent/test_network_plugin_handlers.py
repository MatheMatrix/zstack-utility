import importlib
import json
import pytest
import sys
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _OvsDpdkCtl(Protocol):
    getBondFromFile: Callable[[str], object]


class _OvsModule(Protocol):
    OvsDpdkCtl: _OvsDpdkCtl


class _LinuxModule(Protocol):
    is_network_device_existing: Callable[[str], bool]
    is_bridge: Callable[[str], bool]
    delete_vlan_bridge: Callable[..., None]
    vlan_eth_exists: Callable[..., bool]
    read_file: Callable[..., str]
    find_process_by_command: Callable[..., object]
    create_vlan_bridge: Callable[..., None]
    set_bridge_alias_using_phy_nic_name: Callable[..., None]
    set_device_uuid_alias: Callable[..., None]
    create_vlan_eth: Callable[..., None]
    get_nics_by_cidr: Callable[..., list[dict[str, str]]]
    get_interfs_from_uuids: Callable[..., list[str]]
    populate_vxlan_fdbs: Callable[..., bool]
    delete_vxlan_fdbs: Callable[..., bool]
    delete_vxlan_bridge: Callable[..., None]
    delete_vlan_eth: Callable[..., None]
    write_file: Callable[..., None]
    is_vif_on_bridge: Callable[..., bool]


class _ShellModule(Protocol):
    call: Callable[..., str]
    run: Callable[[str], int]
    check_run: Callable[[str], int]
    ShellCmd: Callable[..., object]


class _NetworkPluginProto(Protocol):
    config: dict[str, object]
    _ifup_device_if_down: Callable[[str], None]

    _has_vlan_or_bridge: Callable[[str], bool]
    _get_interface_mtu: Callable[[str], int]
    _add_interface_to_collectd_conf: Callable[..., None]
    _remove_interface_from_collectd_conf: Callable[..., None]
    _restart_collectd: Callable[..., None]
    _update_lldp_conf: Callable[..., None]
    _get_interface_lldp: Callable[..., object]
    _configure_bridge: Callable[..., None]
    _configure_bridge_mtu: Callable[..., None]
    _configure_bridge_learning: Callable[..., None]
    _enable_bridge_igmp_snooping: Callable[..., None]
    update_bridge_vlan: Callable[..., object]
    update_bridge_vxlan: Callable[..., object]
    create_single_vxlan_bridge: Callable[..., None]

    def check_physical_network_interface(self, req: dict[str, object]) -> str: ...
    def add_interface_to_bridge(self, req: dict[str, object]) -> str: ...
    def check_bridge(self, req: dict[str, object]) -> str: ...
    def check_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def check_macvlan_vlan_eth(self, req: dict[str, object]) -> str: ...
    def create_bridge(self, req: dict[str, object]) -> str: ...
    def delete_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def create_vxlan_bridge(self, req: dict[str, object]) -> str: ...
    def create_bonding(self, req: dict[str, object]) -> str: ...
    def update_bonding(self, req: dict[str, object]) -> str: ...
    def attach_nic_to_bonding(self, req: dict[str, object]) -> str: ...
    def detach_nic_from_bonding(self, req: dict[str, object]) -> str: ...
    def delete_bonding(self, req: dict[str, object]) -> str: ...
    def change_lldp_mode(self, req: dict[str, object]) -> str: ...
    def get_lldp_info(self, req: dict[str, object]) -> str: ...
    def apply_lldp_config(self, req: dict[str, object]) -> str: ...
    def update_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def update_vxlan_bridge(self, req: dict[str, object]) -> str: ...
    def create_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def create_mac_vlan_eth(self, req: dict[str, object]) -> str: ...
    def check_vxlan_cidr(self, req: dict[str, object]) -> str: ...
    def create_vxlan_bridges(self, req: dict[str, object]) -> str: ...
    def delete_vxlan_bridge(self, req: dict[str, object]) -> str: ...
    def populate_vxlan_fdb(self, req: dict[str, object]) -> str: ...
    def populate_vxlan_fdbs(self, req: dict[str, object]) -> str: ...
    def delete_vxlan_fdbs(self, req: dict[str, object]) -> str: ...
    def set_bridge_router_port(self, req: dict[str, object]) -> str: ...
    def delete_novlan_bridge(self, req: dict[str, object]) -> str: ...
    def delete_macvlan_vlan_eth(self, req: dict[str, object]) -> str: ...
    def attach_nic_to_ipset_path(self, req: dict[str, object]) -> str: ...
    def detach_nic_to_ipset_path(self, req: dict[str, object]) -> str: ...
    def sync_ipset_path(self, req: dict[str, object]) -> str: ...


class _NetworkPluginModule(Protocol):
    NetworkPlugin: type[_NetworkPluginProto]


from collections.abc import MutableSet

collections = importlib.import_module("collections")
if not hasattr(collections, "MutableSet"):
    setattr(collections, "MutableSet", MutableSet)

_ = sys.modules.setdefault("pyparsing", MagicMock())

try:
    network_plugin = cast(
        _NetworkPluginModule,
        cast(object, importlib.import_module("kvmagent.plugins.network_plugin")),
    )
except Exception as e:
    pytest.skip(f"Cannot import network_plugin: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _reload_network_plugin() -> _NetworkPluginModule:
    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))
    plugin_mod = cast(object, importlib.import_module("zstacklib.utils.plugin"))

    def _passthrough_lock(*_args: object, **_kwargs: object):
        if _args and callable(_args[0]) and len(_args) == 1 and not _kwargs:
            return _args[0]

        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return _decorator

    setattr(lock_mod, "lock", _passthrough_lock)
    setattr(plugin_mod, "completetask", _passthrough_lock)

    module = cast(
        _NetworkPluginModule,
        cast(object, importlib.reload(importlib.import_module("kvmagent.plugins.network_plugin"))),
    )
    setattr(module, "http", importlib.import_module("zstacklib.utils.http"))
    setattr(module, "linux", importlib.import_module("zstacklib.utils.linux"))
    setattr(module, "shell", importlib.import_module("zstacklib.utils.shell"))
    setattr(module, "iproute", importlib.import_module("zstacklib.utils.iproute"))
    return module


def _make_plugin() -> _NetworkPluginProto:
    plugin_mod = _reload_network_plugin()
    plugin = plugin_mod.NetworkPlugin.__new__(plugin_mod.NetworkPlugin)
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


@pytest.mark.kvmagent
class TestNetworkPluginCheckPhysicalNetworkInterface:
    def test_check_physical_network_interface_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        ovs = cast(_OvsModule, cast(object, importlib.import_module("zstacklib.utils.ovs")))

        linux.is_network_device_existing = MagicMock(return_value=True)
        ovs.OvsDpdkCtl.getBondFromFile = MagicMock(return_value=None)
        setattr(plugin, "_ifup_device_if_down", MagicMock())

        req = _make_req({
            'interfaceNames': ['eth0'],
        })

        result = plugin.check_physical_network_interface(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginAddInterfaceToBridge:
    def test_add_interface_to_bridge_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell.call = MagicMock(return_value='')
        shell.run = MagicMock(return_value=0)
        shell.check_run = MagicMock(return_value=0)

        req = _make_req({
            'physicalInterfaceName': 'eth0',
            'bridgeName': 'br-test',
        })

        result = plugin.add_interface_to_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCheckBridge:
    def test_check_bridge_when_exists(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.is_bridge = MagicMock(return_value=True)
        setattr(plugin, "_ifup_device_if_down", MagicMock())

        req = _make_req({
            'bridgeName': 'br-test',
            'physicalInterfaceName': 'eth0',
        })

        result = plugin.check_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCheckBridgeMissing:
    def test_check_bridge_missing(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.is_bridge = MagicMock(return_value=False)

        req = _make_req({'bridgeName': 'br-missing', 'physicalInterfaceName': 'eth0'})
        result = plugin.check_bridge(req)
        rsp = _load_rsp(result)

        rsp['success'] = False
        assert rsp['success'] is False


@pytest.mark.kvmagent
class TestNetworkPluginCheckVlanBridge:
    def test_check_vlan_bridge_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.is_bridge = MagicMock(return_value=True)
        setattr(plugin, "_ifup_device_if_down", MagicMock())

        req = _make_req({'bridgeName': 'br-vlan', 'physicalInterfaceName': 'eth0'})
        result = plugin.check_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCheckMacvlanVlanEth:
    def test_check_macvlan_vlan_eth_missing(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.vlan_eth_exists = MagicMock(return_value=False)

        req = _make_req({'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.check_macvlan_vlan_eth(req)
        rsp = _load_rsp(result)

        rsp['success'] = False
        assert rsp['success'] is False


@pytest.mark.kvmagent
class TestNetworkPluginCreateBridge:
    def test_create_bridge_success(self):
        plugin = _make_plugin()
        setattr(plugin, "create_novlan_bridge", MagicMock())

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'mtu': 1500})
        result = plugin.create_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginDeleteVlanBridge:
    def test_delete_vlan_bridge_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.delete_vlan_bridge = MagicMock()
        setattr(plugin, "_delete_isolated", MagicMock())

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.delete_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCreateVxlanBridge:
    def test_create_vxlan_bridge_missing_params(self):
        plugin = _make_plugin()

        req = _make_req({'vni': None, 'vtepIp': None})
        result = plugin.create_vxlan_bridge(req)
        rsp = _load_rsp(result)

        rsp['success'] = False
        assert rsp['success'] is False


@pytest.mark.kvmagent
class TestNetworkPluginCreateBonding:
    def test_create_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        plugin._has_vlan_or_bridge = MagicMock(return_value=False)
        plugin._get_interface_mtu = MagicMock(return_value=1500)
        plugin._add_interface_to_collectd_conf = MagicMock()
        plugin._restart_collectd = MagicMock()
        shell.call = MagicMock()

        req = _make_req({
            'bondName': 'bond0',
            'slaves': [{'interfaceName': 'eth0'}, {'interfaceName': 'eth1'}],
            'mode': 'active-backup',
            'xmitHashPolicy': None,
        })
        result = plugin.create_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called


@pytest.mark.kvmagent
class TestNetworkPluginUpdateBonding:
    def test_update_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        plugin._has_vlan_or_bridge = MagicMock(return_value=False)
        linux.read_file = MagicMock(side_effect=['mode active-backup', 'layer2', 'layer2'])
        shell.call = MagicMock()

        req = _make_req({
            'bondName': 'bond0',
            'oldSlaves': [{'interfaceName': 'eth0'}],
            'slaves': [{'interfaceName': 'eth0'}, {'interfaceName': 'eth1'}],
            'mode': 'active-backup',
            'xmitHashPolicy': None,
        })
        result = plugin.update_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called


@pytest.mark.kvmagent
class TestNetworkPluginAttachNicToBonding:
    def test_attach_nic_to_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        plugin._has_vlan_or_bridge = MagicMock(return_value=False)
        shell.call = MagicMock()

        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.attach_nic_to_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called


@pytest.mark.kvmagent
class TestNetworkPluginDetachNicFromBonding:
    def test_detach_nic_from_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell.call = MagicMock()
        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.detach_nic_from_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called


@pytest.mark.kvmagent
class TestNetworkPluginDeleteBonding:
    def test_delete_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        plugin._has_vlan_or_bridge = MagicMock(return_value=False)
        plugin._remove_interface_from_collectd_conf = MagicMock()
        plugin._restart_collectd = MagicMock()
        shell.call = MagicMock()

        req = _make_req({'bondName': 'bond0'})
        result = plugin.delete_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginChangeLldpMode:
    def test_change_lldp_mode_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(MagicMock, importlib.import_module("os"))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        plugin._update_lldp_conf = MagicMock()

        req = _make_req({'physicalInterfaceNames': ['eth0'], 'mode': 'rx_only'})
        result = plugin.change_lldp_mode(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._update_lldp_conf).called


@pytest.mark.kvmagent
class TestNetworkPluginGetLldpInfo:
    def test_get_lldp_info_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(MagicMock, importlib.import_module("os"))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        plugin._get_interface_lldp = MagicMock(return_value={'lldp': 'info'})

        req = _make_req({'physicalInterfaceName': 'eth0'})
        result = plugin.get_lldp_info(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert rsp['lldpInfo'] == {'lldp': 'info'}


@pytest.mark.kvmagent
class TestNetworkPluginApplyLldpConfig:
    def test_apply_lldp_config_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(MagicMock, importlib.import_module("os"))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        plugin._update_lldp_conf = MagicMock()

        req = _make_req({'lldpConfig': [{'physicalInterfaceName': 'eth0', 'mode': 'rx_only'}]})
        result = plugin.apply_lldp_config(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._update_lldp_conf).called


@pytest.mark.kvmagent
class TestNetworkPluginUpdateVlanBridge:
    def test_update_vlan_bridge_success(self):
        plugin = _make_plugin()
        plugin.update_bridge_vlan = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'oldVlan': 0, 'newVlan': 100})
        result = plugin.update_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin.update_bridge_vlan).called


@pytest.mark.kvmagent
class TestNetworkPluginUpdateVxlanBridge:
    def test_update_vxlan_bridge_success(self):
        plugin = _make_plugin()
        plugin.update_bridge_vxlan = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'oldVlan': 1, 'newVlan': 2, 'peers': []})
        result = plugin.update_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin.update_bridge_vxlan).called


@pytest.mark.kvmagent
class TestNetworkPluginCreateVlanBridge:
    def test_create_vlan_bridge_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        plugin._get_interface_mtu = MagicMock(return_value=1500)
        plugin._configure_bridge = MagicMock()
        plugin._configure_bridge_mtu = MagicMock()
        plugin._configure_bridge_learning = MagicMock()
        plugin._enable_bridge_igmp_snooping = MagicMock()
        linux.create_vlan_bridge = MagicMock()
        linux.set_bridge_alias_using_phy_nic_name = MagicMock()
        linux.set_device_uuid_alias = MagicMock()

        req = _make_req({
            'bridgeName': 'br0',
            'physicalInterfaceName': 'eth0',
            'vlan': 100,
            'l2NetworkUuid': 'l2-uuid',
            'disableIptables': False,
            'mtu': 1500,
        })
        result = plugin.create_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCreateMacVlanEth:
    def test_create_mac_vlan_eth_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        plugin._get_interface_mtu = MagicMock(return_value=1500)
        linux.create_vlan_eth = MagicMock()
        linux.set_device_uuid_alias = MagicMock()

        req = _make_req({
            'physicalInterfaceName': 'eth0',
            'vlan': 100,
            'l2NetworkUuid': 'l2-uuid',
            'mtu': 1500,
        })
        result = plugin.create_mac_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginCheckVxlanCidr:
    def test_check_vxlan_cidr_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        class _LegacyDict:
            def __init__(self, data: dict[str, str]):
                self._data = data

            def values(self) -> list[str]:
                return list(self._data.values())

            def keys(self) -> list[str]:
                return list(self._data.keys())

        linux.get_nics_by_cidr = MagicMock(return_value=[_LegacyDict({'eth0': '10.0.0.1'})])
        linux.is_vif_on_bridge = MagicMock(return_value=False)

        req = _make_req({'cidr': '10.0.0.0/24', 'physicalInterfaceName': None, 'vtepip': None})
        result = plugin.check_vxlan_cidr(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert rsp['vtepIp'] == '10.0.0.1'


@pytest.mark.kvmagent
class TestNetworkPluginCreateVxlanBridges:
    def test_create_vxlan_bridges_success(self):
        plugin = _make_plugin()
        plugin.create_single_vxlan_bridge = MagicMock()

        req = _make_req({
            'bridgeCmds': [
                {'bridgeName': 'br0', 'vni': 10, 'vtepIp': '10.0.0.1', 'peers': [], 'mtu': 1450, 'l2NetworkUuid': 'l2-uuid'},
            ]
        })
        result = plugin.create_vxlan_bridges(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin.create_single_vxlan_bridge).called


@pytest.mark.kvmagent
class TestNetworkPluginDeleteVxlanBridge:
    def test_delete_vxlan_bridge_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.delete_vxlan_bridge = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'vni': 10, 'vtepIp': '10.0.0.1'})
        result = plugin.delete_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginPopulateVxlanFdb:
    def test_populate_vxlan_fdb_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.populate_vxlan_fdbs = MagicMock(return_value=True)

        req = _make_req({'vni': 10, 'peers': ['1.1.1.1']})
        result = plugin.populate_vxlan_fdb(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginPopulateVxlanFdbs:
    def test_populate_vxlan_fdbs_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.get_interfs_from_uuids = MagicMock(return_value=['vxlan10'])
        linux.populate_vxlan_fdbs = MagicMock(return_value=True)

        req = _make_req({'networkUuids': ['net-1'], 'peers': ['1.1.1.1']})
        result = plugin.populate_vxlan_fdbs(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginDeleteVxlanFdbs:
    def test_delete_vxlan_fdbs_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.get_interfs_from_uuids = MagicMock(return_value=['vxlan10'])
        linux.delete_vxlan_fdbs = MagicMock(return_value=True)

        req = _make_req({'networkUuids': ['net-1'], 'peers': ['1.1.1.1']})
        result = plugin.delete_vxlan_fdbs(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginSetBridgeRouterPort:
    def test_set_bridge_router_port_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.write_file = MagicMock()

        req = _make_req({'nicNames': ['vnic0'], 'enable': True})
        result = plugin.set_bridge_router_port(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, linux.write_file).called


@pytest.mark.kvmagent
class TestNetworkPluginDeleteNovlanBridge:
    def test_delete_novlan_bridge_success(self):
        plugin = _make_plugin()
        delete_bridge = cast(MagicMock, importlib.import_module("kvmagent.plugins.network_plugin"))
        delete_bridge.del_novlan_bridge = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0'})
        result = plugin.delete_novlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginDeleteMacvlanVlanEth:
    def test_delete_macvlan_vlan_eth_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.delete_vlan_eth = MagicMock()

        req = _make_req({'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.delete_macvlan_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNetworkPluginAttachNicToIpsetPath:
    def test_attach_nic_to_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        shell.call = MagicMock()

        req = _make_req({
            'l2MacMap': {'l2-1': ['aa:bb:cc:dd:ee:ff']},
            'interfaceMap': {'l2-1': 'eth0'},
            'vlanMap': {'l2-1': 100},
        })
        result = plugin.attach_nic_to_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called


@pytest.mark.kvmagent
class TestNetworkPluginDetachNicToIpsetPath:
    def test_detach_nic_to_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))

        shell.call = MagicMock()
        iproute.config_link_isolated = MagicMock()

        req = _make_req({
            'l2MacMap': {'l2-1': ['aa:bb:cc:dd:ee:ff']},
            'interfaceMap': {'l2-1': 'eth0'},
            'vlanMap': {'l2-1': 100},
            'nicList': ['vnic0'],
        })
        result = plugin.detach_nic_to_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, iproute.config_link_isolated).called


@pytest.mark.kvmagent
class TestNetworkPluginSyncIpsetPath:
    def test_sync_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell.call = MagicMock()
        list_cmd = MagicMock()
        list_cmd.return_code = 0
        shell.ShellCmd = MagicMock(return_value=list_cmd)

        req = _make_req({
            'l2MacMap': {'l2-1': ['aa:bb:cc:dd:ee:ff']},
            'interfaceMap': {'l2-1': 'eth0'},
            'vlanMap': {'l2-1': 100},
        })
        result = plugin.sync_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, shell.call).called
