from __future__ import annotations

import importlib
import json
import pytest
import sys
import tempfile
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _MevocoPluginProto(Protocol):
    config: dict[str, object]
    _apply_dns_forward: Callable[..., None]
    _apply_userdata_restart_httpd: Callable[..., None]
    _apply_userdata_vmdata: Callable[..., None]
    _apply_userdata_xtables: Callable[..., None]
    _del_bridge_fdb_entry_for_inner_dev: Callable[..., None]
    _delete_dhcp: Callable[..., None]
    _delete_dhcp4: Callable[..., None]
    _delete_dhcp6: Callable[..., None]
    _refresh_dnsmasq: Callable[..., None]
    do_apply_dhcp: Callable[..., None]
    _make_conf_path: Callable[..., tuple[str, str, str, str, str]]
    _remove_dns_forward: Callable[..., None]
    _restart_dnsmasq: Callable[..., None]
    restore_ebtables_chain_except_kvmagent: Callable[[], None]
    userData_vms: dict[str, list[str]]

    def arping_dhcp_namespace(self, req: dict[str, object]) -> str: ...
    def apply_dhcp(self, req: dict[str, object]) -> str: ...
    def apply_userdata(self, req: dict[str, object]) -> str: ...
    def batch_apply_dhcp(self, req: dict[str, object]) -> str: ...
    def batch_apply_userdata(self, req: dict[str, object]) -> str: ...
    def batch_prepare_dhcp(self, req: dict[str, object]) -> str: ...
    def delete_dhcp_namespace(self, req: dict[str, object]) -> str: ...
    def setup_dns_forward(self, req: dict[str, object]) -> str: ...
    def flush_dhcp_namespace(self, req: dict[str, object]) -> str: ...
    def remove_dns_forward(self, req: dict[str, object]) -> str: ...
    def prepare_dhcp(self, req: dict[str, object]) -> str: ...
    def connect(self, req: dict[str, object]) -> str: ...
    def reset_default_gateway(self, req: dict[str, object]) -> str: ...


class _MevocoModule(Protocol):
    iproute: object
    ip: object
    linux: object
    Mevoco: type[_MevocoPluginProto]


class _LockModule(Protocol):
    lock: Callable[..., Callable[[Callable[..., object]], Callable[..., object]]]

from collections.abc import MutableSet

collections = importlib.import_module("collections")
if not hasattr(collections, "MutableSet"):
    setattr(collections, "MutableSet", MutableSet)

_ = sys.modules.setdefault("plugin", MagicMock())
_ = sys.modules.setdefault("traceable_shell", MagicMock())
_ = sys.modules.setdefault("report", MagicMock())
_ = sys.modules.setdefault("linux", MagicMock())
_ = sys.modules.setdefault("pyparsing", MagicMock())

try:
    mevoco = cast(
        _MevocoModule,
        cast(object, importlib.import_module("kvmagent.plugins.mevoco")),
    )
