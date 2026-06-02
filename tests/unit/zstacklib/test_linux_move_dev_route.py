from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


def _load_linux_module():
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "zstacklib"))
    sys.modules.setdefault("simplejson", json)
    sys.modules.setdefault("netaddr", MagicMock())
    sys.modules.setdefault("xxhash", MagicMock())
    sys.modules.setdefault("zstacklib.utils.thread", MagicMock())
    sys.modules.setdefault("zstacklib.utils.qemu_img", MagicMock())
    sys.modules.setdefault("zstacklib.utils.lock", MagicMock())
    sys.modules.setdefault("zstacklib.utils.xmlobject", MagicMock())
    sys.modules.setdefault("zstacklib.utils.shell", MagicMock())
    sys.modules.setdefault("zstacklib.utils.iproute", MagicMock())
    sys.modules.setdefault("zstacklib.utils.network_ipv6", MagicMock())
    log_module = types.ModuleType("zstacklib.utils.log")
    log_module.get_logger = MagicMock(return_value=MagicMock())
    sys.modules.setdefault("zstacklib.utils.log", log_module)

    linux_path = repo_root / "zstacklib" / "zstacklib" / "utils" / "linux.py"
    spec = importlib.util.spec_from_file_location("linux_move_dev_route_under_test", linux_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_move_dev_route_moves_ipv6_address_and_routes():
    linux = _load_linux_module()
    calls = []

    def shell_call(cmd, exception=True):
        calls.append((cmd, exception))
        if cmd == 'ip addr show dev ens4 | grep "inet "':
            return ""
        if cmd == 'ip addr show dev ens4 | grep "inet6 " | grep -v " scope link"':
            return "    inet6 2026:3:3:1::4b:3364/64 scope global noprefixroute\n"
        if cmd == "ip route show dev ens4 | grep via | sed 's/onlink//g'":
            return ""
        if cmd == "ip -6 route show dev ens4 | grep via | sed 's/onlink//g'":
            return "default via 2026:3:3:1::1 proto static metric 101\n"
        if cmd == "ip -6 route show dev ens4 proto kernel | grep -v '^fe80::' | sed 's/onlink//g'":
            return "2026:3:3:1::/64 proto kernel metric 101 pref medium\n"
        if cmd == 'ip addr show dev br_ens4 | grep "inet6 2026:3:3:1::4b:3364/64"':
            return ""
        return ""

    linux.shell.call = MagicMock(side_effect=shell_call)

    linux.move_dev_route("ens4", "br_ens4")

    assert ("ip -6 route del default via 2026:3:3:1::1 proto static metric 101", True) in calls
    assert ("ip addr del 2026:3:3:1::4b:3364/64 dev ens4", True) in calls
    assert ("ip -6 route del 2026:3:3:1::/64 proto kernel metric 101 pref medium", False) in calls
    assert ("ip addr add 2026:3:3:1::4b:3364/64 dev br_ens4", True) in calls
    assert ("ip -6 route add default via 2026:3:3:1::1 proto static metric 101", True) in calls


def test_move_dev_route_moves_ipv6_direct_static_route():
    linux = _load_linux_module()
    calls = []

    def shell_call(cmd, exception=True):
        calls.append((cmd, exception))
        if cmd == 'ip addr show dev ens4 | grep "inet "':
            return ""
        if cmd == 'ip addr show dev ens4 | grep "inet6 " | grep -v " scope link"':
            return "    inet6 fd00:5:5:28::62:d0e5/128 scope global noprefixroute\n"
        if cmd == "ip route show dev ens4 | grep via | sed 's/onlink//g'":
            return ""
        if cmd == "ip -6 route show dev ens4 | grep via | sed 's/onlink//g'":
            return ""
        if cmd == "ip -6 route show dev ens4 | grep -v via | grep -v ' proto kernel ' | grep -v '^fe80::' | sed 's/onlink//g'":
            return "fd00:5:5:28::/64 proto static metric 101 pref medium\n"
        if cmd == "ip -6 route show dev ens4 proto kernel | grep -v '^fe80::' | sed 's/onlink//g'":
            return "fd00:5:5:28::62:d0e5 proto kernel metric 101 pref medium\n"
        if cmd == 'ip addr show dev br_ens4 | grep "inet6 fd00:5:5:28::62:d0e5/128"':
            return ""
        return ""

    linux.shell.call = MagicMock(side_effect=shell_call)

    linux.move_dev_route("ens4", "br_ens4")

    assert ("ip -6 route del fd00:5:5:28::/64 dev ens4 proto static metric 101 pref medium", True) in calls
    assert ("ip addr del fd00:5:5:28::62:d0e5/128 dev ens4", True) in calls
    assert ("ip addr add fd00:5:5:28::62:d0e5/128 dev br_ens4", True) in calls
    assert ("ip -6 route add fd00:5:5:28::/64 dev br_ens4 proto static metric 101 pref medium", True) in calls
