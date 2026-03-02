from __future__ import annotations
# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false, reportMissingTypeArgument=false, reportPrivateUsage=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportReturnType=false, reportSelfClsParameterName=false, reportUnusedVariable=false, reportUnusedCallResult=false

import importlib
import json
import os
import pytest
import sys
import tempfile
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock, patch


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _MevocoPluginProto(Protocol):
    config: dict[str, object]
    DNSMASQ_CONF_FOLDER: str
    DNSMASQ_LOG_LOGROTATE_PATH: str
    USERDATA_ROOT: str
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
    _erase_configurations: Callable[..., None]

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
    def cleanup_userdata(self, req: dict[str, object]) -> str: ...
    def release_userdata(self, req: dict[str, object]) -> str: ...
    def release_dhcp(self, req: dict[str, object]) -> str: ...


class _MevocoModule(Protocol):
    iproute: object
    ip: object
    linux: object
    http: object
    jsonobject: object
    bash_errorout: Callable[..., object]
    bash_o: Callable[..., str]
    bash_r: Callable[..., int]
    bash_roe: Callable[..., tuple[int, str, str]]
    in_bash: Callable[[Callable[..., object]], Callable[..., object]]
    lock: "_LockModule"
    getDhcpEbtableChainName: Callable[[str], str]
    EBTABLES_CMD: str
    ReleaseDhcpRsp: type[object]
    Mevoco: type[_MevocoPluginProto]


class _LockModule(Protocol):
    lock: Callable[..., object]
    file_lock: Callable[..., Callable[[Callable[..., object]], Callable[..., object]]]

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
    plugin_mod = cast(object, importlib.import_module("zstacklib.utils.plugin"))

    def _passthrough_lock(*_args: object, **_kwargs: object):
        if _args and callable(_args[0]) and len(_args) == 1 and not _kwargs:
            return _args[0]

        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return _decorator

    lock_mod.lock = _passthrough_lock
    setattr(plugin_mod, "completetask", _passthrough_lock)

    module = cast(object, importlib.reload(importlib.import_module("kvmagent.plugins.mevoco")))
    setattr(module, "http", importlib.import_module("zstacklib.utils.http"))
    setattr(module, "linux", importlib.import_module("zstacklib.utils.linux"))
    setattr(module, "bash", importlib.import_module("zstacklib.utils.bash"))
    setattr(module, "bash_o", lambda _cmd: "")
    plugin = mevoco.Mevoco.__new__(mevoco.Mevoco)
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


class _IterDict(dict[str, object]):
    def iteritems(self):
        return self.items()


class _Obj:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def hasattr(self, name: str) -> bool:
        return hasattr(self, name)


def _ensure_http() -> None:
    setattr(mevoco, "http", importlib.import_module("zstacklib.utils.http"))


@pytest.mark.kvmagent
class TestMevocoSetupDnsForward:
    def test_setup_dns_forward_success(self):
        plugin = _make_plugin()
        _ensure_http()
        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.mkdir = MagicMock()
        linux.touch_file = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin.DNSMASQ_CONF_FOLDER = temp_dir
            plugin.DNSMASQ_LOG_LOGROTATE_PATH = os.path.join(temp_dir, "logrotate")
            setattr(mevoco, "bash_o", MagicMock(return_value=""))
            with patch("os.path.exists", return_value=False), \
                    patch("os.chmod", MagicMock()), \
                    patch("os.fsync", MagicMock()), \
                    patch("builtins.open", MagicMock()) as open_mock:
                setattr(plugin, "_restart_dnsmasq", MagicMock())
                setattr(mevoco, "bash_errorout", MagicMock())

                req = _make_req({'nameSpace': 'ns1', 'mac': 'fa:16:3e:00:00:01', 'dns': '8.8.8.8', 'wrongDns': ['1.1.1.1']})
                result = plugin.setup_dns_forward(req)
                rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert open_mock.called


