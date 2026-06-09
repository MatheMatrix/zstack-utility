# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock

from zstacklib.utils import http
from kvmagent.plugins import storage_device


def _make_req(body_dict=None):
    return {
        http.REQUEST_BODY: json.dumps(body_dict or {}),
        http.REQUEST_HEADER: {},
    }


def _make_plugin():
    return storage_device.StorageDevicePlugin.__new__(storage_device.StorageDevicePlugin)


@pytest.mark.kvmagent
class TestStorageDeviceIscsiLogin:
    def test_iscsi_login_selects_data_network_portal(self):
        plugin = _make_plugin()
        plugin.clean_iscsi_cache_configuration = MagicMock()
        plugin.get_iqn_login_timeout = MagicMock(return_value=10)
        plugin.trigger_events_for_block = MagicMock()

        discovery = "\n".join([
            "[fd00:5:5:28::7f:42a4]:3260,1 iqn.2018-06.org.19172disk1",
            "[fd66:6:6:6:1:1:1:4c35]:3260,1 iqn.2018-06.org.19172disk1",
        ])

        login_commands = []

        def bash_roe(cmd):
            if "discovery" in cmd:
                return 0, discovery, ""
            if "--login" in cmd:
                login_commands.append(cmd)
                return 0, "", ""
            return 0, "", ""

        def bash_o(cmd):
            if "iscsiadm -m session | grep" in cmd:
                return "[1]"
            if "Host Number:" in cmd:
                return "1"
            return ""

        storage_device.bash.bash_roe = MagicMock(side_effect=bash_roe)
        storage_device.bash.bash_o = MagicMock(side_effect=bash_o)
        storage_device.bash.bash_ro = MagicMock(return_value=(1, ""))
        storage_device.bash.bash_r = MagicMock(return_value=1)
        storage_device.shell.run = MagicMock(return_value=0)
        storage_device.os.path.exists = MagicMock(return_value=False)
        storage_device.os.listdir = MagicMock(return_value=[])
        storage_device.linux.set_fail_if_no_path = MagicMock()

        req = _make_req({
            "iscsiServerIp": "fd00:5:5:28::7f:42a4",
            "iscsiServerPort": "3260",
            "dataNetworkCidr": "fd66:6:6:6::/64",
            "iscsiTargets": [],
        })

        result = plugin.iscsi_login(req)
        rsp = json.loads(result)

        assert rsp["success"] is True
        assert login_commands
        assert "-p '[fd66:6:6:6:1:1:1:4c35]:3260'" in login_commands[0]

    def test_iscsi_login_rediscovers_selected_data_portal_after_cache_cleanup(self):
        plugin = _make_plugin()
        plugin.clean_iscsi_cache_configuration = MagicMock()
        plugin.get_iqn_login_timeout = MagicMock(return_value=10)
        plugin.trigger_events_for_block = MagicMock()

        discovery = "\n".join([
            "[fd00:5:5:28::7f:42a4]:3260,1 iqn.2018-06.org.19172disk1",
            "[fd66:6:6:6:1:1:1:4c35]:3260,1 iqn.2018-06.org.19172disk1",
        ])

        discovery_commands = []
        login_commands = []

        def bash_roe(cmd):
            if "discovery" in cmd:
                discovery_commands.append(cmd)
                return 0, discovery, ""
            if "--login" in cmd:
                login_commands.append(cmd)
                return 0, "", ""
            return 0, "", ""

        def bash_o(cmd):
            if "iscsiadm -m session | grep" in cmd:
                return "[1]"
            if "Host Number:" in cmd:
                return "1"
            return ""

        storage_device.bash.bash_roe = MagicMock(side_effect=bash_roe)
        storage_device.bash.bash_o = MagicMock(side_effect=bash_o)
        storage_device.bash.bash_ro = MagicMock(return_value=(1, ""))
        storage_device.bash.bash_r = MagicMock(return_value=1)
        storage_device.shell.run = MagicMock(return_value=0)
        storage_device.os.path.exists = MagicMock(return_value=False)
        storage_device.os.listdir = MagicMock(return_value=[])
        storage_device.linux.set_fail_if_no_path = MagicMock()

        req = _make_req({
            "iscsiServerIp": "fd00:5:5:28::7f:42a4",
            "iscsiServerPort": "3260",
            "dataNetworkCidr": "fd66:6:6:6::/64",
            "iscsiTargets": ["iqn.2018-06.org.19172disk1"],
        })

        result = plugin.iscsi_login(req)
        rsp = json.loads(result)

        assert rsp["success"] is True
        assert len(discovery_commands) == 2
        assert "--portal '[fd00:5:5:28::7f:42a4]:3260'" in discovery_commands[0]
        assert "--portal '[fd66:6:6:6:1:1:1:4c35]:3260'" in discovery_commands[1]
        assert login_commands
        assert "-p '[fd66:6:6:6:1:1:1:4c35]:3260'" in login_commands[0]
