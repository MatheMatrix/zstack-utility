import importlib
import json
import pytest
import io
import sys
from unittest.mock import MagicMock, patch
from typing import Callable, Protocol, cast
from types import SimpleNamespace


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
    create_bridge: Callable[..., None]
    delete_vlan_bridge: Callable[..., None]
    vlan_eth_exists: Callable[..., bool]
    read_file: Callable[..., str]
    find_process_by_command: Callable[..., object]
    get_hostname: Callable[[], str]
    create_vlan_bridge: Callable[..., None]
    set_bridge_alias_using_phy_nic_name: Callable[..., None]
    set_device_uuid_alias: Callable[..., None]
    create_vlan_eth: Callable[..., None]
    create_vxlan_interface: Callable[..., None]
    create_vxlan_bridge: Callable[..., None]
    update_bridge_interface_configuration: Callable[..., None]
    move_dev_route: Callable[..., None]
    change_vxlan_interface: Callable[..., None]
    get_nics_by_cidr: Callable[..., list[dict[str, str]]]
    get_interfs_from_uuids: Callable[..., list[str]]
    populate_vxlan_fdbs: Callable[..., bool]
    delete_vxlan_fdbs: Callable[..., bool]
    delete_vxlan_bridge: Callable[..., None]
    delete_vlan_eth: Callable[..., None]
    write_file: Callable[..., None]
    is_vif_on_bridge: Callable[..., bool]


class _OsPathModule(Protocol):
    exists: Callable[[str], bool]


class _OsModule(Protocol):
    path: _OsPathModule






class _IprouteModule(Protocol):
    query_link: Callable[..., object]
    set_link_attribute: Callable[..., None]
    set_link_up: Callable[[str], None]
    config_link_isolated: Callable[..., None]




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