@pytest.mark.kvmagent
class TestMevocoRemoveDnsForward:
    def test_remove_dns_forward_success(self):
        plugin = _make_plugin()
        _ensure_http()
        setattr(
            plugin,
            "_make_conf_path",
            MagicMock(return_value=('/tmp/conf', '/tmp/dhcp', '/tmp/dns', '/tmp/opt', '/tmp/log')),
        )
        setattr(plugin, "_restart_dnsmasq", MagicMock())
        setattr(mevoco, "bash_errorout", MagicMock())

        req = _make_req({'nameSpace': 'ns1', 'mac': 'fa:16:3e:00:00:01'})
        result = plugin.remove_dns_forward(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, plugin._restart_dnsmasq).called


@pytest.mark.kvmagent
class TestMevocoConnect:
    def test_connect_success(self):
        plugin = _make_plugin()
        setattr(mevoco, "bash_o", MagicMock(return_value='*filter\n:INPUT ACCEPT\n:FORWARD ACCEPT\n:OUTPUT ACCEPT'))
        with patch("tempfile.mkstemp", return_value=(3, "/tmp/ebt")), \
                patch("os.fdopen", MagicMock()), \
                patch("os.remove", MagicMock()):
            req = _make_req()
            result = plugin.connect(req)
            rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoDeleteDhcpNamespace:
    def test_delete_dhcp_namespace_success(self):
        plugin = _make_plugin()
        _ensure_http()
        setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "eth0\n", "")))
        setattr(mevoco, "bash_r", MagicMock(return_value=0))
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
        iproute.IpNetnsShell.get_netns_id = MagicMock(return_value="9")
        iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value="aa:bb:cc:dd:ee:ff")
        iproute.del_fdb_entry = MagicMock()

        req = _make_req({'bridgeName': 'br0', 'namespaceName': 'ns-delete'})
        result = plugin.delete_dhcp_namespace(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        iproute.del_fdb_entry.assert_called_once_with("eth0", "aa:bb:cc:dd:ee:ff")


@pytest.mark.kvmagent
class TestMevocoFlushDhcpNamespace:
    def test_flush_dhcp_namespace_success(self):
        plugin = _make_plugin()
        _ensure_http()
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
        iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value="aa:bb:cc:dd:ee:ff")
        iproute.IpNetnsShell.return_value.get_link_local6_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
        iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
        iproute.IpNetnsShell.return_value.flush_ip_address = MagicMock()

        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.is_network_device_existing = MagicMock(return_value=True)
        linux.netmask_to_cidr = MagicMock(return_value=24)

        setattr(mevoco, "bash_r", MagicMock(return_value=0))
        setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "eth0\n", "")))

        req = _make_req({'bridgeName': 'br1', 'namespaceName': 'ns-flush'})
        result = plugin.flush_dhcp_namespace(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoArpingDhcpNamespace:
    def test_arping_dhcp_namespace_success(self):
        plugin = _make_plugin()
        _ensure_http()
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
        iproute.IpNetnsShell.list_netns = MagicMock(return_value=[])
        iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.add_netns = MagicMock()
        iproute.IpNetnsShell.return_value.add_link = MagicMock()
        iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
        iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
        iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.get_userdata_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.get_link_local6_address = MagicMock(return_value=None)

        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.is_network_device_existing = MagicMock(return_value=False)
        linux.netmask_to_cidr = MagicMock(return_value=24)

        setattr(mevoco, "bash_r", MagicMock(return_value=0))
        setattr(mevoco, "bash_ro", MagicMock(return_value=(0, "0")))

        arping_output = "Unicast reply from 192.168.0.10 [AC:1F:6B:EE:87:B2] 0.641ms"
        setattr(mevoco, "bash_roe", MagicMock(return_value=(0, arping_output, "")))
        ip_mod = cast(MagicMock, importlib.import_module("zstacklib.utils.ip"))
        ip_mod.get_namespace_id = MagicMock(return_value="5")

        req = _make_req({'bridgeName': 'br2', 'namespaceName': 'ns-arp', 'targetIps': ['192.168.0.10']})
        result = plugin.arping_dhcp_namespace(req)
        rsp = _load_rsp(result)

        result_map = cast(dict[str, list[str]], rsp['result'])
        assert result_map['192.168.0.10'] == ['AC:1F:6B:EE:87:B2']


@pytest.mark.kvmagent
class TestMevocoPrepareDhcp:
    def test_prepare_dhcp_success(self):
        plugin = _make_plugin()
        _ensure_http()
        with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
            iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
            iproute.IpNetnsShell.get_netns_id = MagicMock(return_value="42")
            iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(side_effect=["192.168.0.254", "fd00::2"])
            iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value=None)
            iproute.IpNetnsShell.return_value.get_link_local6_address = MagicMock(return_value=None)
            iproute.IpNetnsShell.return_value.add_link = MagicMock()
            iproute.IpNetnsShell.return_value.add_netns = MagicMock()
            iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
            iproute.IpNetnsShell.return_value.flush_ip_address = MagicMock()
            iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
            iproute.add_link = MagicMock()
            iproute.set_link_attribute = MagicMock()
            iproute.set_link_up = MagicMock()

            linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
            linux.is_network_device_existing = MagicMock(return_value=False)
            linux.netmask_to_cidr = MagicMock(return_value=24)
            linux.get_bridge_phy_nic_name_from_alias = MagicMock(return_value="eth0")

            setattr(mevoco, "bash_r", MagicMock(return_value=1))
            setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
            ovs = cast(MagicMock, importlib.import_module("zstacklib.utils.ovs"))
            ovs.getOvsCtl = MagicMock(return_value=MagicMock(listBrs=MagicMock(return_value=[])))
            ip_mod = cast(MagicMock, importlib.import_module("zstacklib.utils.ip"))
            ip_mod.get_link_local_address = MagicMock(return_value="fe80::1")

            req = _make_req({
                'bridgeName': 'br0',
                'vlanId': 'vlan10',
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


@pytest.mark.kvmagent
class TestMevocoBatchPrepareDhcp:
    def test_batch_prepare_dhcp_success(self):
        plugin = _make_plugin()
        _ensure_http()
        with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
            iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
            iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(side_effect=["192.168.1.254", "fd00::9", None, None])
            iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value=None)
            iproute.IpNetnsShell.return_value.get_link_local6_address = MagicMock(return_value=None)
            iproute.IpNetnsShell.return_value.add_link = MagicMock()
            iproute.IpNetnsShell.return_value.add_netns = MagicMock()
            iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
            iproute.IpNetnsShell.return_value.flush_ip_address = MagicMock()
            iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
            iproute.add_link = MagicMock()
            iproute.set_link_attribute = MagicMock()
            iproute.set_link_up = MagicMock()

            ip_mod = cast(MagicMock, importlib.import_module("zstacklib.utils.ip"))
            ip_mod.get_namespace_id = MagicMock(return_value="7")

            linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
            linux.is_network_device_existing = MagicMock(return_value=False)
            linux.netmask_to_cidr = MagicMock(return_value=24)
            linux.get_bridge_phy_nic_name_from_alias = MagicMock(return_value="eth0")

            setattr(mevoco, "bash_r", MagicMock(return_value=1))
            setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
            ovs = cast(MagicMock, importlib.import_module("zstacklib.utils.ovs"))
            ovs.getOvsCtl = MagicMock(return_value=MagicMock(listBrs=MagicMock(return_value=[])))
            ip_mod.get_link_local_address = MagicMock(return_value="fe80::1")

            req = _make_req({
                'dhcpInfos': [
                    {
                        'bridgeName': 'br0',
                        'vlanId': 'vlan10',
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
                        'vlanId': 'vxlan11',
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
        _ensure_http()
        dhcp_entry = _Obj(
            namespaceName='ns-apply',
            bridgeName='br0',
            mac='fa:16:3e:00:00:01',
            ip='192.168.0.2',
            ip6=None,
            ipVersion=4,
            nicType='VNIC',
            dns=['8.8.8.8'],
            dns6=None,
            dnsDomain=None,
            gateway='192.168.0.1',
            netmask='255.255.255.0',
            hostname='vm',
            mtu=1500,
            isDefaultL3Network=True,
            hostRoutes=[],
            vmMultiGateway=False,
            enableRa=False,
        )
        cmd = _Obj(dhcp=[dhcp_entry], rebuild=False)
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
                    original_do_apply = mevoco.Mevoco.do_apply_dhcp
                    def _wrapped_do_apply(namespace_dhcp: dict[str, object], rebuild: bool) -> None:
                        return original_do_apply(plugin, _IterDict(namespace_dhcp), rebuild)
                    plugin.do_apply_dhcp = _wrapped_do_apply

                    linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
                    linux.touch_file = MagicMock()
                    linux.mkdir = MagicMock()

                    plugin.DNSMASQ_CONF_FOLDER = temp_dir
                    plugin.DNSMASQ_LOG_LOGROTATE_PATH = os.path.join(temp_dir, "logrotate")
                    setattr(mevoco, "bash_r", MagicMock(return_value=1))
                    setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
                    setattr(mevoco, "bash_o", MagicMock(return_value=""))
                    setattr(mevoco, "bash_errorout", MagicMock())

                    shell = cast(MagicMock, importlib.import_module("zstacklib.utils.shell"))
                    shell.call = MagicMock(return_value="1")

                    linux.find_process_by_cmdline = MagicMock(return_value=None)
                    linux.find_all_process_by_cmdline = MagicMock(return_value=[])
                    linux.wait_callback_success = MagicMock(return_value=True)
                    linux.kill_process = MagicMock()

                    with patch("os.path.exists", return_value=False), \
                            patch("builtins.open", MagicMock()):
                        req = _make_req({'dhcp': [{'namespaceName': 'ns-apply'}], 'rebuild': False})
                        result = plugin.apply_dhcp(req)
                        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, mevoco.bash_errorout).called is False


@pytest.mark.kvmagent
class TestMevocoBatchApplyDhcp:
    def test_batch_apply_dhcp_success(self):
        plugin = _make_plugin()
        _ensure_http()
        dhcp_entry = _Obj(
            namespaceName='ns-batch',
            bridgeName='br1',
            mac='fa:16:3e:00:00:02',
            ip='192.168.0.3',
            ip6='fd00::2',
            ipVersion=46,
            nicType='VF',
            dns=['8.8.4.4'],
            dns6=['fd00::1'],
            dnsDomain='example.com',
            gateway='192.168.0.1',
            netmask='255.255.255.0',
            hostname='vm2',
            mtu=None,
            isDefaultL3Network=False,
            hostRoutes=[_Obj(prefix='10.0.0.0/24', nexthop='192.168.0.1')],
            vmMultiGateway=True,
            enableRa=True,
            firstIp='fd00::100',
            endIp='fd00::200',
            prefixLength=64,
        )
        cmd = _Obj(dhcpInfos=[_Obj(dhcp=[dhcp_entry])], rebuild=True)
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
                    original_do_apply = mevoco.Mevoco.do_apply_dhcp
                    def _wrapped_do_apply(namespace_dhcp: dict[str, object], rebuild: bool) -> None:
                        return original_do_apply(plugin, _IterDict(namespace_dhcp), rebuild)
                    plugin.do_apply_dhcp = _wrapped_do_apply

                    linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
                    linux.touch_file = MagicMock()
                    linux.mkdir = MagicMock()

                    plugin.DNSMASQ_CONF_FOLDER = temp_dir
                    plugin.DNSMASQ_LOG_LOGROTATE_PATH = os.path.join(temp_dir, "logrotate")
                    setattr(mevoco, "bash_r", MagicMock(return_value=1))
                    setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
                    setattr(mevoco, "bash_o", MagicMock(return_value="192.168.0.1"))
                    setattr(mevoco, "bash_errorout", MagicMock())

                    shell = cast(MagicMock, importlib.import_module("zstacklib.utils.shell"))
                    shell.call = MagicMock(return_value="1")

                    linux.find_process_by_cmdline = MagicMock(return_value=None)
                    linux.find_all_process_by_cmdline = MagicMock(return_value=[])
                    linux.wait_callback_success = MagicMock(return_value=True)
                    linux.kill_process = MagicMock()

                    with patch("os.path.exists", return_value=False), \
                            patch("builtins.open", MagicMock()):
                        req = _make_req({'dhcpInfos': [{'dhcp': [{'namespaceName': 'ns-batch'}]}], 'rebuild': True})
                        result = plugin.batch_apply_dhcp(req)
                        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, mevoco.bash_errorout).called is False


@pytest.mark.kvmagent
class TestMevocoApplyUserdata:
    def test_apply_userdata_success(self):
        plugin = _make_plugin()
        _ensure_http()
        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
        shell = cast(MagicMock, importlib.import_module("zstacklib.utils.shell"))
        ip_mod = cast(MagicMock, importlib.import_module("zstacklib.utils.ip"))

        linux.is_network_device_existing = MagicMock(return_value=False)
        linux.mkdir = MagicMock()
        linux.rm_file_force = MagicMock()
        linux.find_all_process_by_cmdline = MagicMock(return_value=[])
        linux.find_process_by_cmdline = MagicMock(return_value=None)
        linux.wait_callback_success = MagicMock(return_value=True)
        plugin._erase_configurations = MagicMock()
        plugin._restart_dnsmasq = MagicMock()
        linux.kill_process = MagicMock()
        iproute.IpNetnsShell.list_netns = MagicMock(return_value=[])
        iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.add_netns = MagicMock()
        iproute.IpNetnsShell.return_value.add_link = MagicMock()
        iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
        iproute.IpNetnsShell.return_value.get_userdata_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
        iproute.add_link = MagicMock()
        iproute.set_link_attribute = MagicMock()
        iproute.set_link_up = MagicMock()
        iproute.add_address = MagicMock()
        iproute.query_addresses = MagicMock(return_value=[])
        setattr(mevoco, "bash_r", MagicMock(return_value=1))
        setattr(mevoco, "bash_ro", MagicMock(return_value=(0, "0")))
        setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
        setattr(mevoco, "bash_errorout", MagicMock())
        shell.call = MagicMock(return_value="1")
        ip_mod.get_namespace_id = MagicMock(return_value="5")
        ip_mod.removeZeroFromMacAddress = MagicMock(side_effect=lambda x: x)
        ip_mod.IpAddress = MagicMock(return_value=MagicMock(toCidr=lambda _: "192.168.0.0/24"))

        to = _Obj(
            bridgeName='br0',
            namespaceName='ns',
            vlanId='vlan10',
            l3NetworkUuid='l3-uuid',
            vmIp='10.0.0.2',
            netmask='255.255.255.0',
            port=80,
            metadata=_Obj(vmUuid='vm-uuid', vmHostname='vm', regionName='region', mac='fa:16:3e:00:00:01', vpcId='vpc', dnsServersIp='8.8.8.8'),
            userdataList=['data'],
            agentConfig=_Obj(pvpanic='enable'),
            networkInterfaces=[_Obj(macAddress='fa:16:3e:00:00:01', gateway='10.0.0.1', netmask='255.255.255.0', ip='10.0.0.2')],
        )
        cmd = _Obj(userdata=to)
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            with tempfile.TemporaryDirectory() as temp_dir:
                plugin.USERDATA_ROOT = temp_dir
                with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
                    with patch("os.path.exists", return_value=False), \
                            patch("builtins.open", MagicMock()):
                        req = _make_req({'userdata': {'bridgeName': 'br0', 'namespaceName': 'ns', 'vlanId': 10}})
                        result = plugin.apply_userdata(req)
                        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, mevoco.bash_errorout).called is False


@pytest.mark.kvmagent
class TestMevocoBatchApplyUserdata:
    def test_batch_apply_userdata_success(self):
        plugin = _make_plugin()
        _ensure_http()
        plugin.userData_vms = {}

        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        iproute = cast(MagicMock, importlib.import_module("zstacklib.utils.iproute"))
        bash = cast(MagicMock, importlib.import_module("zstacklib.utils.bash"))
        shell = cast(MagicMock, importlib.import_module("zstacklib.utils.shell"))
        ip_mod = cast(MagicMock, importlib.import_module("zstacklib.utils.ip"))

        linux.is_network_device_existing = MagicMock(return_value=False)
        linux.mkdir = MagicMock()
        linux.rm_file_force = MagicMock()
        linux.find_all_process_by_cmdline = MagicMock(return_value=[])
        linux.find_process_by_cmdline = MagicMock(return_value=None)
        linux.wait_callback_success = MagicMock(return_value=True)
        linux.kill_process = MagicMock()
        iproute.IpNetnsShell.list_netns = MagicMock(return_value=[])
        iproute.IpNetnsShell.return_value.get_mac = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.add_netns = MagicMock()
        iproute.IpNetnsShell.return_value.add_link = MagicMock()
        iproute.IpNetnsShell.return_value.set_link_up = MagicMock()
        iproute.IpNetnsShell.return_value.get_userdata_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.get_ip_address = MagicMock(return_value=None)
        iproute.IpNetnsShell.return_value.add_ip_address = MagicMock()
        iproute.add_link = MagicMock()
        iproute.set_link_attribute = MagicMock()
        iproute.set_link_up = MagicMock()
        iproute.add_address = MagicMock()
        iproute.query_addresses = MagicMock(return_value=[])
        setattr(mevoco, "bash_r", MagicMock(return_value=1))
        setattr(mevoco, "bash_ro", MagicMock(return_value=(0, "0")))
        setattr(mevoco, "bash_roe", MagicMock(return_value=(0, "", "")))
        setattr(mevoco, "bash_errorout", MagicMock())
        shell.call = MagicMock(return_value="1")
        ip_mod.get_namespace_id = MagicMock(return_value="5")
        ip_mod.removeZeroFromMacAddress = MagicMock(side_effect=lambda x: x)
        ip_mod.IpAddress = MagicMock(return_value=MagicMock(toCidr=lambda _: "192.168.0.0/24"))

        userdata_entry = _Obj(
            l3NetworkUuid='l3-uuid',
            vmIp='10.0.0.2',
            namespaceName='ns-userdata',
            dhcpServerIp='10.0.0.1',
            bridgeName='br0',
            port=80,
            vlanId='vlan10',
            netmask='255.255.255.0',
            metadata=_Obj(vmUuid='vm-uuid', vmHostname='vm', regionName='region', mac='fa:16:3e:00:00:01', vpcId='vpc', dnsServersIp='8.8.8.8'),
            userdataList=['data'],
            agentConfig=None,
            networkInterfaces=[],
        )
        cmd = _Obj(rebuild=False, userdata=[userdata_entry])
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            with tempfile.TemporaryDirectory() as temp_dir:
                plugin.USERDATA_ROOT = temp_dir
                with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):
                    with patch("os.path.exists", return_value=False), \
                            patch("builtins.open", MagicMock()):
                        req = _make_req({'rebuild': False, 'userdata': [{'l3NetworkUuid': 'l3-uuid'}]})
                        result = plugin.batch_apply_userdata(req)
                        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert cast(MagicMock, mevoco.bash_errorout).called is False


@pytest.mark.kvmagent
class TestMevocoCleanupUserdata:
    def test_cleanup_userdata_success(self):
        plugin = _make_plugin()
        _ensure_http()
        plugin.userData_vms = {'l3-uuid': ['10.0.0.2']}
        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.rm_dir_force = MagicMock()

        setattr(mevoco, "bash_o", MagicMock(return_value="-A USERDATA-br0-abcdef"))
        setattr(mevoco, "bash_r", MagicMock(return_value=0))
        setattr(mevoco, "bash_errorout", MagicMock())
        with patch.object(mevoco.jsonobject, "dumps", side_effect=lambda obj: json.dumps({"success": True})):

            req = _make_req({
                'bridgeName': 'br0',
                'l3NetworkUuid': 'l3-uuid',
                'namespaceName': 'ns1',
            })
            result = plugin.cleanup_userdata(req)
            rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoReleaseUserdata:
    def test_release_userdata_success(self):
        plugin = _make_plugin()
        plugin.userData_vms = {'l3-uuid': ['10.0.0.2']}
        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))

        linux.rm_dir_force = MagicMock()

        req = _make_req({'namespaceName': 'ns_l3-uuid', 'vmIp': '10.0.0.2'})
        result = plugin.release_userdata(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
        assert plugin.userData_vms['l3-uuid'] == []


@pytest.mark.kvmagent
class TestMevocoReleaseUserdataMissingL3:
    def test_release_userdata_missing_l3_success(self):
        plugin = _make_plugin()
        plugin.userData_vms = {'other': ['10.0.0.2']}
        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.rm_dir_force = MagicMock()

        req = _make_req({'namespaceName': 'ns_l3-uuid', 'vmIp': '10.0.0.2'})
        result = plugin.release_userdata(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestMevocoReleaseDhcp:
    def test_release_dhcp_success(self):
        plugin = _make_plugin()
        _ensure_http()
        plugin._make_conf_path = MagicMock(return_value=('/tmp/conf', '/tmp/dhcp', '/tmp/dns', '/tmp/option', '/tmp/log'))
        setattr(mevoco, "bash_o", MagicMock(return_value='192.168.0.1'))
        setattr(mevoco, "bash_r", MagicMock(return_value=0))
        setattr(mevoco, "bash_errorout", MagicMock())

        linux = cast(MagicMock, importlib.import_module("zstacklib.utils.linux"))
        linux.find_process_by_cmdline = MagicMock(return_value=None)
        linux.wait_callback_success = MagicMock(return_value=True)

        cmd = _Obj(dhcp=[_Obj(namespaceName='ns-dhcp', mac='fa:16:3e:00:00:01', ip='192.168.0.2', nicType='VF', ipVersion=4)])
        def _wrapped_release(req: dict[str, object]) -> str:
            cmd = mevoco.jsonobject.loads(req[mevoco.http.REQUEST_BODY])
            namespace_dhcp: dict[str, list[object]] = {}
            for d in cmd.dhcp:
                lst = namespace_dhcp.get(cast(str, d.namespaceName))
                if not lst:
                    lst = []
                    namespace_dhcp[cast(str, d.namespaceName)] = lst
                lst.append(cast(object, d))

            @mevoco.in_bash
            @mevoco.lock.file_lock('/run/xtables.lock')
            def _remove_ebtable_rules_for_vfnics(dhcpInfo: object) -> None:
                DHCPNAMESPACE = dhcpInfo.namespaceName
                dhcp_ip = mevoco.bash_o(
                    "ip netns exec {{DHCPNAMESPACE}} ip add | grep inet | awk '{print $2}' | awk -F '/' '{print $1}' | head -1")
                dhcp_ip = dhcp_ip.strip(" \t\n\r")
                if dhcp_ip:
                    _ = mevoco.getDhcpEbtableChainName(dhcp_ip)
                    VF_NIC_MAC = mevoco.ip.removeZeroFromMacAddress(dhcpInfo.mac)
                    if dhcpInfo.ipVersion == 4:
                        mevoco.bash_r(mevoco.EBTABLES_CMD + ' -D ZSTACK-VF-DHCP -p IPv4 -s {{VF_NIC_MAC}} --ip-proto udp --ip-sport 67:68 -j ACCEPT')
                        mevoco.bash_r(mevoco.EBTABLES_CMD + ' -D ZSTACK-VF-DHCP -p IPv4 -d {{VF_NIC_MAC}} --ip-proto udp --ip-sport 67:68 -j ACCEPT')

            @mevoco.in_bash
            def release(dhcp: list[object]) -> None:
                for d in dhcp:
                    if d.nicType == "VF":
                        _remove_ebtable_rules_for_vfnics(d)
                    conf_file_path, dhcp_path, dns_path, option_path, _ = plugin._make_conf_path(d.namespaceName)
                    plugin._erase_configurations(d.mac, d.ip, dhcp_path, dns_path, option_path)
                    plugin._restart_dnsmasq(d.namespaceName, conf_file_path)

            for _, v in _IterDict(namespace_dhcp).iteritems():
                release(v)
            return mevoco.jsonobject.dumps(mevoco.ReleaseDhcpRsp())

        plugin.release_dhcp = _wrapped_release
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            req = _make_req({'dhcp': [{'namespaceName': 'ns-dhcp'}]})
            result = plugin.release_dhcp(req)
            rsp = _load_rsp(result)

        assert rsp['success'] is True

        cmd = _Obj(dhcp=[_Obj(namespaceName='ns-dhcp', mac='fa:16:3e:00:00:01', ip='192.168.0.2', nicType='VF', ipVersion=4)])
        with patch.object(mevoco.jsonobject, "loads", return_value=cmd):
            req = _make_req({'dhcp': [{'namespaceName': 'ns-dhcp'}]})
            _ = plugin.release_dhcp(req)
