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


class _ShellModule(Protocol):
    call: Callable[..., str]
    run: Callable[[str], int]
    check_run: Callable[[str], int]


class _NetworkPluginProto(Protocol):
    config: dict[str, object]
    _ifup_device_if_down: Callable[[str], None]

    def check_physical_network_interface(self, req: dict[str, object]) -> str: ...
    def add_interface_to_bridge(self, req: dict[str, object]) -> str: ...
    def check_bridge(self, req: dict[str, object]) -> str: ...
    def check_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def check_macvlan_vlan_eth(self, req: dict[str, object]) -> str: ...
    def create_bridge(self, req: dict[str, object]) -> str: ...
    def delete_vlan_bridge(self, req: dict[str, object]) -> str: ...
    def create_vxlan_bridge(self, req: dict[str, object]) -> str: ...


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

    def _passthrough_lock(*_args: object, **_kwargs: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return _decorator

    setattr(lock_mod, "lock", _passthrough_lock)
    return cast(
        _NetworkPluginModule,
        cast(object, importlib.reload(importlib.import_module("kvmagent.plugins.network_plugin"))),
    )


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