def _make_open(data: str) -> Callable[..., object]:
    def _open(*_args: object, **_kwargs: object) -> object:
        return io.StringIO(data)

    return _open


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

    def test_check_physical_network_interface_skips_bonded(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        ovs = cast(_OvsModule, cast(object, importlib.import_module("zstacklib.utils.ovs")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))
        iproute.set_link_up = MagicMock()

        def _is_existing(name: str) -> bool:
            return name == "eth1"

        def _bond_for(name: str) -> str | None:
            return "bond0" if name == "eth0" else None

        linux.is_network_device_existing = MagicMock(side_effect=_is_existing)
        ovs.OvsDpdkCtl.getBondFromFile = MagicMock(side_effect=_bond_for)
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=True)
        with patch("builtins.open", new=_make_open("down")):
            req = _make_req({'interfaceNames': ['eth0', 'eth1']})
            result = plugin.check_physical_network_interface(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        iproute.set_link_up.assert_called_once_with('eth1')


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

    def test_add_interface_to_bridge_moves_from_old_bridge(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell.call = MagicMock(return_value='br-old')
        shell.run = MagicMock(return_value=0)
        shell.check_run = MagicMock(return_value=0)

        req = _make_req({
            'physicalInterfaceName': 'eth0',
            'bridgeName': 'br-new',
        })
        result = plugin.add_interface_to_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        shell.run.assert_called_once_with('brctl delif br-old eth0')
        shell.check_run.assert_called_once_with('brctl addif br-new eth0')


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

    def test_check_bridge_missing_sets_error(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.is_bridge = MagicMock(return_value=False)

        req = _make_req({
            'bridgeName': 'br-missing',
            'physicalInterfaceName': 'eth0',
        })
        result = plugin.check_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'can not find bridge' in cast(str, rsp['error'])


@pytest.mark.kvmagent
class TestNetworkPluginCheckBridgeMissing:
    def test_check_bridge_missing(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.is_bridge = MagicMock(return_value=False)

        req = _make_req({'bridgeName': 'br-missing', 'physicalInterfaceName': 'eth0'})
        result = plugin.check_bridge(req)
        rsp = _load_rsp(result)

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

    def test_check_vlan_bridge_missing_sets_error(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.is_bridge = MagicMock(return_value=False)

        req = _make_req({'bridgeName': 'br-vlan', 'physicalInterfaceName': 'eth0'})
        result = plugin.check_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'can not find vlan bridge' in cast(str, rsp['error'])


@pytest.mark.kvmagent
class TestNetworkPluginCheckMacvlanVlanEth:
    def test_check_macvlan_vlan_eth_missing(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.vlan_eth_exists = MagicMock(return_value=False)

        req = _make_req({'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.check_macvlan_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False

    def test_check_macvlan_vlan_eth_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.vlan_eth_exists = MagicMock(return_value=True)
        ifup = MagicMock()
        setattr(plugin, "_ifup_device_if_down", ifup)

        req = _make_req({'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.check_macvlan_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        ifup.assert_called_once_with('eth0')


@pytest.mark.kvmagent
class TestNetworkPluginCreateBridge:
    def test_create_bridge_success(self):
        plugin = _make_plugin()
        setattr(plugin, "create_novlan_bridge", MagicMock())

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'mtu': 1500})
        result = plugin.create_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True

    def test_create_bridge_runs_internal_config(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        linux.create_bridge = MagicMock()
        linux.set_device_uuid_alias = MagicMock()
        linux.set_bridge_alias_using_phy_nic_name = MagicMock()
        linux.write_file = MagicMock(return_value=True)
        iproute.query_link = MagicMock(return_value=SimpleNamespace(mtu=1600))
        iproute.set_link_attribute = MagicMock()
        iproute.set_link_up = MagicMock()
        shell_call = MagicMock()
        shell.call = shell_call

        def _exists(path: str) -> bool:
            return path.endswith('/operstate')

        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(side_effect=_exists)
        with patch("builtins.open", new=_make_open("down")):
            req = _make_req({
                'bridgeName': 'br0',
                'physicalInterfaceName': 'eth0',
                'mtu': 1500,
                'disableIptables': True,
                'l2NetworkUuid': 'l2-uuid',
            })
            result = plugin.create_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.create_bridge.assert_called_once_with('br0', 'eth0')
        iproute.set_link_attribute.assert_called_once_with('eth0', mtu=1600)
        shell.call.assert_any_call('modprobe br_netfilter || true')


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

    def test_delete_vlan_bridge_for_novlan(self):
        plugin = _make_plugin()
        delete_bridge = cast(MagicMock, importlib.import_module("kvmagent.plugins.network_plugin"))

        delete_bridge.del_novlan_bridge = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'vlan': 0})
        result = plugin.delete_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        cast(MagicMock, delete_bridge.del_novlan_bridge).assert_called_once()


@pytest.mark.kvmagent
class TestNetworkPluginCreateVxlanBridge:
    def test_create_vxlan_bridge_missing_params(self):
        plugin = _make_plugin()

        req = _make_req({'vni': None, 'vtepIp': None})
        result = plugin.create_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False

    def test_create_vxlan_bridge_runs_internal(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))

        linux.create_vxlan_interface = MagicMock()
        linux.create_vxlan_bridge = MagicMock()
        linux.set_device_uuid_alias = MagicMock()
        iproute.query_link = MagicMock(return_value=SimpleNamespace(mtu=1400))
        iproute.set_link_attribute = MagicMock()

        req = _make_req({
            'bridgeName': 'br-vxlan',
            'vni': 10,
            'vtepIp': '10.0.0.1',
            'peers': ['10.0.0.2'],
            'mtu': 1300,
            'l2NetworkUuid': 'l2-uuid',
            'dstport': None,
        })
        result = plugin.create_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.create_vxlan_interface.assert_called_once_with(10, '10.0.0.1', 8472)
        linux.create_vxlan_bridge.assert_called_once_with('vxlan10', 'br-vxlan', ['10.0.0.2'])
        iproute.set_link_attribute.assert_called_once_with('vxlan10', mtu=1400)


@pytest.mark.kvmagent
class TestNetworkPluginCreateBonding:
    def test_create_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        setattr(plugin, "_get_interface_mtu", MagicMock(return_value=1500))
        setattr(plugin, "_add_interface_to_collectd_conf", MagicMock())
        setattr(plugin, "_restart_collectd", MagicMock())
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({
            'bondName': 'bond0',
            'slaves': [{'interfaceName': 'eth0'}, {'interfaceName': 'eth1'}],
            'mode': 'active-backup',
            'xmitHashPolicy': None,
        })
        result = plugin.create_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert shell_call.called

    def test_create_bonding_8023ad_uses_min_mtu(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        setattr(plugin, "_get_interface_mtu", MagicMock(side_effect=[9000, 1400]))
        setattr(plugin, "_add_interface_to_collectd_conf", MagicMock())
        setattr(plugin, "_restart_collectd", MagicMock())
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({
            'bondName': 'bond1',
            'slaves': [{'interfaceName': 'eth0'}, {'interfaceName': 'eth1'}],
            'mode': '802.3ad',
            'xmitHashPolicy': 'layer2+3',
        })
        result = plugin.create_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert any('xmit_hash_policy layer2+3' in call.args[0] for call in shell_call.mock_calls)
        assert any('zs-bond -u bond1 mtu 1400' in call.args[0] for call in shell_call.mock_calls)


@pytest.mark.kvmagent
class TestNetworkPluginUpdateBonding:
    def test_update_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        linux.read_file = MagicMock(side_effect=['mode active-backup', 'layer2', 'layer2'])
        shell_call = MagicMock()
        shell.call = shell_call

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
        assert shell_call.called

    def test_update_bonding_updates_mode_and_slaves(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        linux.read_file = MagicMock(side_effect=['mode active-backup', 'layer2', 'layer2'])
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({
            'bondName': 'bond0',
            'oldSlaves': [{'interfaceName': 'eth0'}, {'interfaceName': 'eth1'}],
            'slaves': [{'interfaceName': 'eth1'}, {'interfaceName': 'eth2'}],
            'mode': '802.3ad',
            'xmitHashPolicy': 'layer2+3',
        })
        result = plugin.update_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert any('zs-bond -u bond0 mode 802.3ad' in call.args[0] for call in shell_call.mock_calls)
        assert any('zs-nic-to-bond -a bond0 eth2' in call.args[0] for call in shell_call.mock_calls)
        assert any('zs-nic-to-bond -d bond0 eth0' in call.args[0] for call in shell_call.mock_calls)


@pytest.mark.kvmagent
class TestNetworkPluginAttachNicToBonding:
    def test_attach_nic_to_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.attach_nic_to_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert shell_call.called

    def test_attach_nic_to_bonding_rejects_vlan_slave(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=True))
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.attach_nic_to_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        shell_call.assert_not_called()


@pytest.mark.kvmagent
class TestNetworkPluginDetachNicFromBonding:
    def test_detach_nic_from_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell_call = MagicMock()
        shell.call = shell_call
        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.detach_nic_from_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert shell_call.called

    def test_detach_nic_from_bonding_handles_error(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell.call = MagicMock(side_effect=Exception("detach error"))

        req = _make_req({'bondName': 'bond0', 'slaves': [{'interfaceName': 'eth2'}]})
        result = plugin.detach_nic_from_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'unable to detach nic from bonding' in cast(str, rsp['error'])


@pytest.mark.kvmagent
class TestNetworkPluginDeleteBonding:
    def test_delete_bonding_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=False))
        setattr(plugin, "_remove_interface_from_collectd_conf", MagicMock())
        setattr(plugin, "_restart_collectd", MagicMock())
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({'bondName': 'bond0'})
        result = plugin.delete_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True

    def test_delete_bonding_rejects_vlan(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        setattr(plugin, "_has_vlan_or_bridge", MagicMock(return_value=True))
        setattr(plugin, "_remove_interface_from_collectd_conf", MagicMock())
        setattr(plugin, "_restart_collectd", MagicMock())
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({'bondName': 'bond0'})
        result = plugin.delete_bonding(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        shell_call.assert_not_called()


@pytest.mark.kvmagent
class TestNetworkPluginChangeLldpMode:
    def test_change_lldp_mode_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        setattr(plugin, "_update_lldp_conf", MagicMock())

        req = _make_req({'physicalInterfaceNames': ['eth0'], 'mode': 'rx_only'})
        result = plugin.change_lldp_mode(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, getattr(plugin, "_update_lldp_conf")).called

    def test_change_lldp_mode_initializes_lldpd(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        linux.find_process_by_command = MagicMock(return_value=False)
        linux.get_hostname = MagicMock(return_value='host')
        iproute.set_link_up = MagicMock()
        shell_call = MagicMock()
        shell.call = shell_call
        setattr(plugin, "_update_lldp_conf", MagicMock())

        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        def _exists_first(path: str) -> bool:
            if path.endswith("/etc/lldpd.d/lldpd.conf"):
                return False
            if path.endswith("command"):
                return True
            return False

        os_module.path.exists = MagicMock(side_effect=_exists_first)
        with patch("kvmagent.plugins.network_plugin.bash_ro", return_value=(0, "0000:00:00.0 Ethernet controller")), \
                patch("builtins.open", new=_make_open("")), \
                patch("kvmagent.plugins.network_plugin.NetworkPlugin._restart_lldpd", MagicMock()), \
                patch("kvmagent.plugins.network_plugin.NetworkPlugin._init_lldpd", MagicMock()):
            req = _make_req({'physicalInterfaceNames': ['eth0'], 'mode': 'rx_only'})
            result = plugin.change_lldp_mode(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        cast(MagicMock, getattr(plugin, "_update_lldp_conf")).assert_called_once()


@pytest.mark.kvmagent
class TestNetworkPluginGetLldpInfo:
    def test_get_lldp_info_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        setattr(plugin, "_get_interface_lldp", MagicMock())
        setattr(plugin, "_get_interface_lldp", MagicMock(return_value={'lldp': 'info'}))

        req = _make_req({'physicalInterfaceName': 'eth0'})
        result = plugin.get_lldp_info(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert rsp['lldpInfo'] == {'lldp': 'info'}

    def test_get_lldp_info_parses_json(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)

        lldp_json = json.dumps({
            "lldp": {
                "interface": {
                    "eth0": {
                        "chassis": {
                            "sw1": {
                                "id": {"value": "00:11"},
                                "descr": "desc\nline",
                                "mgmt-ip": "10.0.0.1",
                                "capability": [{"type": "bridge", "enabled": True}],
                            }
                        },
                        "port": {
                            "ttl": 100,
                            "id": {"value": "p1"},
                            "descr": "port-desc",
                            "aggregation": "lag1",
                            "mfs": 1500,
                        },
                        "vlan": {"vlan-id": 100},
                    }
                }
            }
        })

        with patch("kvmagent.plugins.network_plugin.bash_ro", return_value=(0, lldp_json)):
            req = _make_req({'physicalInterfaceName': 'eth0'})
            result = plugin.get_lldp_info(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        cast(MagicMock, getattr(plugin, "_get_interface_lldp")).assert_called_once_with('eth0')


@pytest.mark.kvmagent
class TestNetworkPluginApplyLldpConfig:
    def test_apply_lldp_config_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        setattr(plugin, "_update_lldp_conf", MagicMock())

        req = _make_req({'lldpConfig': [{'physicalInterfaceName': 'eth0', 'mode': 'rx_only'}]})
        result = plugin.apply_lldp_config(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, getattr(plugin, "_update_lldp_conf")).called

    def test_apply_lldp_config_updates_multiple(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))

        linux.find_process_by_command = MagicMock(return_value=True)
        os_module.path.exists = MagicMock(return_value=True)
        setattr(plugin, "_update_lldp_conf", MagicMock())

        req = _make_req({
            'lldpConfig': [
                {'physicalInterfaceName': 'eth0', 'mode': 'rx_only'},
                {'physicalInterfaceName': 'eth1', 'mode': 'tx_only'},
            ]
        })
        result = plugin.apply_lldp_config(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, getattr(plugin, "_update_lldp_conf")).call_count == 2


@pytest.mark.kvmagent
class TestNetworkPluginUpdateVlanBridge:
    def test_update_vlan_bridge_success(self):
        plugin = _make_plugin()
        update_vlan = MagicMock()
        plugin.update_bridge_vlan = update_vlan

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0', 'oldVlan': 0, 'newVlan': 100})
        result = plugin.update_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert update_vlan.called

    def test_update_vlan_bridge_updates_routes(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.create_vlan_eth = MagicMock()
        linux.update_bridge_interface_configuration = MagicMock()
        linux.move_dev_route = MagicMock()
        ifup = MagicMock()
        setattr(plugin, "_ifup_device_if_down", ifup)

        req = _make_req({
            'bridgeName': 'br0',
            'physicalInterfaceName': 'eth0',
            'oldVlan': 100,
            'newVlan': 0,
            'l2NetworkUuid': 'l2-uuid',
        })
        result = plugin.update_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.update_bridge_interface_configuration.assert_called_once_with('eth0.100', 'eth0', 'br0', 'l2-uuid')
        linux.move_dev_route.assert_called_once_with('eth0', 'br0')


@pytest.mark.kvmagent
class TestNetworkPluginUpdateVxlanBridge:
    def test_update_vxlan_bridge_success(self):
        plugin = _make_plugin()
        update_vxlan = MagicMock()
        plugin.update_bridge_vxlan = update_vxlan

        req = _make_req({'bridgeName': 'br0', 'oldVlan': 1, 'newVlan': 2, 'peers': []})
        result = plugin.update_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert update_vxlan.called

    def test_update_vxlan_bridge_updates_interfaces(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.delete_vxlan_fdbs = MagicMock()
        linux.change_vxlan_interface = MagicMock()
        linux.update_bridge_interface_configuration = MagicMock()
        linux.populate_vxlan_fdbs = MagicMock()

        req = _make_req({
            'bridgeName': 'br0',
            'oldVlan': 1,
            'newVlan': 2,
            'peers': ['1.1.1.1'],
            'l2NetworkUuid': 'l2-uuid',
        })
        result = plugin.update_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.delete_vxlan_fdbs.assert_called_once_with(['vxlan1'], ['1.1.1.1'])
        linux.populate_vxlan_fdbs.assert_called_once_with(['vxlan2'], ['1.1.1.1'])

    def test_update_vxlan_bridge_missing_vlan_error(self):
        plugin = _make_plugin()

        req = _make_req({
            'bridgeName': 'br0',
            'oldVlan': None,
            'newVlan': 2,
            'peers': [],
        })
        result = plugin.update_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'both oldVlan and newVlan' in cast(str, rsp['error'])


@pytest.mark.kvmagent
class TestNetworkPluginCreateVlanBridge:
    def test_create_vlan_bridge_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        setattr(plugin, "_get_interface_mtu", MagicMock(return_value=1500))
        setattr(plugin, "_configure_bridge", MagicMock())
        setattr(plugin, "_configure_bridge_mtu", MagicMock())
        setattr(plugin, "_configure_bridge_learning", MagicMock())
        setattr(plugin, "_enable_bridge_igmp_snooping", MagicMock())
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

    def test_create_vlan_bridge_isolated(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        iptables = cast(MagicMock, importlib.import_module("zstacklib.utils.iptables_v2"))

        setattr(plugin, "_get_interface_mtu", MagicMock(return_value=1500))
        linux.create_vlan_bridge = MagicMock()
        linux.set_bridge_alias_using_phy_nic_name = MagicMock()
        linux.set_device_uuid_alias = MagicMock()
        linux.write_file = MagicMock(return_value=True)
        shell_call = MagicMock()
        shell.call = shell_call

        forward_chain = MagicMock()
        isolated_chain = MagicMock()
        filter_table_v4 = MagicMock()
        filter_table_v6 = MagicMock()

        def _get_chain(name: str) -> object | None:
            if name == getattr(iptables, "FORWARD_CHAIN_NAME", "FORWARD"):
                return forward_chain
            return None

        filter_table_v4.get_chain_by_name = MagicMock(side_effect=_get_chain)
        filter_table_v6.get_chain_by_name = MagicMock(side_effect=_get_chain)
        filter_table_v4.add_chain_if_not_exist = MagicMock(return_value=isolated_chain)
        filter_table_v6.add_chain_if_not_exist = MagicMock(return_value=isolated_chain)
        iptables.from_iptables_save = MagicMock(side_effect=[filter_table_v4, filter_table_v6])

        req = _make_req({
            'bridgeName': 'br0',
            'physicalInterfaceName': 'eth0',
            'vlan': 100,
            'l2NetworkUuid': 'l2-uuid',
            'disableIptables': False,
            'mtu': 1500,
            'isolated': True,
        })
        result = plugin.create_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.create_vlan_bridge.assert_called_once_with('br0', 'eth0', 100)
        assert shell_call.called

    def test_create_vlan_bridge_zero_vlan_uses_novlan_path(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        linux.create_bridge = MagicMock()
        linux.set_device_uuid_alias = MagicMock()
        linux.set_bridge_alias_using_phy_nic_name = MagicMock()
        linux.write_file = MagicMock(return_value=True)
        iproute.query_link = MagicMock(return_value=SimpleNamespace(mtu=1450))
        iproute.set_link_attribute = MagicMock()
        iproute.set_link_up = MagicMock()
        shell_call = MagicMock()
        shell.call = shell_call

        def _exists(path: str) -> bool:
            return path.endswith('/operstate')

        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(side_effect=_exists)
        with patch("builtins.open", new=_make_open("down")):
            req = _make_req({
                'bridgeName': 'br0',
                'physicalInterfaceName': 'eth0',
                'vlan': 0,
                'l2NetworkUuid': 'l2-uuid',
                'disableIptables': False,
                'mtu': 1400,
            })
            result = plugin.create_vlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.create_bridge.assert_called_once_with('br0', 'eth0')


@pytest.mark.kvmagent
class TestNetworkPluginCreateMacVlanEth:
    def test_create_mac_vlan_eth_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        setattr(plugin, "_get_interface_mtu", MagicMock(return_value=1500))
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

    def test_create_mac_vlan_eth_uses_larger_mtu(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        setattr(plugin, "_get_interface_mtu", MagicMock(return_value=1600))
        linux.create_vlan_eth = MagicMock()
        linux.set_device_uuid_alias = MagicMock()

        req = _make_req({
            'physicalInterfaceName': 'eth0',
            'vlan': 200,
            'l2NetworkUuid': 'l2-uuid',
            'mtu': 1500,
        })
        result = plugin.create_mac_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.create_vlan_eth.assert_called_once_with('eth0', 200)


@pytest.mark.kvmagent
class TestNetworkPluginCheckVxlanCidr:
    def test_check_vxlan_cidr_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        class _LegacyDict:
            _data: dict[str, str]

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

    def test_check_vxlan_cidr_multiple_interfaces_error(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        class _LegacyDict:
            _data: dict[str, str]

            def __init__(self, data: dict[str, str]):
                self._data = data

            def values(self) -> list[str]:
                return list(self._data.values())

            def keys(self) -> list[str]:
                return list(self._data.keys())

        linux.get_nics_by_cidr = MagicMock(return_value=[
            _LegacyDict({'eth0': '10.0.0.1'}),
            _LegacyDict({'eth1': '10.0.0.1'}),
        ])
        linux.is_vif_on_bridge = MagicMock(return_value=False)

        req = _make_req({'cidr': '10.0.0.0/24', 'physicalInterfaceName': None, 'vtepip': None})
        result = plugin.check_vxlan_cidr(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'multiple interfaces' in cast(str, rsp['error'])

    def test_check_vxlan_cidr_filters_by_interface(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        class _LegacyDict:
            _data: dict[str, str]

            def __init__(self, data: dict[str, str]):
                self._data = data

            def values(self) -> list[str]:
                return list(self._data.values())

            def keys(self) -> list[str]:
                return list(self._data.keys())

        linux.get_nics_by_cidr = MagicMock(return_value=[
            _LegacyDict({'eth0': '10.0.0.2'}),
            _LegacyDict({'eth1': '10.0.0.3'}),
        ])
        linux.is_vif_on_bridge = MagicMock(return_value=False)

        req = _make_req({'cidr': '10.0.0.0/24', 'physicalInterfaceName': 'eth1', 'vtepip': None})
        result = plugin.check_vxlan_cidr(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert rsp['physicalInterfaceName'] == 'eth1'


@pytest.mark.kvmagent
class TestNetworkPluginCreateVxlanBridges:
    def test_create_vxlan_bridges_success(self):
        plugin = _make_plugin()
        create_single = MagicMock()
        plugin.create_single_vxlan_bridge = create_single

        req = _make_req({
            'bridgeCmds': [
                {'bridgeName': 'br0', 'vni': 10, 'vtepIp': '10.0.0.1', 'peers': [], 'mtu': 1450, 'l2NetworkUuid': 'l2-uuid'},
            ]
        })
        result = plugin.create_vxlan_bridges(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert create_single.called

    def test_create_vxlan_bridges_runs_internal(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))

        linux.create_vxlan_interface = MagicMock()
        linux.create_vxlan_bridge = MagicMock()
        linux.set_device_uuid_alias = MagicMock()
        iproute.query_link = MagicMock(return_value=SimpleNamespace(mtu=1450))
        iproute.set_link_attribute = MagicMock()

        req = _make_req({
            'bridgeCmds': [
                {'bridgeName': 'br0', 'vni': 10, 'vtepIp': '10.0.0.1', 'peers': [], 'mtu': 1400, 'l2NetworkUuid': 'l2-uuid'},
                {'bridgeName': 'br1', 'vni': 11, 'vtepIp': '10.0.0.2', 'peers': ['10.0.0.3'], 'mtu': 1400, 'l2NetworkUuid': 'l2-uuid'},
            ]
        })
        result = plugin.create_vxlan_bridges(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert linux.create_vxlan_interface.call_count == 2


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

    def test_delete_vxlan_bridge_missing_params(self):
        plugin = _make_plugin()

        req = _make_req({'bridgeName': 'br0', 'vni': None, 'vtepIp': None})
        result = plugin.delete_vxlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False


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

    def test_populate_vxlan_fdb_failure_sets_error(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.populate_vxlan_fdbs = MagicMock(return_value=False)

        req = _make_req({'vni': 10, 'peers': ['1.1.1.1']})
        result = plugin.populate_vxlan_fdb(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'error on populate fdb' in cast(str, rsp['error'])


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

    def test_populate_vxlan_fdbs_no_interfaces(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.get_interfs_from_uuids = MagicMock(return_value=[])
        linux.populate_vxlan_fdbs = MagicMock(return_value=True)

        req = _make_req({'networkUuids': ['net-1'], 'peers': ['1.1.1.1']})
        result = plugin.populate_vxlan_fdbs(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.populate_vxlan_fdbs.assert_not_called()


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

    def test_delete_vxlan_fdbs_failure(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.get_interfs_from_uuids = MagicMock(return_value=['vxlan10'])
        linux.delete_vxlan_fdbs = MagicMock(return_value=False)

        req = _make_req({'networkUuids': ['net-1'], 'peers': ['1.1.1.1']})
        result = plugin.delete_vxlan_fdbs(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'error on delete fdb' in cast(str, rsp['error'])


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
        assert linux.write_file.called

    def test_set_bridge_router_port_disable(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.write_file = MagicMock()

        req = _make_req({'nicNames': ['vnic0'], 'enable': False})
        result = plugin.set_bridge_router_port(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        linux.write_file.assert_called_once_with(
            '/sys/devices/virtual/net/vnic0/brport/multicast_router', '1'
        )


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

    def test_delete_novlan_bridge_error(self):
        plugin = _make_plugin()
        delete_bridge = cast(MagicMock, importlib.import_module("kvmagent.plugins.network_plugin"))

        delete_bridge.del_novlan_bridge = MagicMock(side_effect=Exception("fail"))

        req = _make_req({'bridgeName': 'br0', 'physicalInterfaceName': 'eth0'})
        result = plugin.delete_novlan_bridge(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'failed to delete bridge' in cast(str, rsp['error'])


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

    def test_delete_macvlan_vlan_eth_error(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.delete_vlan_eth = MagicMock(side_effect=Exception("fail"))

        req = _make_req({'physicalInterfaceName': 'eth0', 'vlan': 100})
        result = plugin.delete_macvlan_vlan_eth(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is False
        assert 'failed to delete vlan eth' in cast(str, rsp['error'])


@pytest.mark.kvmagent
class TestNetworkPluginAttachNicToIpsetPath:
    def test_attach_nic_to_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({
            'l2MacMap': {'l2-1': ['aa:bb:cc:dd:ee:ff']},
            'interfaceMap': {'l2-1': 'eth0'},
            'vlanMap': {'l2-1': 100},
        })
        result = plugin.attach_nic_to_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert shell_call.called

    def test_attach_nic_to_ipset_path_no_macs(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell_call = MagicMock()
        shell.call = shell_call

        req = _make_req({
            'l2MacMap': None,
            'interfaceMap': None,
            'vlanMap': None,
        })
        result = plugin.attach_nic_to_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        shell_call.assert_not_called()


@pytest.mark.kvmagent
class TestNetworkPluginDetachNicToIpsetPath:
    def test_detach_nic_to_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))

        shell_call = MagicMock()
        shell.call = shell_call
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
        iproute.config_link_isolated.assert_called()

    def test_detach_nic_to_ipset_path_no_macs(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        iproute = cast(_IprouteModule, cast(object, importlib.import_module("zstacklib.utils.iproute")))

        shell_call = MagicMock()
        shell.call = shell_call
        iproute.config_link_isolated = MagicMock()

        req = _make_req({
            'l2MacMap': None,
            'interfaceMap': None,
            'vlanMap': None,
            'nicList': [],
        })
        result = plugin.detach_nic_to_ipset_path(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        shell_call.assert_not_called()
        iproute.config_link_isolated.assert_not_called()


@pytest.mark.kvmagent
class TestNetworkPluginSyncIpsetPath:
    def test_sync_ipset_path_success(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell_call = MagicMock()
        shell.call = shell_call
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
        assert shell_call.called

    def test_sync_ipset_path_existing_list(self):
        plugin = _make_plugin()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))

        shell_call = MagicMock()
        shell.call = shell_call
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
        assert any('ipset destroy isolated_eth0.100' in call.args[0] for call in shell_call.mock_calls)
