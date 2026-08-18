#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone test runner for zrm_checkpoint_create.

zstacklib/kvmagent are Python 2 codebases that cannot be imported directly
in Python 3 due to syntax differences (reload(sys), print statements, octal
literals, etc.). This script mocks out all external dependencies and tests
the checkpoint_create method logic in isolation.
"""
import json
import sys
import types
import unittest


# ============================================================
# Mock infrastructure — fake modules so zrm_plugin can import
# ============================================================

def _make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# --- zstacklib.utils.jsonobject (minimal) ---
jsonobject_mod = _make_module("zstacklib")
utils_mod = _make_module("zstacklib.utils")
jsonobject_mod = _make_module("zstacklib.utils.jsonobject")


class _JsonObj(object):
    """Minimal jsonobject replacement — attribute-style access on dicts."""
    def __init__(self, d=None):
        if d:
            for k, v in d.items():
                setattr(self, k, v)


def _jo_loads(s):
    d = json.loads(s) if isinstance(s, (str, bytes)) else s
    return _JsonObj(d)


def _jo_dumps(obj):
    if isinstance(obj, dict):
        return json.dumps(obj)
    return json.dumps(obj.__dict__ if hasattr(obj, "__dict__") else {})


jsonobject_mod.loads = _jo_loads
jsonobject_mod.dumps = _jo_dumps

# --- zstacklib.utils.http ---
http_mod = _make_module("zstacklib.utils.http")
http_mod.REQUEST_BODY = "body"
http_mod.json_post = None  # will be patched per test

# --- zstacklib.utils.log ---
log_mod = _make_module("zstacklib.utils.log")


class _FakeLogger(object):
    def info(self, *a, **kw): pass
    def warn(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def exception(self, *a, **kw): pass


log_mod.get_logger = lambda *a, **kw: _FakeLogger()

# --- zstacklib.utils.qmp ---
qmp_mod = _make_module("zstacklib.utils.qmp")
qmp_mod.query_block_jobs_by_device = lambda vm_uuid: {}
qmp_mod.block_job_set_speed = lambda vm_uuid, device, speed: None
qmp_mod.execute_qmp_command = lambda *a, **kw: None

# --- zstacklib.utils.qga ---
qga_mod = _make_module("zstacklib.utils.qga")
qga_mod.VmQga = type("VmQga", (), {})

# --- zstacklib.utils (namespace extras sometimes imported) ---
for name in ["plugin", "daemon", "linux", "qemu"]:
    _make_module("zstacklib.utils." + name)

# --- kvmagent package mock ---
kvmagent_pkg = _make_module("kvmagent")
kvmagent_inner = _make_module("kvmagent.kvmagent")


def _replyerror(func):
    """Decorator stub — just returns the function unchanged."""
    return func


class _FakeKvmAgent(object):
    """Minimal KvmAgent base class stub."""
    pass


kvmagent_inner.replyerror = _replyerror
kvmagent_inner.SEND_COMMAND_URL = "SEND_COMMAND_URL"
kvmagent_inner.KvmAgent = _FakeKvmAgent
kvmagent_pkg.replyerror = _replyerror

# --- kvmagent.plugins namespace ---
plugins_mod = _make_module("kvmagent.plugins")

# --- time module (already available, but we'll patch per test) ---
import time as real_time

# ============================================================
# NOW load zrm_plugin directly via importlib (bypass package resolution)
# ============================================================
import importlib.util
import pathlib

_zrm_plugin_path = str(pathlib.Path(__file__).resolve().parents[1] / "plugins" / "zrm_plugin.py")
_spec = importlib.util.spec_from_file_location("kvmagent.plugins.zrm_plugin", _zrm_plugin_path)
zrm_plugin = importlib.util.module_from_spec(_spec)
sys.modules["kvmagent.plugins.zrm_plugin"] = zrm_plugin
_spec.loader.exec_module(zrm_plugin)


# ============================================================
# Test cases
# ============================================================

class TestZrmCheckpointCreate(unittest.TestCase):
    """Tests for zrm_checkpoint_create source-side gate logic."""

    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_json_post = http_mod.json_post
        self._throttle_calls = []
        self._http_post_calls = []

    def tearDown(self):
        http_mod.json_post = self._orig_json_post

    def _make_req(self, body_dict):
        return {http_mod.REQUEST_BODY: json.dumps(body_dict)}

    def _load_rsp(self, rsp_json):
        return json.loads(rsp_json)

    def _mock_throttle(self, response_dict):
        """Replace _replication_throttle with a mock returning given response."""
        def fake_throttle(req):
            self._throttle_calls.append(req)
            return json.dumps(response_dict)
        self.plugin._replication_throttle = fake_throttle

    def _mock_http_post(self, response_dict):
        """Replace http.json_post with a mock returning given response."""
        def fake_post(url, body=None, fail_soon=False):
            self._http_post_calls.append({"url": url, "body": body, "fail_soon": fail_soon})
            return json.dumps(response_dict)
        http_mod.json_post = fake_post

    # ----------------------------------------------------------
    # Test 1: Happy path — mirrors ready, ZR Server succeeds
    # ----------------------------------------------------------
    def test_happy_path_returns_checkpoint_uuid(self):
        self._mock_throttle({"success": True, "allReady": True, "readyCount": 2, "totalJobs": 2})
        self._mock_http_post({"success": True})

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800",
            "waitReadyTimeout": 30,
            "originalSpeed": 1048576
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertTrue(rsp.get("success", True))
        self.assertEqual("cp-xyz", rsp.get("checkpointUuid"))
        # Verify throttle was called twice: speed=0 (Step A) + restore (Step C)
        self.assertEqual(2, len(self._throttle_calls))
        throttle_body_a = json.loads(self._throttle_calls[0][http_mod.REQUEST_BODY])
        self.assertEqual(0, throttle_body_a["speed"])
        self.assertEqual("vm-123", throttle_body_a["vmUuid"])
        throttle_body_c = json.loads(self._throttle_calls[1][http_mod.REQUEST_BODY])
        self.assertEqual(1048576, throttle_body_c["speed"])
        self.assertEqual("vm-123", throttle_body_c["vmUuid"])
        # Verify http.json_post was called to ZR Server
        self.assertEqual(1, len(self._http_post_calls))
        self.assertEqual("http://192.168.1.10:6800/zr/checkpoint/create",
                         self._http_post_calls[0]["url"])
        post_body = json.loads(self._http_post_calls[0]["body"])
        self.assertEqual("sess-abc", post_body["sessionUuid"])
        self.assertEqual("cp-xyz", post_body["checkpointUuid"])

    # ----------------------------------------------------------
    # Test 2: Mirrors not ready — should fail, NOT call ZR Server
    # ----------------------------------------------------------
    def test_mirrors_not_ready_returns_failure(self):
        self._mock_throttle({"success": True, "allReady": False, "readyCount": 1, "totalJobs": 3})
        self._mock_http_post({"success": True})  # should NOT be called

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800"
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertFalse(rsp.get("success"))
        self.assertIn("not ready", rsp.get("error", ""))
        # ZR Server should NOT have been called
        self.assertEqual(0, len(self._http_post_calls))

    # ----------------------------------------------------------
    # Test 3: ZR Server returns failure
    # ----------------------------------------------------------
    def test_zr_server_failure_propagates_error(self):
        self._mock_throttle({"success": True, "allReady": True, "readyCount": 2, "totalJobs": 2})
        self._mock_http_post({"success": False, "error": "snapshot atomic commit failed"})

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800"
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertFalse(rsp.get("success"))
        self.assertIn("snapshot atomic commit failed", rsp.get("error", ""))

    # ----------------------------------------------------------
    # Test 4: Missing required fields
    # ----------------------------------------------------------
    def test_missing_required_fields_returns_error(self):
        req = self._make_req({
            "vmUuid": "vm-123",
            # sessionUuid missing
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800"
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertFalse(rsp.get("success"))
        self.assertIn("required", rsp.get("error", ""))

    # ----------------------------------------------------------
    # Test 5: Throttle convergence error (success=False)
    # ----------------------------------------------------------
    def test_throttle_failure_returns_convergence_error(self):
        self._mock_throttle({"success": False, "error": "QMP connection lost"})
        self._mock_http_post({"success": True})

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800"
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertFalse(rsp.get("success"))
        self.assertIn("convergence failed", rsp.get("error", ""))
        self.assertEqual(0, len(self._http_post_calls))

    # ----------------------------------------------------------
    # Test 6: No mirrors (totalJobs=0) must not create a checkpoint
    # ----------------------------------------------------------
    def test_no_mirrors_rejects_checkpoint(self):
        self._mock_throttle({"success": True, "allReady": True, "readyCount": 0, "totalJobs": 0})
        self._mock_http_post({"success": True})

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800"
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertFalse(rsp.get("success", True))
        self.assertIn("no active ZRM mirror jobs", rsp.get("error", ""))
        self.assertEqual(0, len(self._http_post_calls))

    # ----------------------------------------------------------
    # Test 7: Speed restore failure is visible to caller
    # ----------------------------------------------------------
    def test_speed_restore_failure_returns_error(self):
        call_count = {"throttle": 0}

        def throttle_with_restore_failure(req):
            call_count["throttle"] += 1
            body = json.loads(req[http_mod.REQUEST_BODY])
            if body.get("speed") == 0:
                # First call: quiesce — success
                return json.dumps({"success": True, "allReady": True, "readyCount": 1, "totalJobs": 1})
            else:
                # Second call: restore — raise exception
                raise RuntimeError("VM already stopped")

        self.plugin._replication_throttle = throttle_with_restore_failure
        self._mock_http_post({"success": True})

        req = self._make_req({
            "vmUuid": "vm-123",
            "sessionUuid": "sess-abc",
            "checkpointUuid": "cp-xyz",
            "zrServerUrl": "http://192.168.1.10:6800",
            "originalSpeed": 1048576
        })

        rsp = self._load_rsp(self.plugin.zrm_checkpoint_create(req))

        self.assertTrue(rsp.get("success", True))
        self.assertTrue(rsp.get("degraded"))
        self.assertEqual("cp-xyz", rsp.get("checkpointUuid"))
        self.assertTrue(rsp.get("speedRestoreFailed"))
        self.assertIn("checkpoint cp-xyz created successfully", rsp.get("error"))
        self.assertIn("Checkpoint is usable", rsp.get("error"))
        self.assertIn("retry speed throttle", rsp.get("error"))
        self.assertIn("ACTION REQUIRED", rsp.get("error"))
        self.assertIn("VM already stopped", rsp.get("speedRestoreError"))
        # Throttle should have been called twice (quiesce + restore attempt)
        self.assertEqual(2, call_count["throttle"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
