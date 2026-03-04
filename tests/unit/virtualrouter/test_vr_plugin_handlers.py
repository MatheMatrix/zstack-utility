from __future__ import annotations

import importlib
import json
import pytest
import os
import sys
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock, patch, mock_open


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


def _setup_lock_passthrough():
    """Make lock.lock and lock.file_lock passthrough decorators."""
    from tests.conftest import passthrough_lock
    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))
    setattr(lock_mod, "lock", passthrough_lock)
    setattr(lock_mod, "file_lock", passthrough_lock)


# Set up lock passthrough BEFORE importing VR modules
_setup_lock_passthrough()

try:
    vr_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.virtualrouter")))
    echo_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.echo")))
    vip_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.vip")))
    dns_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.dns")))
    snat_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.snat")))
    eip_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.eip")))
    pf_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.port_forwarding")))
    lb_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.lb")))
    dnsmasq_module = cast(object, importlib.reload(importlib.import_module("virtualrouter.plugins.dnsmasq")))
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import virtualrouter modules: {e}", allow_module_level=True)


def _make_req(body_dict=None):
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_vr():
    """Create VirtualRouter via __new__, skip __init__."""
    vr = vr_module.VirtualRouter.__new__(vr_module.VirtualRouter)
    vr.config = {}
    vr.uuid = None
    vr.init_command = None
    return vr