except Exception as e:
    pytest.skip(f"Cannot import mevoco: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_plugin() -> _MevocoPluginProto:
    lock_mod = cast(_LockModule, cast(object, importlib.import_module("zstacklib.utils.lock")))

    def _passthrough_lock(*_args: object, **_kwargs: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return _decorator

    lock_mod.lock = _passthrough_lock

    _ = importlib.reload(importlib.import_module("kvmagent.plugins.mevoco"))
    plugin = mevoco.Mevoco.__new__(mevoco.Mevoco)
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


@pytest.mark.kvmagent
class TestMevocoSetupDnsForward:
    def test_setup_dns_forward_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_apply_dns_forward", MagicMock())

        req = _make_req({'nameSpace': 'ns1', 'mac': 'fa:16:3e:00:00:01', 'dns': '8.8.8.8', 'wrongDns': []})
        result = plugin.setup_dns_forward(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoRemoveDnsForward:
    def test_remove_dns_forward_success(self):
        plugin = _make_plugin()
        setattr(
            plugin,
            "_make_conf_path",
            MagicMock(return_value=('/tmp/conf', '/tmp/dhcp', '/tmp/dns', '/tmp/opt', '/tmp/log')),
        )
        setattr(plugin, "_remove_dns_forward", MagicMock())
        setattr(plugin, "_restart_dnsmasq", MagicMock())

        req = _make_req({'nameSpace': 'ns1', 'mac': 'fa:16:3e:00:00:01'})
        result = plugin.remove_dns_forward(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoConnect:
    def test_connect_success(self):
        plugin = _make_plugin()
        setattr(plugin, "restore_ebtables_chain_except_kvmagent", MagicMock())

        req = _make_req()
        result = plugin.connect(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoDeleteDhcpNamespace:
    def test_delete_dhcp_namespace_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_del_bridge_fdb_entry_for_inner_dev", MagicMock())
        setattr(plugin, "_delete_dhcp", MagicMock())

        req = _make_req({'bridgeName': 'br0', 'namespaceName': 'ns-delete'})
        result = plugin.delete_dhcp_namespace(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoFlushDhcpNamespace:
    def test_flush_dhcp_namespace_success(self):
        plugin = _make_plugin()
        ns_mock = MagicMock()
        setattr(mevoco, "DhcpNameSpaceEnv", MagicMock(return_value=ns_mock))

        req = _make_req({'bridgeName': 'br1', 'namespaceName': 'ns-flush'})
        result = plugin.flush_dhcp_namespace(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, ns_mock.disable).called


@pytest.mark.kvmagent
class TestMevocoArpingDhcpNamespace:
    def test_arping_dhcp_namespace_success(self):
        plugin = _make_plugin()
        ns_mock = MagicMock()
        ns_mock.ns_new_created = True
        setattr(mevoco, "NamespaceInfraEnv", MagicMock(return_value=ns_mock))
        setattr(plugin, "_Mevoco__do_arping_namepsace", MagicMock(return_value=['aa:bb:cc:dd:ee:ff']))

        req = _make_req({'bridgeName': 'br2', 'namespaceName': 'ns-arp', 'targetIps': ['192.168.0.10']})
        result = plugin.arping_dhcp_namespace(req)
        rsp = _load_rsp(result)

        result_map = cast(dict[str, list[str]], rsp['result'])
        assert result_map['192.168.0.10'] == ['aa:bb:cc:dd:ee:ff']
        assert cast(MagicMock, ns_mock.delete_dev).called


@pytest.mark.kvmagent
class TestMevocoPrepareDhcp:
    def test_prepare_dhcp_success(self):
        plugin = _make_plugin()
        dhcp_env_instance = MagicMock()
        setattr(mevoco, "DhcpEnv", MagicMock(return_value=dhcp_env_instance))

        ipnetns_instance = MagicMock()
        ipnetns_instance.get_ip_address.return_value = None
        ipnetns_class = MagicMock(return_value=ipnetns_instance)
        ipnetns_class.get_netns_id = MagicMock(return_value="42")
        setattr(mevoco.iproute, "IpNetnsShell", ipnetns_class)

        setattr(plugin, "_delete_dhcp", MagicMock())

        req = _make_req({
            'bridgeName': 'br0',
            'vlanId': 10,
            'dhcpServerIp': '192.168.0.1',
            'dhcp6ServerIp': 'fd00::1',
            'dhcpNetmask': '255.255.255.0',
            'namespaceName': 'ns-prepare',
            'ipVersion': 4,
            'prefixLen': 64,
            'addressMode': 'stateful',
        })
        result = plugin.prepare_dhcp(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, dhcp_env_instance.prepare).called


@pytest.mark.kvmagent
class TestMevocoBatchPrepareDhcp:
    def test_batch_prepare_dhcp_success(self):
        plugin = _make_plugin()
        dhcp_env_instance = MagicMock()
        setattr(mevoco, "DhcpEnv", MagicMock(return_value=dhcp_env_instance))
        setattr(plugin, "_delete_dhcp4", MagicMock())
        setattr(plugin, "_delete_dhcp6", MagicMock())

        ipnetns_instance = MagicMock()
        ipnetns_instance.get_ip_address.return_value = None
        ipnetns_class = MagicMock(return_value=ipnetns_instance)
        setattr(mevoco.iproute, "IpNetnsShell", ipnetns_class)
        setattr(mevoco.ip, "get_namespace_id", MagicMock(return_value="7"))

        req = _make_req({
            'dhcpInfos': [
                {
                    'bridgeName': 'br0',
                    'vlanId': 10,
                    'dhcpServerIp': '192.168.1.1',
                    'dhcp6ServerIp': 'fd00::1',
                    'dhcpNetmask': '255.255.255.0',
                    'namespaceName': 'ns-batch-1',
                    'ipVersion': 4,
                    'prefixLen': 64,
                    'addressMode': 'stateful',
                },
                {
                    'bridgeName': 'br1',
                    'vlanId': 11,
                    'dhcpServerIp': '192.168.2.1',
                    'dhcp6ServerIp': 'fd00::2',
                    'dhcpNetmask': '255.255.255.0',
                    'namespaceName': 'ns-batch-2',
                    'ipVersion': 6,
                    'prefixLen': 64,
                    'addressMode': 'stateful',
                },
            ]
        })
        result = plugin.batch_prepare_dhcp(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert dhcp_env_instance.prepare.call_count == 2


@pytest.mark.kvmagent
class TestMevocoResetDefaultGateway:
    def test_reset_default_gateway_success(self):
        plugin = _make_plugin()
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.close()

        setattr(
            plugin,
            "_make_conf_path",
            MagicMock(return_value=("/tmp/conf", "/tmp/dhcp", "/tmp/dns", tmp_file.name, "/tmp/log")),
        )
        setattr(plugin, "_refresh_dnsmasq", MagicMock())
        setattr(mevoco.linux, "delete_lines_from_file", MagicMock())

        req = _make_req({
            'namespaceNameOfGatewayToRemove': 'ns-remove',
            'macOfGatewayToRemove': 'fa:16:3e:00:00:01',
            'gatewayToRemove': '192.168.0.1',
            'namespaceNameOfGatewayToAdd': 'ns-add',
            'macOfGatewayToAdd': 'fa:16:3e:00:00:02',
            'gatewayToAdd': '192.168.0.2',
        })
        result = plugin.reset_default_gateway(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._refresh_dnsmasq).call_count == 2


@pytest.mark.kvmagent
class TestMevocoApplyDhcp:
    def test_apply_dhcp_success(self):
        plugin = _make_plugin()
        setattr(plugin, "do_apply_dhcp", MagicMock())

        req = _make_req({
            'dhcp': [{'namespaceName': 'ns-apply'}],
            'rebuild': False,
        })
        result = plugin.apply_dhcp(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin.do_apply_dhcp).called


@pytest.mark.kvmagent
class TestMevocoBatchApplyDhcp:
    def test_batch_apply_dhcp_success(self):
        plugin = _make_plugin()
        setattr(plugin, "do_apply_dhcp", MagicMock())

        req = _make_req({
            'dhcpInfos': [
                {'dhcp': [{'namespaceName': 'ns-batch'}]},
            ],
            'rebuild': True,
        })
        result = plugin.batch_apply_dhcp(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin.do_apply_dhcp).called


@pytest.mark.kvmagent
class TestMevocoApplyUserdata:
    def test_apply_userdata_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_apply_userdata_xtables", MagicMock())
        setattr(plugin, "_apply_userdata_vmdata", MagicMock())
        setattr(plugin, "_apply_userdata_restart_httpd", MagicMock())

        req = _make_req({'userdata': {'bridgeName': 'br0', 'namespaceName': 'ns', 'vlanId': 10}})
        result = plugin.apply_userdata(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._apply_userdata_xtables).called
        assert cast(MagicMock, plugin._apply_userdata_vmdata).called
        assert cast(MagicMock, plugin._apply_userdata_restart_httpd).called


@pytest.mark.kvmagent
class TestMevocoBatchApplyUserdata:
    def test_batch_apply_userdata_success(self):
        plugin = _make_plugin()
        plugin.userData_vms = {}
        setattr(plugin, "_apply_userdata_xtables", MagicMock())
        setattr(plugin, "_apply_userdata_vmdata", MagicMock())
        setattr(plugin, "_apply_userdata_restart_httpd", MagicMock())

        req = _make_req({
            'rebuild': False,
            'userdata': [
                {
                    'l3NetworkUuid': 'l3-uuid',
                    'vmIp': '10.0.0.2',
                    'namespaceName': 'ns-userdata',
                    'dhcpServerIp': '10.0.0.1',
                    'bridgeName': 'br0',
                    'port': 80,
                },
            ],
        })
        result = plugin.batch_apply_userdata(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._apply_userdata_xtables).called
        assert cast(MagicMock, plugin._apply_userdata_vmdata).called
        assert cast(MagicMock, plugin._apply_userdata_restart_httpd).called
