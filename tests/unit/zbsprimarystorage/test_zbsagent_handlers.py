from __future__ import annotations

import importlib
import functools
import json
import re
import sys
import types
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock


_PKG_ROOT = Path(__file__).resolve().parents[3] / "zbsprimarystorage"
_ZSTACKLIB_ROOT = Path(__file__).resolve().parents[3] / "zstacklib"
sys.path.insert(0, str(_PKG_ROOT))
sys.path.insert(0, str(_ZSTACKLIB_ROOT))
sys.modules.setdefault("simplejson", json)


class _Logger:
    def warn(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


def _install_lightweight_zstacklib_modules():
    log_mod = types.ModuleType("zstacklib.utils.log")
    log_mod.get_logger = lambda *args, **kwargs: _Logger()
    log_mod.get_logfile_path = lambda: "/tmp/zstack.log"

    shell_mod = types.SimpleNamespace(call=MagicMock(return_value=""), run=MagicMock(return_value=0))
    linux_mod = types.SimpleNamespace(
        shellquote=lambda value: value,
        find_free_port_with_locking=lambda *args: (0, None),
        retry=lambda *args, **kwargs: lambda func: func,
    )

    bash_mod = types.ModuleType("zstacklib.utils.bash")
    bash_mod.functools = functools
    bash_mod.re = re
    bash_mod.log = log_mod
    bash_mod.shell = shell_mod
    bash_mod.linux = linux_mod
    bash_mod.in_bash = lambda func: func
    bash_mod.bash_roe = MagicMock(return_value=(0, "{}", ""))

    http_mod = types.ModuleType("zstacklib.utils.http")
    http_mod.REQUEST_BODY = "body"
    http_mod.REQUEST_HEADER = "headers"
    http_mod.HttpServer = MagicMock()

    report_mod = types.ModuleType("zstacklib.utils.report")
    report_mod.http = http_mod

    plugin_mod = types.ModuleType("zstacklib.utils.plugin")
    plugin_mod.TaskManager = type("TaskManager", (), {})
    plugin_mod.TaskDaemon = type("TaskDaemon", (), {})

    daemon_mod = types.ModuleType("zstacklib.utils.daemon")
    daemon_mod.Daemon = type("Daemon", (), {"__init__": lambda self, *args, **kwargs: None})

    version_mod = types.ModuleType("zstacklib.utils.version")
    version_mod.NumericVersion = lambda value: value

    traceable_shell_mod = types.ModuleType("zstacklib.utils.traceable_shell")
    traceable_shell_mod.cancel_job_by_api = MagicMock()

    for name, mod in {
        "zstacklib.utils.log": log_mod,
        "zstacklib.utils.bash": bash_mod,
        "zstacklib.utils.http": http_mod,
        "zstacklib.utils.report": report_mod,
        "zstacklib.utils.plugin": plugin_mod,
        "zstacklib.utils.daemon": daemon_mod,
        "zstacklib.utils.version": version_mod,
        "zstacklib.utils.traceable_shell": traceable_shell_mod,
        "zstacklib.utils.iproute": types.ModuleType("zstacklib.utils.iproute"),
    }.items():
        sys.modules[name] = mod


_install_lightweight_zstacklib_modules()

try:
    module = importlib.import_module("zbsprimarystorage.zbsagent")
except (ImportError, ModuleNotFoundError) as e:
    raise unittest.SkipTest(f"Cannot import zbsprimarystorage: {e}")


def _make_req(body_dict=None):
    http = cast(object, importlib.import_module("zstacklib.utils.http"))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_agent():
    return module.ZbsAgent.__new__(module.ZbsAgent)


def _zbs_success(result):
    return json.dumps({"error": {"code": 0, "message": ""}, "result": result})


class TestZbsPrimaryStorageQueryVolume(unittest.TestCase):
    def test_query_volume_ignores_requested_snapshot_stats(self):
        agent = _make_agent()
        module.zbsutils.parse_cbd_path = MagicMock(return_value=("pool", "lpool", "vol1", None))
        module.zbsutils.query_volume_info = MagicMock(return_value=_zbs_success({
            "info": {"fileInfo": {"length": 1024, "usedSize": 128, "fileType": 0}},
        }))
        module.zbsutils.get_snapshot_info = MagicMock()

        result = agent.query_volume(_make_req({
            "path": "cbd:pool/lpool/vol1",
            "snapshotInstallPaths": ["cbd:pool/lpool/vol1@snap1"],
        }))

        rsp = _load_rsp(result)
        self.assertTrue(rsp["success"])
        self.assertNotIn("snapshots", rsp)
        module.zbsutils.get_snapshot_info.assert_not_called()

    def test_batch_query_volume_ignores_requested_snapshot_stats(self):
        agent = _make_agent()
        module.zbsutils.parse_cbd_path = MagicMock(return_value=("pool", "lpool", "vol1", None))
        module.zbsutils.query_volumes_in_logical_pool = MagicMock(return_value=_zbs_success({
            "fileInfo": [{"fileName": "vol1", "length": 1024, "usedSize": 128}],
        }))
        module.zbsutils.get_snapshot_info = MagicMock()

        result = agent.batch_query_volume(_make_req({
            "installPaths": ["cbd:pool/lpool/vol1"],
            "snapshotInstallPaths": ["cbd:pool/lpool/vol1@snap1"],
        }))

        rsp = _load_rsp(result)
        self.assertTrue(rsp["success"])
        self.assertEqual(rsp["volumes"], {"cbd:pool/lpool/vol1": {"length": 1024, "usedSize": 128}})
        self.assertNotIn("snapshots", rsp)
        module.zbsutils.get_snapshot_info.assert_not_called()

    def test_batch_query_volume_with_snapshot_returns_requested_snapshot_stats(self):
        agent = _make_agent()
        module.zbsutils.parse_cbd_path = MagicMock(side_effect=[
            ("pool", "lpool", "vol1", None),
            ("pool", "lpool", "vol1", "snap1"),
        ])
        module.zbsutils.query_volumes_in_logical_pool = MagicMock(return_value=_zbs_success({
            "fileInfo": [{"fileName": "vol1", "length": 1024, "usedSize": 128}],
        }))
        module.zbsutils.get_snapshot_info = MagicMock(return_value=_zbs_success({
            "fileInfo": {"usedSize": 64},
        }))

        result = agent.batch_query_volume_with_snapshot(_make_req({
            "installPaths": ["cbd:pool/lpool/vol1"],
            "snapshotInstallPaths": ["cbd:pool/lpool/vol1@snap1"],
        }))

        rsp = _load_rsp(result)
        self.assertTrue(rsp["success"])
        self.assertEqual(rsp["volumes"], {"cbd:pool/lpool/vol1": {"length": 1024, "usedSize": 128}})
        self.assertEqual(rsp["snapshots"], {"cbd:pool/lpool/vol1@snap1": {"usedSize": 64}})

    def test_snapshot_size_endpoint_is_not_registered(self):
        self.assertFalse(hasattr(module.ZbsAgent, "GET_VOLUME_SNAPSHOT_SIZE_PATH"))
        self.assertFalse(hasattr(module, "GetVolumeSnapshotSizeRsp"))
        self.assertFalse(hasattr(module.ZbsAgent, "get_volume_snapshot_size"))