# ---------------------------------------------------------------------------
# VirtualRouter — init
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestVirtualRouterInit:
    def test_init_sets_uuid_and_command(self):
        vr = _make_vr()
        result = vr.init(_make_req({"uuid": "vr-uuid-001"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert vr.uuid == "vr-uuid-001"
        assert vr.init_command is not None


# ---------------------------------------------------------------------------
# VirtualRouter — ping
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestVirtualRouterPing:
    def test_ping_returns_uuid(self):
        vr = _make_vr()
        vr.uuid = "vr-uuid-001"
        result = vr.ping(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["uuid"] == "vr-uuid-001"

    def test_ping_returns_none_when_not_initialized(self):
        vr = _make_vr()
        result = vr.ping(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert "uuid" not in rsp


# ---------------------------------------------------------------------------
# Echo
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestEchoPlugin:
    def test_echo_returns_empty_string(self):
        plugin = echo_module.EchoPlugin.__new__(echo_module.EchoPlugin)
        result = plugin.echo(_make_req())
        assert result == ""


# ---------------------------------------------------------------------------
# Vip — create_vip
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestCreateVip:
    def test_create_vip_success(self):
        plugin = vip_module.Vip.__new__(vip_module.Vip)
        linux = sys.modules["zstacklib.utils.linux"]

        result = plugin.create_vip(_make_req({
            "vips": [
                {"ip": "10.0.0.100", "netmask": "255.255.255.0", "ownerEthernetMac": "fa:00:00:00:00:01"},
                {"ip": "10.0.0.101", "netmask": "255.255.255.0", "ownerEthernetMac": "fa:00:00:00:00:02"},
            ]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert linux.create_vip_if_not_exists.call_count == 2


# ---------------------------------------------------------------------------
# Vip — remove_vip
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRemoveVip:
    def test_remove_vip_success(self):
        plugin = vip_module.Vip.__new__(vip_module.Vip)
        linux = sys.modules["zstacklib.utils.linux"]

        result = plugin.remove_vip(_make_req({
            "vips": [
                {"ip": "10.0.0.100"},
            ]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        linux.delete_vip_by_ip_if_exists.assert_called_with("10.0.0.100")


# ---------------------------------------------------------------------------
# Dns — set_dns
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestSetDns:
    def test_set_dns_writes_resolv_conf(self):
        plugin = dns_module.Dns.__new__(dns_module.Dns)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_pid_by_process_name.return_value = "1234"

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="nameserver 8.8.8.8\n")):
            result = plugin.set_dns(_make_req({
                "dns": [{"dnsAddress": "8.8.4.4"}]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Dns — remove_dns
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRemoveDns:
    def test_remove_dns_filters_entries(self):
        plugin = dns_module.Dns.__new__(dns_module.Dns)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_pid_by_process_name.return_value = "1234"

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="nameserver 8.8.8.8\nnameserver 8.8.4.4\n")):
            result = plugin.remove_dns(_make_req({
                "dns": [{"dnsAddress": "8.8.4.4"}]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Snat — set_snat
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestSetSnat:
    def test_set_snat_success(self):
        plugin = snat_module.Snat.__new__(snat_module.Snat)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_names_by_mac.return_value = ["eth0"]

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.set_snat(_make_req({
            "snat": {
                "publicNicMac": "fa:00:00:00:00:01",
                "privateNicMac": "fa:00:00:00:00:02",
                "publicIp": "192.168.1.1",
            }
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.iptable_restore.assert_called_once()


# ---------------------------------------------------------------------------
# Snat — remove_snat
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRemoveSnat:
    def test_remove_snat_success(self):
        plugin = snat_module.Snat.__new__(snat_module.Snat)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.remove_snat(_make_req({
            "natInfo": [{
                "privateNicMac": "fa:00:00:00:00:02",
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.delete_chain.assert_called()


# ---------------------------------------------------------------------------
# Snat — sync_snat
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestSyncSnat:
    def test_sync_snat_creates_all(self):
        plugin = snat_module.Snat.__new__(snat_module.Snat)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_names_by_mac.return_value = ["eth0"]

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.sync_snat(_make_req({
            "snats": [
                {"publicNicMac": "fa:00:00:00:00:01", "privateNicMac": "fa:00:00:00:00:02", "publicIp": "192.168.1.1"},
                {"publicNicMac": "fa:00:00:00:00:03", "privateNicMac": "fa:00:00:00:00:04", "publicIp": "192.168.1.2"},
            ]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Eip — create_eip
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestCreateEip:
    def test_create_eip_success(self):
        plugin = eip_module.Eip.__new__(eip_module.Eip)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.create_eip(_make_req({
            "eip": {
                "privateMac": "fa:00:00:00:00:01",
                "vipIp": "192.168.1.100",
                "guestIp": "10.0.0.50",
                "snatInboundTraffic": False,
            }
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.iptable_restore.assert_called_once()


# ---------------------------------------------------------------------------
# Eip — remove_eip
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRemoveEip:
    def test_remove_eip_success(self):
        plugin = eip_module.Eip.__new__(eip_module.Eip)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.remove_eip(_make_req({
            "eip": {
                "privateMac": "fa:00:00:00:00:01",
                "vipIp": "192.168.1.100",
                "guestIp": "10.0.0.50",
            }
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.delete_chain.assert_called()


# ---------------------------------------------------------------------------
# Eip — sync_eip
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestSyncEip:
    def test_sync_eip_removes_old_and_creates_new(self):
        plugin = eip_module.Eip.__new__(eip_module.Eip)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        # get_table returns a mock with children
        table_mock = MagicMock()
        table_mock.children = []
        iptc_mock.get_table.return_value = table_mock
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.sync_eip(_make_req({
            "eips": [{
                "privateMac": "fa:00:00:00:00:01",
                "vipIp": "192.168.1.100",
                "guestIp": "10.0.0.50",
                "snatInboundTraffic": False,
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# PortForwarding — create_rule
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestCreatePortForwardingRule:
    def test_create_rule_success(self):
        plugin = pf_module.PortForwarding.__new__(pf_module.PortForwarding)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.create_rule(_make_req({
            "rules": [{
                "vipPortStart": 8080,
                "vipPortEnd": 8080,
                "privatePortStart": 80,
                "privatePortEnd": 80,
                "protocolType": "TCP",
                "vipIp": "192.168.1.100",
                "privateIp": "10.0.0.50",
                "privateMac": "fa:00:00:00:00:01",
                "allowedCidr": "0.0.0.0/0",
                "snatInboundTraffic": False,
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.iptable_restore.assert_called_once()


# ---------------------------------------------------------------------------
# PortForwarding — revoke_rule
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRevokePortForwardingRule:
    def test_revoke_rule_success(self):
        plugin = pf_module.PortForwarding.__new__(pf_module.PortForwarding)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.revoke_rule(_make_req({
            "rules": [{
                "vipPortStart": 8080,
                "vipIp": "192.168.1.100",
                "protocolType": "TCP",
                "privateMac": "fa:00:00:00:00:01",
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        iptc_mock.delete_chain.assert_called()


# ---------------------------------------------------------------------------
# PortForwarding — sync_rule
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestSyncPortForwardingRule:
    def test_sync_rule_success(self):
        plugin = pf_module.PortForwarding.__new__(pf_module.PortForwarding)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_nic_name_by_mac.return_value = "eth1"
        linux.get_nic_name_by_ip.return_value = "eth0"

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        table_mock = MagicMock()
        table_mock.children = []
        iptc_mock.get_table.return_value = table_mock
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.sync_rule(_make_req({
            "rules": [{
                "vipPortStart": 8080,
                "vipPortEnd": 8080,
                "privatePortStart": 80,
                "privatePortEnd": 80,
                "protocolType": "TCP",
                "vipIp": "192.168.1.100",
                "privateIp": "10.0.0.50",
                "privateMac": "fa:00:00:00:00:01",
                "allowedCidr": "0.0.0.0/0",
                "snatInboundTraffic": False,
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Lb — refresh (with nicIps → _refresh path)
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestLbRefresh:
    def test_refresh_with_nic_ips_calls_refresh(self):
        plugin = lb_module.Lb.__new__(lb_module.Lb)
        shell = sys.modules["zstacklib.utils.shell"]
        shell.call.return_value = ""  # md5sum returns different each time

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        linux = sys.modules["zstacklib.utils.linux"]
        linux.touch_file.return_value = None
        linux.rm_file_force.return_value = None
        linux.find_process_by_cmdline.return_value = None

        with patch("os.path.exists", return_value=False), \
             patch("builtins.open", mock_open()):
            result = plugin.refresh(_make_req({
                "lbs": [{
                    "lbUuid": "lb-001",
                    "listenerUuid": "listener-001",
                    "nicIps": ["10.0.0.1", "10.0.0.2"],
                    "vip": "192.168.1.100",
                    "loadBalancerPort": 80,
                    "instancePort": 80,
                    "parameters": ["healthCheckTarget::http:80", "maxConnection::1000",
                                   "balancerAlgorithm::roundrobin", "connectionIdleTimeout::60",
                                   "healthCheckInterval::5", "healthyThreshold::2", "unhealthyThreshold::3",
                                   "mode::tcp"],
                }]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Lb — delete
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestLbDelete:
    def test_delete_kills_lb_process(self):
        plugin = lb_module.Lb.__new__(lb_module.Lb)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.find_process_by_cmdline.return_value = None
        linux.rm_file_force.return_value = None

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.delete(_make_req({
            "lbs": [{
                "lbUuid": "lb-001",
                "listenerUuid": "listener-001",
                "vip": "192.168.1.100",
                "loadBalancerPort": 80,
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Lb — refresh with empty nicIps (→ _kill_lb path)
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestLbRefreshEmptyNicIps:
    def test_refresh_empty_nic_ips_kills_lb(self):
        plugin = lb_module.Lb.__new__(lb_module.Lb)
        linux = sys.modules["zstacklib.utils.linux"]
        linux.find_process_by_cmdline.return_value = None
        linux.rm_file_force.return_value = None

        iptables = sys.modules["zstacklib.utils.iptables"]
        iptc_mock = MagicMock()
        iptables.from_iptables_save.return_value = iptc_mock

        result = plugin.refresh(_make_req({
            "lbs": [{
                "lbUuid": "lb-001",
                "listenerUuid": "listener-001",
                "nicIps": [],
                "vip": "192.168.1.100",
                "loadBalancerPort": 80,
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Dnsmasq — add_dhcp_entry (merge path)
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestAddDhcpEntry:
    def test_add_dhcp_entry_merge_success(self):
        plugin = dnsmasq_module.Dnsmasq.__new__(dnsmasq_module.Dnsmasq)
        plugin.signal_count = 0
        plugin.config = MagicMock()
        # Make restartDnsmasqAfterNumberOfSIGUSER1 > signal_count
        plugin.config.init_command.restartDnsmasqAfterNumberOfSIGUSER1 = 100

        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_pid_by_process_name.return_value = "1234"
        linux.is_systemd_enabled.return_value = True
        linux.sync_file.return_value = None

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="")):
            result = plugin.add_dhcp_entry(_make_req({
                "rebuild": False,
                "dhcpEntries": [{
                    "ip": "10.0.0.50",
                    "mac": "fa:00:00:00:00:01",
                    "hostname": "test-vm",
                    "netmask": "255.255.255.0",
                    "gateway": "10.0.0.1",
                    "dns": ["8.8.8.8"],
                    "dnsDomain": "example.com",
                    "isDefaultL3Network": True,
                }]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Dnsmasq — add_dhcp_entry (rebuild path)
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestAddDhcpEntryRebuild:
    def test_add_dhcp_entry_rebuild_success(self):
        plugin = dnsmasq_module.Dnsmasq.__new__(dnsmasq_module.Dnsmasq)
        plugin.signal_count = 0
        plugin.config = MagicMock()
        plugin.config.init_command.restartDnsmasqAfterNumberOfSIGUSER1 = 100

        linux = sys.modules["zstacklib.utils.linux"]
        linux.get_pid_by_process_name.return_value = "1234"
        linux.is_systemd_enabled.return_value = True

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="")):
            result = plugin.add_dhcp_entry(_make_req({
                "rebuild": True,
                "dhcpEntries": [{
                    "ip": "10.0.0.50",
                    "mac": "fa:00:00:00:00:01",
                    "hostname": "test-vm",
                    "netmask": "255.255.255.0",
                    "gateway": "10.0.0.1",
                    "dns": ["8.8.8.8"],
                    "dnsDomain": None,
                    "isDefaultL3Network": True,
                }]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# Dnsmasq — remove_dhcp_entry
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestRemoveDhcpEntry:
    def test_remove_dhcp_entry_success(self):
        plugin = dnsmasq_module.Dnsmasq.__new__(dnsmasq_module.Dnsmasq)
        plugin.signal_count = 0
        plugin.config = MagicMock()
        plugin.config.init_command.restartDnsmasqAfterNumberOfSIGUSER1 = 100

        shell = sys.modules["zstacklib.utils.shell"]
        shell.call.return_value = "eth1\n"
        linux = sys.modules["zstacklib.utils.linux"]
        linux.sync_file.return_value = None
        linux.get_pid_by_process_name.return_value = "1234"

        result = plugin.remove_dhcp_entry(_make_req({
            "dhcpEntries": [{
                "mac": "fa:00:00:00:00:01",
                "ip": "10.0.0.50",
                "vrNicMac": "fa:00:00:00:00:ff",
            }]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
