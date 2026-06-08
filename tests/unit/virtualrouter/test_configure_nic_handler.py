from __future__ import annotations

import importlib
import json
import os
import pytest
import sys
from typing import cast
from unittest.mock import MagicMock, patch


def _setup_lock_passthrough():
    """Make lock.lock / lock.file_lock passthrough decorators."""
    from tests.conftest import passthrough_lock
    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))
    setattr(lock_mod, "lock", passthrough_lock)
    setattr(lock_mod, "file_lock", passthrough_lock)


try:
    _setup_lock_passthrough()
    # configure_nic.py uses dict.has_key() — Py2 only. Use the haskey fixer.
    from tests.conftest import _import_with_haskey_fix

    _src_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "virtualrouter", "virtualrouter", "plugins", "configure_nic.py",
    )
    _src_path = os.path.normpath(_src_path)
    module = _import_with_haskey_fix("virtualrouter.plugins.configure_nic", _src_path)
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import configure_nic: {e}", allow_module_level=True)


def _make_req(body_dict=None):
    http = cast(object, importlib.import_module("zstacklib.utils.http"))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_plugin():
    """Create NicPlugin via __new__ to skip start()."""
    plugin = module.NicPlugin.__new__(module.NicPlugin)
    return plugin


# ---------------------------------------------------------------------------
# configure_nic handler
# ---------------------------------------------------------------------------
@pytest.mark.virtualrouter
class TestConfigureNic:
    def test_configure_nic_success(self):
        """Happy path: matching MACs found, nics configured."""
        plugin = _make_plugin()

        # Mock _get_nics to return a MAC→devname mapping
        mac1 = "fa:16:3e:aa:bb:cc"
        mac2 = "fa:16:3e:dd:ee:ff"
        with patch.object(plugin, "_get_nics", return_value={mac1: "eth1", mac2: "eth2"}):
            with patch.object(plugin, "_configure_nic") as mock_configure:
                result = plugin.configure_nic(_make_req({
                    "nics": [
                        {"mac": mac1, "ip": "10.0.0.1", "netmask": "255.255.255.0"},
                        {"mac": mac2, "ip": "10.0.0.2", "netmask": "255.255.255.0"},
                    ]
                }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert mock_configure.call_count == 2

    def test_configure_nic_mac_not_found(self):
        """MAC not in the VM's NIC list → error."""
        plugin = _make_plugin()

        with patch.object(plugin, "_get_nics", return_value={"fa:16:3e:aa:bb:cc": "eth1"}):
            result = plugin.configure_nic(_make_req({
                "nics": [
                    {"mac": "fa:16:3e:xx:yy:zz", "ip": "10.0.0.1", "netmask": "255.255.255.0"},
                ]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "unable to find nic" in rsp["error"]

    def test_configure_nic_get_nics_raises(self):
        """_get_nics raises VirtualRouterError → error response."""
        plugin = _make_plugin()
        vr_mod = importlib.import_module("virtualrouter.virtualrouter")

        with patch.object(plugin, "_get_nics", side_effect=vr_mod.VirtualRouterError("duplicate mac")):
            result = plugin.configure_nic(_make_req({
                "nics": [{"mac": "fa:16:3e:aa:bb:cc", "ip": "10.0.0.1", "netmask": "255.255.255.0"}]
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "duplicate mac" in rsp["error"]

    def test_get_nics_parses_ip_link_output(self):
        """_get_nics parses `ip link` output into {mac: devname}."""
        plugin = _make_plugin()

        ip_link_output = (
            "1: lo: <LOOPBACK,UP> mtu 65536 qdisc noqueue state UNKNOWN\n"
            "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
            "2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500 qdisc pfifo_fast state UP\n"
            "    link/ether fa:16:3e:aa:bb:cc brd ff:ff:ff:ff:ff:ff\n"
            "3: eth1: <BROADCAST,MULTICAST,UP> mtu 1500 qdisc pfifo_fast state UP\n"
            "    link/ether fa:16:3e:dd:ee:ff brd ff:ff:ff:ff:ff:ff\n"
        )

        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_cmd_instance = MagicMock(return_value=ip_link_output)
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        nics = plugin._get_nics()
        assert nics == {
            "00:00:00:00:00:00": "lo",
            "fa:16:3e:aa:bb:cc": "eth0",
            "fa:16:3e:dd:ee:ff": "eth1",
        }

    def test_get_nics_raises_on_duplicate_mac(self):
        """_get_nics raises VirtualRouterError on duplicate MAC."""
        plugin = _make_plugin()
        vr_mod = importlib.import_module("virtualrouter.virtualrouter")

        ip_link_output = (
            "2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500\n"
            "    link/ether fa:16:3e:aa:bb:cc brd ff:ff:ff:ff:ff:ff\n"
            "3: eth1: <BROADCAST,MULTICAST,UP> mtu 1500\n"
            "    link/ether fa:16:3e:aa:bb:cc brd ff:ff:ff:ff:ff:ff\n"
        )

        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_cmd_instance = MagicMock(return_value=ip_link_output)
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        with pytest.raises(vr_mod.VirtualRouterError, match="same mac address"):
            plugin._get_nics()
