# -*- coding: utf-8 -*-

import itertools
import io
import json
import sys
import threading
import types
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from zstacklib.utils import http
from zstacklib.utils import jsonobject

from kvmagent.plugins import zrm_plugin


class _ControllableTimer(object):
    created = []

    def __init__(self, delay, function, args=None):
        self.delay = delay
        self.function = function
        self.args = args or []
        self.daemon = False
        self.cancelled = False
        self.__class__.created.append(self)

    @classmethod
    def reset(cls):
        cls.created = []

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.function(*self.args)


class _ControllableStopEvent(object):
    def __init__(self):
        self.stopped = False
        self.waits = []

    def is_set(self):
        return self.stopped

    def isSet(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, delay):
        self.waits.append(delay)
        return self.stopped


class TestZrmPluginWaitInitial(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_time_time = zrm_plugin.time.time
        self._orig_time_sleep = zrm_plugin.time.sleep
        self._orig_execute_qmp_command = zrm_plugin.qmp.execute_qmp_command

    def tearDown(self):
        zrm_plugin.time.time = self._orig_time_time
        zrm_plugin.time.sleep = self._orig_time_sleep
        zrm_plugin.qmp.execute_qmp_command = self._orig_execute_qmp_command

    def _make_req(self, body_dict):
        return {
            http.REQUEST_BODY: json.dumps(body_dict)
        }

    def _load_rsp(self, rsp_json):
        rsp = jsonobject.loads(rsp_json)
        return rsp, json.loads(rsp_json)

    def test_wait_initial_empty_volume_returns_agent_response(self):
        req = self._make_req({
            "vmUuid": "vm-1",
            "volumeUuids": []
        })

        rsp_json = self.plugin._replication_wait_initial(req)

        rsp, rsp_dict = self._load_rsp(rsp_json)
        self.assertFalse(rsp.success)
        self.assertEqual("no volumeUuids specified for initial full sync wait", rsp.error)
        self.assertEqual(False, rsp_dict.get("success"))
        self.assertEqual("no volumeUuids specified for initial full sync wait", rsp_dict.get("error"))

    def test_wait_initial_all_ready_returns_progress_fields(self):
        self.plugin._query_zrm_block_jobs = lambda vm_uuid: ({
            "zrm-mirror-volready": {
                "status": "ready",
                "ready": True,
                "offset": 128,
                "len": 256
            }
        }, None)
        req = self._make_req({
            "vmUuid": "vm-1",
            "volumeUuids": ["volready-uuid"],
            "timeoutSeconds": 1
        })

        rsp_json = self.plugin._replication_wait_initial(req)

        rsp, rsp_dict = self._load_rsp(rsp_json)
        self.assertTrue(rsp.success)
        self.assertEqual(128, rsp.lastSyncDataBytes)
        self.assertEqual(128, rsp.lastSyncBytes)
        self.assertEqual(256, rsp.totalSyncTargetBytes)
        self.assertEqual(1, rsp.readyJobCount)
        self.assertEqual(0, rsp.runningJobCount)
        self.assertEqual(0, rsp.concludedJobCount)
        self.assertEqual(1, rsp.totalJobs)
        self.assertEqual(1, rsp_dict.get("readyJobCount"))

    def test_wait_initial_timeout_returns_failure_response(self):
        self.plugin._query_zrm_block_jobs = lambda vm_uuid: ({
            "zrm-mirror-voltimeo": {
                "status": "running",
                "ready": False,
                "offset": 64,
                "len": 256
            }
        }, None)
        time_points = [100.0, 101.5]

        def fake_time():
            return time_points.pop(0) if time_points else 101.5

        zrm_plugin.time.time = fake_time
        zrm_plugin.time.sleep = lambda seconds: None
        req = self._make_req({
            "vmUuid": "vm-1",
            "volumeUuids": ["voltimeo-uuid"],
            "timeoutSeconds": 1
        })

        rsp_json = self.plugin._replication_wait_initial(req)

        rsp, rsp_dict = self._load_rsp(rsp_json)
        self.assertFalse(rsp.success)
        self.assertIn("initial full sync timeout", rsp.error)
        self.assertEqual(0, rsp.readyJobCount)
        self.assertEqual(1, rsp.runningJobCount)
        self.assertEqual(0, rsp.concludedJobCount)
        self.assertEqual(["zrm-mirror-voltimeo"], list(rsp.not_ready))
        self.assertEqual([], list(rsp.missing))
        self.assertEqual(False, rsp_dict.get("success"))

    def test_wait_initial_query_failure_reports_retry_metrics(self):
        self.plugin._query_zrm_block_jobs = lambda vm_uuid: ({}, "query-block-jobs timeout")
        time_points = [100.0, 100.0, 101.1]

        def fake_time():
            return time_points.pop(0) if time_points else 101.1

        zrm_plugin.time.time = fake_time
        zrm_plugin.time.sleep = lambda seconds: None

        rsp_json = self.plugin._replication_wait_initial(self._make_req({
            "vmUuid": "vm-1",
            "volumeUuids": ["volquery-uuid"],
            "timeoutSeconds": 1
        }))

        rsp, rsp_dict = self._load_rsp(rsp_json)
        self.assertFalse(rsp.success)
        self.assertTrue(rsp.queryBlockJobsFailed)
        self.assertEqual("query-block-jobs timeout", rsp.queryBlockJobsError)
        self.assertEqual(2, rsp.queryRetryCount)
        self.assertAlmostEqual(1.1, rsp.totalQueryFailureDuration)
        self.assertEqual(2, rsp_dict.get("queryRetryCount"))

    def test_wait_initial_concluded_returns_failure_and_dismisses_job(self):
        dismiss_calls = []
        self.plugin._query_zrm_block_jobs = lambda vm_uuid: ({
            "zrm-mirror-volconcl": {
                "status": "concluded",
                "ready": False,
                "offset": 32,
                "len": 512,
                "error": "Input/output error"
            }
        }, None)

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=False, id=None):
            dismiss_calls.append({
                "vmUuid": vm_uuid,
                "command": command,
                "raise_exception": raise_exception,
                "id": id
            })
            return None

        zrm_plugin.qmp.execute_qmp_command = fake_execute_qmp_command
        req = self._make_req({
            "vmUuid": "vm-1",
            "volumeUuids": ["volconcl-uuid"],
            "timeoutSeconds": 5
        })

        rsp_json = self.plugin._replication_wait_initial(req)

        rsp, rsp_dict = self._load_rsp(rsp_json)
        self.assertFalse(rsp.success)
        self.assertIn("mirror job concluded during initial full sync", rsp.error)
        self.assertEqual(1, rsp.concludedJobCount)
        self.assertEqual(0, rsp.readyJobCount)
        self.assertEqual(0, rsp.runningJobCount)
        self.assertEqual(1, len(rsp.concludedJobErrors))
        self.assertEqual("zrm-mirror-volconcl", rsp.concludedJobErrors[0].device)
        self.assertEqual("Input/output error", rsp.concludedJobErrors[0].error)
        self.assertEqual(1, len(dismiss_calls))
        self.assertEqual("block-job-dismiss", dismiss_calls[0]["command"])
        self.assertEqual("zrm-mirror-volconcl", dismiss_calls[0]["id"])
        self.assertEqual(1, rsp_dict.get("concludedJobCount"))


class TestZrmPluginGuestFsfreeze(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)

    def _make_req(self, body_dict):
        return {
            http.REQUEST_BODY: json.dumps(body_dict)
        }

    def _load_rsp(self, rsp_json):
        rsp = jsonobject.loads(rsp_json)
        body = json.loads(rsp_json)
        return rsp, body

    def test_guest_fsfreeze_missing_vm_uuid(self):
        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "action": "freeze",
            "timeoutSeconds": 10
        }))
        rsp, body = self._load_rsp(rsp_json)
        self.assertFalse(rsp.success)
        self.assertEqual("vmUuid required", rsp.error)
        self.assertEqual(False, body.get("success"))

    def test_guest_fsfreeze_linux_freeze_success(self):
        class FakeQga(object):
            vm_uuid = "vm-linux-1"
            os = "centos"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
                "guest-fsfreeze-freeze-list": True,
            }

            def __init__(self):
                self.status_calls = 0

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    self.status_calls += 1
                    return "thawed" if self.status_calls == 1 else "frozen"
                if command == "guest-fsfreeze-freeze":
                    return 2
                raise AssertionError("unexpected command: %s" % command)

        self.plugin._get_vm_qga = lambda vm_uuid: (FakeQga(), None)
        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "vmUuid": "vm-linux-1",
            "action": "freeze",
            "timeoutSeconds": 15
        }))
        rsp, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertEqual("frozen", body.get("fsFreezeStatus"))
        self.assertEqual(2, body.get("filesystemCount"))
        self.assertEqual("linux", body.get("guestOsType"))
        self.assertEqual("qga-fsfreeze", body.get("quiesceProvider"))
        self.assertEqual(2, self.plugin._linux_fsfreeze_counts["vm-linux-1"])

    def test_guest_fsfreeze_linux_freeze_already_frozen_uses_cached_count(self):
        class FakeQga(object):
            vm_uuid = "vm-linux-frozen"
            os = "centos"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            }

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    return "frozen"
                if command == "guest-fsfreeze-freeze-list":
                    raise AssertionError("freeze-list must not be called when already frozen")
                raise AssertionError("unexpected command: %s" % command)

        self.plugin._linux_fsfreeze_counts = {"vm-linux-frozen": 3}
        self.plugin._get_vm_qga = lambda vm_uuid: (FakeQga(), None)

        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "vmUuid": "vm-linux-frozen",
            "action": "freeze",
            "timeoutSeconds": 15
        }))

        _, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertEqual("frozen", body.get("fsFreezeStatus"))
        self.assertEqual(3, body.get("filesystemCount"))

    def test_guest_fsfreeze_linux_thaw_success(self):
        thaw_qga = type("ThawFakeQga", (), {
            "vm_uuid": "vm-linux-2",
            "os": "centos",
            "supported_commands": {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            },
        })()
        status_calls = {"count": 0}

        def fake_call(command, args=None, timeout=3):
            if command == "guest-fsfreeze-status":
                status_calls["count"] += 1
                return "frozen" if status_calls["count"] == 1 else "thawed"
            if command == "guest-fsfreeze-thaw":
                return 2
            raise AssertionError("unexpected command: %s" % command)

        thaw_qga.call_qga_command = fake_call
        self.plugin._linux_fsfreeze_counts = {"vm-linux-2": 2}
        self.plugin._get_vm_qga = lambda vm_uuid: (thaw_qga, None)
        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "vmUuid": "vm-linux-2",
            "action": "thaw",
            "timeoutSeconds": 10
        }))
        _, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertEqual("thawed", body.get("fsFreezeStatus"))
        self.assertNotIn("vm-linux-2", self.plugin._linux_fsfreeze_counts)

    def test_guest_fsfreeze_qga_not_running(self):
        self.plugin._get_vm_qga = lambda vm_uuid: (None, "QEMU Guest Agent not in running state")
        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "vmUuid": "vm-down",
            "action": "freeze",
            "timeoutSeconds": 10
        }))
        _, body = self._load_rsp(rsp_json)
        self.assertFalse(body.get("success"))
        self.assertEqual("error", body.get("fsFreezeStatus"))
        self.assertEqual("QGA_NOT_RUNNING", body.get("errorCode"))


class TestZrmPluginCheckpointCreate(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_json_post = http.json_post
        self.json_post_calls = []

    def tearDown(self):
        http.json_post = self._orig_json_post

    def _make_req(self, body_dict):
        return {
            http.REQUEST_BODY: json.dumps(body_dict)
        }

    def _load_rsp(self, rsp_json):
        rsp = jsonobject.loads(rsp_json)
        body = json.loads(rsp_json)
        return rsp, body

    def _mock_throttle(self, allReady=True, success=True, readyCount=2, totalJobs=2, error=None):
        """Replace _replication_throttle with a fake that returns the given state."""
        def fake_throttle(req):
            rsp = {"success": success, "allReady": allReady,
                   "readyCount": readyCount, "runningCount": 0 if allReady else 1,
                   "totalJobs": totalJobs}
            if error:
                rsp["error"] = error
            return json.dumps(rsp)
        self.plugin._replication_throttle = fake_throttle

    def _mock_json_post(self, response_dict):
        """Replace http.json_post with a fake that records calls and returns response_dict."""
        def fake_post(url, body=None, headers=None, fail_soon=False, **kwargs):
            self.json_post_calls.append({"url": url, "body": body, "fail_soon": fail_soon})
            return json.dumps(response_dict)
        http.json_post = fake_post

    def test_happy_path_returns_checkpoint_uuid(self):
        self._mock_throttle(allReady=True, totalJobs=2, readyCount=2)
        self._mock_json_post({"success": True})

        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "sess-1",
            "checkpointUuid": "cp-uuid-123",
            "zrServerUrl": "http://192.168.1.10:6800",
            "waitReadyTimeout": 10,
            "originalSpeed": 1048576
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertEqual("cp-uuid-123", body.get("checkpointUuid"))
        # Verify ZR Server was called
        self.assertEqual(1, len(self.json_post_calls))
        self.assertEqual("http://192.168.1.10:6800/zr/checkpoint/create", self.json_post_calls[0]["url"])
        self.assertTrue(self.json_post_calls[0]["fail_soon"])
        # Verify body sent to ZR Server
        sent_body = json.loads(self.json_post_calls[0]["body"])
        self.assertEqual("sess-1", sent_body["sessionUuid"])
        self.assertEqual("cp-uuid-123", sent_body["checkpointUuid"])

    def test_mirrors_not_ready_returns_failure_and_skips_zr_call(self):
        self._mock_throttle(allReady=False, readyCount=1, totalJobs=3)
        self._mock_json_post({"success": True})  # should not be called

        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "sess-1",
            "checkpointUuid": "cp-uuid-456",
            "zrServerUrl": "http://192.168.1.10:6800",
            "waitReadyTimeout": 5
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertFalse(body.get("success"))
        self.assertIn("mirrors not ready", body.get("error"))
        self.assertIn("ready=1", body.get("error"))
        self.assertIn("total=3", body.get("error"))
        # http.json_post must NOT have been called
        self.assertEqual(0, len(self.json_post_calls))

    def test_zr_server_failure_returns_error(self):
        self._mock_throttle(allReady=True, totalJobs=1, readyCount=1)
        self._mock_json_post({"success": False, "error": "disk full on target"})

        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "sess-1",
            "checkpointUuid": "cp-uuid-789",
            "zrServerUrl": "http://192.168.1.10:6800"
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertFalse(body.get("success"))
        self.assertIn("disk full on target", body.get("error"))
        self.assertIn("ZR Server", body.get("error"))

    def test_missing_required_fields_returns_error(self):
        # No mock needed — validation fails before throttle/post
        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "",
            "checkpointUuid": "cp-1",
            "zrServerUrl": ""
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertFalse(body.get("success"))
        self.assertIn("required", body.get("error"))

    def test_throttle_failure_returns_error(self):
        self._mock_throttle(success=False, allReady=False, error="QMP connection lost")
        self._mock_json_post({"success": True})

        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "sess-1",
            "checkpointUuid": "cp-1",
            "zrServerUrl": "http://10.0.0.1:6800"
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertFalse(body.get("success"))
        self.assertIn("mirror convergence failed", body.get("error"))
        self.assertIn("QMP connection lost", body.get("error"))
        self.assertEqual(0, len(self.json_post_calls))

    def test_speed_restore_failure_returns_visible_error(self):
        throttle_calls = []

        def fake_throttle(req):
            throttle_calls.append(json.loads(req[http.REQUEST_BODY]))
            if throttle_calls[-1]["speed"] == 0:
                return json.dumps({
                    "success": True,
                    "allReady": True,
                    "readyCount": 1,
                    "runningCount": 0,
                    "totalJobs": 1
                })
            return json.dumps({
                "success": False,
                "error": "failed to set speed for ZRM mirror jobs: zrm-mirror-vol1: QMP connection lost",
                "speedSetFailed": True,
                "speedSetFailures": [{
                    "device": "zrm-mirror-vol1",
                    "error": "QMP connection lost"
                }]
            })

        self.plugin._replication_throttle = fake_throttle
        self._mock_json_post({"success": True})

        rsp_json = self.plugin.zrm_checkpoint_create(self._make_req({
            "vmUuid": "vm-1",
            "sessionUuid": "sess-1",
            "checkpointUuid": "cp-restore-failed",
            "zrServerUrl": "http://10.0.0.1:6800",
            "originalSpeed": 1048576
        }))

        rsp, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertTrue(body.get("degraded"))
        self.assertEqual("cp-restore-failed", body.get("checkpointUuid"))
        self.assertTrue(body.get("speedRestoreFailed"))
        self.assertIn("checkpoint cp-restore-failed created successfully", body.get("error"))
        self.assertIn("Checkpoint is usable", body.get("error"))
        self.assertIn("retry speed throttle", body.get("error"))
        self.assertIn("ACTION REQUIRED", body.get("error"))
        self.assertEqual([{
            "device": "zrm-mirror-vol1",
            "error": "QMP connection lost"
        }], body.get("speedRestoreFailures"))
        self.assertEqual(2, len(throttle_calls))


class TestZrmPluginReplicationThrottle(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_query_block_jobs_by_device = zrm_plugin.qmp.query_block_jobs_by_device
        self._orig_block_job_set_speed = zrm_plugin.qmp.block_job_set_speed

    def tearDown(self):
        zrm_plugin.qmp.query_block_jobs_by_device = self._orig_query_block_jobs_by_device
        zrm_plugin.qmp.block_job_set_speed = self._orig_block_job_set_speed

    def _make_req(self, body_dict):
        return {http.REQUEST_BODY: json.dumps(body_dict)}

    def _load_rsp(self, rsp_json):
        return json.loads(rsp_json)

    def test_set_speed_failure_returns_error_details(self):
        zrm_plugin.qmp.query_block_jobs_by_device = lambda vm_uuid: {
            "zrm-mirror-vol1": {"status": "running"}
        }

        def fake_block_job_set_speed(vm_uuid, device, speed):
            raise RuntimeError("QMP connection lost")

        zrm_plugin.qmp.block_job_set_speed = fake_block_job_set_speed

        body = self._load_rsp(self.plugin._replication_throttle(
            self._make_req({"vmUuid": "vm-1", "speed": 1048576, "waitReadyTimeout": 0})))

        self.assertFalse(body["success"])
        self.assertTrue(body["speedSetFailed"])
        self.assertIn("failed to set speed", body["error"])
        self.assertEqual([{
            "device": "zrm-mirror-vol1",
            "error": "QMP connection lost"
        }], body["speedSetFailures"])
        self.assertEqual(1, body["totalJobs"])

    def test_partial_speed_set_failure_returns_failed_subset(self):
        zrm_plugin.qmp.query_block_jobs_by_device = lambda vm_uuid: {
            "zrm-mirror-vol1": {"status": "running"},
            "zrm-mirror-vol2": {"status": "running"},
            "zrm-mirror-vol3": {"status": "running"}
        }

        def fake_block_job_set_speed(vm_uuid, device, speed):
            if device == "zrm-mirror-vol2":
                raise RuntimeError("vol2 NBD server unreachable")

        zrm_plugin.qmp.block_job_set_speed = fake_block_job_set_speed

        body = self._load_rsp(self.plugin._replication_throttle(
            self._make_req({"vmUuid": "vm-1", "speed": 1048576, "waitReadyTimeout": 0})))

        self.assertFalse(body["success"])
        self.assertTrue(body["speedSetFailed"])
        self.assertIn("zrm-mirror-vol2", body["error"])
        self.assertEqual([{
            "device": "zrm-mirror-vol2",
            "error": "vol2 NBD server unreachable"
        }], body["speedSetFailures"])
        self.assertEqual(3, body["totalJobs"])

    def test_query_failure_returns_error(self):
        def fake_query_block_jobs(vm_uuid):
            raise RuntimeError("query-block-jobs timeout")

        zrm_plugin.qmp.query_block_jobs_by_device = fake_query_block_jobs

        body = self._load_rsp(self.plugin._replication_throttle(
            self._make_req({"vmUuid": "vm-1", "speed": 1048576, "waitReadyTimeout": 0})))

        self.assertFalse(body["success"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertIn("query-block-jobs failed", body["error"])
        self.assertEqual("query-block-jobs timeout", body["queryBlockJobsError"])

    def test_final_query_failure_returns_speed_set_devices(self):
        query_calls = {"count": 0}
        set_speed_calls = []

        def fake_query_block_jobs(vm_uuid):
            query_calls["count"] += 1
            if query_calls["count"] == 1:
                return {
                    "zrm-mirror-vol1": {"status": "running"},
                    "zrm-mirror-vol2": {"status": "running"}
                }
            raise RuntimeError("query-block-jobs lost after set-speed")

        def fake_block_job_set_speed(vm_uuid, device, speed):
            set_speed_calls.append(device)

        zrm_plugin.qmp.query_block_jobs_by_device = fake_query_block_jobs
        zrm_plugin.qmp.block_job_set_speed = fake_block_job_set_speed

        body = self._load_rsp(self.plugin._replication_throttle(
            self._make_req({"vmUuid": "vm-1", "speed": 1048576, "waitReadyTimeout": 0})))

        self.assertFalse(body["success"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertEqual("query-block-jobs lost after set-speed", body["queryBlockJobsError"])
        self.assertEqual(set(["zrm-mirror-vol1", "zrm-mirror-vol2"]), set(body["speedSetDevices"]))
        self.assertEqual(set(set_speed_calls), set(body["speedSetDevices"]))
        self.assertEqual(2, body["totalJobs"])


class TestZrmPluginReplicationStop(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_block_job_cancel = zrm_plugin.qmp.block_job_cancel
        self._orig_query_block_jobs_by_device = zrm_plugin.qmp.query_block_jobs_by_device

    def tearDown(self):
        zrm_plugin.qmp.block_job_cancel = self._orig_block_job_cancel
        zrm_plugin.qmp.query_block_jobs_by_device = self._orig_query_block_jobs_by_device

    def _make_req(self, body_dict):
        return {http.REQUEST_BODY: json.dumps(body_dict)}

    def _load_rsp(self, rsp_json):
        return json.loads(rsp_json)

    def test_cancel_failure_returns_error_with_failed_job(self):
        zrm_plugin.qmp.query_block_jobs_by_device = lambda vm_uuid: {
            "zrm-mirror-volfail": {"status": "running"}
        }

        def fake_block_job_cancel(vm_uuid, device):
            raise RuntimeError("QMP connection lost")

        zrm_plugin.qmp.block_job_cancel = fake_block_job_cancel

        body = self._load_rsp(self.plugin._replication_stop(
            self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("failed to cancel ZRM mirror jobs", body["error"])
        self.assertEqual([{
            "device": "zrm-mirror-volfail",
            "error": "QMP connection lost"
        }], body["cancelFailedJobs"])

    def test_initial_query_failure_returns_error(self):
        def fake_query_block_jobs(vm_uuid):
            raise RuntimeError("query-block-jobs timeout")

        zrm_plugin.qmp.query_block_jobs_by_device = fake_query_block_jobs

        body = self._load_rsp(self.plugin._replication_stop(
            self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("query-block-jobs failed", body["error"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertEqual("query-block-jobs timeout", body["queryBlockJobsError"])

    def test_post_cancel_query_failure_returns_error(self):
        query_calls = {"count": 0}

        def fake_query_block_jobs(vm_uuid):
            query_calls["count"] += 1
            if query_calls["count"] == 1:
                return {"zrm-mirror-volquery": {"status": "running"}}
            raise RuntimeError("query-block-jobs lost after cancel")

        zrm_plugin.qmp.query_block_jobs_by_device = fake_query_block_jobs
        zrm_plugin.qmp.block_job_cancel = lambda vm_uuid, device: None

        body = self._load_rsp(self.plugin._replication_stop(
            self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("query-block-jobs failed after cancel", body["error"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertEqual("query-block-jobs lost after cancel", body["queryBlockJobsError"])
        self.assertEqual(["zrm-mirror-volquery"], body["cancelRequestedDevices"])

    def test_pending_job_is_finalized_then_dismissed(self):
        query_results = iter([
            {"zrm-mirror-volpending": {"status": "running"}},
            {"zrm-mirror-volpending": {"status": "pending", "auto-finalize": False}},
            {"zrm-mirror-volpending": {"status": "concluded"}},
            {},
            {},
        ])
        qmp_commands = []

        zrm_plugin.qmp.query_block_jobs_by_device = lambda vm_uuid: next(query_results)
        zrm_plugin.qmp.block_job_cancel = lambda vm_uuid, device: None

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=True, **kwargs):
            qmp_commands.append((command, kwargs.get("id")))

        with mock.patch.object(zrm_plugin.qmp, "execute_qmp_command",
                               side_effect=fake_execute_qmp_command), \
             mock.patch.object(zrm_plugin.time, "sleep"):
            body = self._load_rsp(self.plugin._replication_stop(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertTrue(body["success"])
        self.assertNotIn("staleJobs", body)
        self.assertEqual([
            ("job-finalize", "zrm-mirror-volpending"),
            ("job-dismiss", "zrm-mirror-volpending"),
            ("query-named-block-nodes", None),
        ], qmp_commands)

    def _assert_settlement_failure_returns_error(self, status, expected_command):
        device = "zrm-mirror-volstale"
        query_results = iter([
            {device: {"status": "running"}},
            {device: {"status": status}},
            {device: {"status": status}},
        ])
        qmp_commands = []

        zrm_plugin.qmp.query_block_jobs_by_device = lambda vm_uuid: next(query_results)
        zrm_plugin.qmp.block_job_cancel = lambda vm_uuid, job_id: None

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=True, **kwargs):
            qmp_commands.append((command, kwargs.get("id")))
            raise RuntimeError("QMP %s failed" % command)

        with mock.patch.object(zrm_plugin.qmp, "execute_qmp_command",
                               side_effect=fake_execute_qmp_command), \
             mock.patch.object(zrm_plugin, "time") as fake_time:
            fake_time.time.side_effect = [0, 0, 11]
            body = self._load_rsp(self.plugin._replication_stop(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("stale ZRM mirror jobs remain after cancel deadline", body["error"])
        self.assertEqual([{"device": device, "status": status}], body["staleJobs"])
        self.assertEqual([(expected_command, device)], qmp_commands)

    def test_finalize_failure_returns_error_with_stale_job(self):
        self._assert_settlement_failure_returns_error("pending", "job-finalize")

    def test_dismiss_failure_returns_error_with_stale_job(self):
        self._assert_settlement_failure_returns_error("concluded", "job-dismiss")


class TestZrmPluginRecoveryPrepare(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)

    def _make_req(self, body_dict):
        return {http.REQUEST_BODY: json.dumps(body_dict)}

    def _load_rsp(self, rsp_json):
        return json.loads(rsp_json)

    def _fake_domain(self, states):
        domain = mock.MagicMock()
        domain.state.side_effect = states
        domain.XMLDesc.return_value = (
            "<domain><devices>"
            "<interface type='bridge'><alias name='net0'/></interface>"
            "<interface type='bridge'><alias name='net1'/></interface>"
            "</devices></domain>"
        )
        return domain

    def _fake_vm(self, domain):
        vm = mock.MagicMock()
        vm.domain = domain
        return vm

    def test_happy_path_clean_shutdown(self):
        import libvirt as _libvirt
        domain = self._fake_domain([
            (_libvirt.VIR_DOMAIN_RUNNING, 0),
            (_libvirt.VIR_DOMAIN_SHUTOFF, 0),
        ])
        stop_rsp = json.dumps({"success": True})
        with mock.patch("kvmagent.plugins.vm_plugin.get_vm_by_uuid",
                        return_value=self._fake_vm(domain)), \
             mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))
        self.assertTrue(body["success"])
        domain.shutdown.assert_called_once()

    def test_shutdown_timeout_falls_back_to_nic_detach(self):
        import libvirt as _libvirt
        running = (_libvirt.VIR_DOMAIN_RUNNING, 0)
        # Two state() calls: pre-shutdown check + one in-loop poll before deadline fires.
        domain = self._fake_domain([running, running])
        stop_rsp = json.dumps({"success": True})
        # time.time: first two calls return 0.0 (deadline setup + first loop check),
        # all subsequent calls return 100.0 so the deadline fires regardless of how
        # many times the implementation calls time.time() inside the loop.
        with mock.patch("kvmagent.plugins.vm_plugin.get_vm_by_uuid",
                        return_value=self._fake_vm(domain)), \
             mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp), \
             mock.patch("time.sleep"), \
             mock.patch("time.time", side_effect=itertools.chain([0.0, 0.0], itertools.repeat(100.0))):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1",
                                "shutdownTimeout": 2})))
        self.assertTrue(body["success"])
        self.assertEqual(2, domain.detachDeviceFlags.call_count)

    def test_state_error_does_not_report_success(self):
        domain = self._fake_domain([RuntimeError("libvirt connection lost")])
        stop_rsp = json.dumps({"success": True})
        with mock.patch("kvmagent.plugins.vm_plugin.get_vm_by_uuid",
                        return_value=self._fake_vm(domain)), \
             mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))
        self.assertFalse(body["success"])
        self.assertIn("vm state check failed", body["error"])
        self.assertEqual(0, domain.shutdown.call_count)

    def test_partial_nic_detach_failure_aborts(self):
        domain = self._fake_domain([])
        domain.detachDeviceFlags.side_effect = [None, RuntimeError("detach net1 failed")]
        stop_rsp = json.dumps({"success": True})
        with mock.patch("kvmagent.plugins.vm_plugin.get_vm_by_uuid",
                        return_value=self._fake_vm(domain)), \
             mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1",
                                "forceIsolate": True})))
        self.assertFalse(body["success"])
        self.assertIn("network isolation failed", body["error"])
        self.assertIn("vNIC(s) remain", body["error"])

    def test_vm_not_found_treated_as_stopped(self):
        stop_rsp = json.dumps({"success": True})
        with mock.patch("kvmagent.plugins.vm_plugin.get_vm_by_uuid", return_value=None), \
             mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-gone", "sessionUuid": "sess-1"})))
        self.assertTrue(body["success"])

    def test_replication_stop_failure_aborts(self):
        stop_rsp = json.dumps({"success": False, "error": "QMP timeout"})
        with mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))
        self.assertFalse(body["success"])
        self.assertIn("replication_stop failed", body["error"])

    def test_cancel_failure_aborts_before_isolation(self):
        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               return_value={"zrm-mirror-volfail": {"status": "running"}}), \
             mock.patch.object(zrm_plugin.qmp, "block_job_cancel",
                               side_effect=RuntimeError("QMP connection lost")), \
             mock.patch.object(self.plugin, "_vm_shutdown_and_isolate",
                               return_value=(True, None)) as isolate:
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("replication_stop failed", body["error"])
        self.assertIn("failed to cancel ZRM mirror jobs", body["error"])
        isolate.assert_not_called()

    def test_initial_query_failure_aborts_before_isolation(self):
        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               side_effect=RuntimeError("query-block-jobs timeout")), \
             mock.patch.object(self.plugin, "_vm_shutdown_and_isolate",
                               return_value=(True, None)) as isolate:
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("replication_stop failed", body["error"])
        self.assertIn("query-block-jobs failed", body["error"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertEqual("query-block-jobs timeout", body["queryBlockJobsError"])
        isolate.assert_not_called()

    def test_post_cancel_query_failure_aborts_before_isolation(self):
        query_calls = {"count": 0}

        def fake_query_block_jobs(vm_uuid):
            query_calls["count"] += 1
            if query_calls["count"] == 1:
                return {"zrm-mirror-volquery": {"status": "running"}}
            raise RuntimeError("query-block-jobs lost after cancel")

        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               side_effect=fake_query_block_jobs), \
             mock.patch.object(zrm_plugin.qmp, "block_job_cancel",
                               return_value=None), \
             mock.patch.object(self.plugin, "_vm_shutdown_and_isolate",
                               return_value=(True, None)) as isolate:
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("replication_stop failed", body["error"])
        self.assertIn("query-block-jobs failed after cancel", body["error"])
        self.assertTrue(body["queryBlockJobsFailed"])
        self.assertEqual("query-block-jobs lost after cancel", body["queryBlockJobsError"])
        self.assertEqual(["zrm-mirror-volquery"], body["cancelRequestedDevices"])
        isolate.assert_not_called()

    def test_stale_jobs_aborts(self):
        stop_rsp = json.dumps({"success": True,
                               "staleJobs": [{"device": "vda", "status": "active"}]})
        with mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))
        self.assertFalse(body["success"])
        self.assertIn("stale mirror jobs", body["error"])


class TestVmPluginBlockGraphFallback(unittest.TestCase):
    def setUp(self):
        from kvmagent.plugins import vm_plugin
        self.vm_plugin = vm_plugin
        self._orig_execute_qmp_command = vm_plugin.qmp.execute_qmp_command
        self._orig_block_graph_capability = dict(vm_plugin._BLOCK_GRAPH_CAPABILITY)
        vm_plugin._BLOCK_GRAPH_CAPABILITY.clear()

    def tearDown(self):
        self.vm_plugin.qmp.execute_qmp_command = self._orig_execute_qmp_command
        self.vm_plugin._BLOCK_GRAPH_CAPABILITY.clear()
        self.vm_plugin._BLOCK_GRAPH_CAPABILITY.update(self._orig_block_graph_capability)

    def test_query_block_match_is_used_when_block_graph_unavailable(self):
        calls = []

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=False, **kwargs):
            calls.append(command)
            if command == "query-block":
                return [{
                    "device": "drive-virtio-disk0",
                    "inserted": {
                        "node-name": "drive-node0",
                        "file": "/var/lib/zstack/volumes/volume-vol-old-qemu.qcow2"
                    }
                }]
            if command == "x-debug-query-block-graph":
                return None
            return None

        self.vm_plugin.qmp.execute_qmp_command = fake_execute_qmp_command

        node_name, device_name = self.vm_plugin.get_mirror_device_for_volume_uuid(
            "vm-qemu-old", "vol-old-qemu")

        self.assertEqual("drive-node0", node_name)
        self.assertEqual("drive-virtio-disk0", device_name)
        self.assertEqual(False, self.vm_plugin._BLOCK_GRAPH_CAPABILITY.get("vm-qemu-old"))
        self.assertEqual(["query-block", "x-debug-query-block-graph"], calls)


class TestZrmPluginReviewFixes(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)

    def _make_req(self, body_dict):
        return {http.REQUEST_BODY: json.dumps(body_dict)}

    def test_nbd_base_url_is_canonical_and_rejects_injection(self):
        self.assertEqual(
            "nbd://example.com:10809",
            self.plugin._normalize_nbd_base_url("nbd://EXAMPLE.com:10809/"))
        self.assertEqual(
            "nbd://[2001:db8::1]:10809",
            self.plugin._normalize_nbd_base_url("nbd://[2001:DB8::1]:10809"))
        self.assertIsNone(self.plugin._normalize_nbd_base_url(
            "nbd://host:10809/vol-a"))
        self.assertIsNone(self.plugin._normalize_nbd_base_url(
            "nbd://host:10809';touch /tmp/pwned;#"))
        self.assertIsNone(self.plugin._normalize_nbd_base_url(
            "nbd://user@host:10809"))

    def test_dirty_bitmap_query_distinguishes_absent_from_failure(self):
        with mock.patch.object(zrm_plugin.qmp, "execute_qmp_command",
                               return_value=[{
                                   "node-name": "node-a",
                                   "dirty-bitmaps": [{"name": "zrm-volume-a"}]
                               }]):
            self.assertTrue(self.plugin._has_dirty_bitmap(
                "vm-a", "node-a", "zrm-volume-a"))
            self.assertFalse(self.plugin._has_dirty_bitmap(
                "vm-a", "node-a", "zrm-volume-b"))

        with mock.patch.object(zrm_plugin.qmp, "execute_qmp_command",
                               side_effect=RuntimeError("QMP disconnected")):
            self.assertIsNone(self.plugin._has_dirty_bitmap(
                "vm-a", "node-a", "zrm-volume-a"))

    def test_mirror_job_identity_changes_with_session_and_target(self):
        volume_uuid = "0123456789abcdef0123456789abcdef"
        job_a = self.plugin._mirror_job_id(
            volume_uuid, "session-a", "nbd://target-a:10809")
        job_b = self.plugin._mirror_job_id(
            volume_uuid, "session-b", "nbd://target-a:10809")
        job_c = self.plugin._mirror_job_id(
            volume_uuid, "session-a", "nbd://target-b:10809")

        self.assertIn(volume_uuid, job_a)
        self.assertNotEqual(job_a, job_b)
        self.assertNotEqual(job_a, job_c)
        self.assertTrue(self.plugin._job_matches_volume(job_a, volume_uuid))
        self.assertTrue(self.plugin._job_matches_session(job_a, "session-a"))
        self.assertFalse(self.plugin._job_matches_session(job_a, "session-b"))

    def test_target_node_uses_complete_job_hash_within_qemu_limit(self):
        volume_uuid = "0123456789abcdef0123456789abcdef"
        job_a = self.plugin._mirror_job_id(
            volume_uuid, "session-a", "nbd://target-a:10809")
        job_b = self.plugin._mirror_job_id(
            volume_uuid, "session-b", "nbd://target-a:10809")

        node_a = self.plugin._target_node_for_job(job_a)
        self.assertEqual(31, len(node_a))
        self.assertTrue(node_a.startswith("zrm-tgt-"))
        self.assertEqual(node_a, self.plugin._target_node_for_job(job_a))
        self.assertNotEqual(node_a, self.plugin._target_node_for_job(job_b))

    def test_start_registers_endpoints_before_background_target_recovery(self):
        events = []
        registered_handlers = {}

        class FakeHttpServer(object):
            def register_async_uri(self, path, handler):
                events.append("register:" + path)
                registered_handlers[path] = handler

        class DeferredThread(object):
            def __init__(self, target, name=None):
                self.target = target
                self.name = name
                self.daemon = False

            def start(self):
                events.append("thread-start:" + self.name)

        self.plugin._recover_fsfreeze_leases = lambda: events.append(
            "recover-fsfreeze")
        self.plugin.zrm_replication_guest_fsfreeze = lambda req: json.dumps({
            "success": True, "handler": "guest-fsfreeze"})
        self.plugin.zrm_replication_pause = lambda req: json.dumps({
            "success": True, "handler": "pause"})
        self.plugin.zrm_replication_start = lambda req: json.dumps({
            "success": True, "handler": "start"})

        with mock.patch.object(
                zrm_plugin.kvmagent, "get_http_server",
                return_value=FakeHttpServer()), \
             mock.patch.object(
                 zrm_plugin.threading, "Thread", DeferredThread):
            self.plugin.start()

        self.assertEqual("recover-fsfreeze", events[0])
        self.assertTrue(events[1].startswith("register:"))
        self.assertTrue(events[-1].startswith("thread-start:"))
        self.assertEqual(11, len(registered_handlers))
        self.assertEqual(set((
            self.plugin.PATH_REPLICATION_START,
            self.plugin.PATH_REPLICATION_STOP,
            self.plugin.PATH_RECOVERY_PREPARE,
        )), set(self.plugin._TARGET_RECOVERY_GUARDED_PATHS))

        guest_rsp = json.loads(registered_handlers[
            self.plugin.PATH_REPLICATION_GUEST_FSFREEZE](self._make_req({
                "vmUuid": "vm-pending", "action": "thaw"})))
        pause_rsp = json.loads(registered_handlers[
            self.plugin.PATH_REPLICATION_PAUSE](self._make_req({
                "vmUuid": "vm-pending"})))
        start_rsp = json.loads(registered_handlers[
            self.plugin.PATH_REPLICATION_START](self._make_req({
                "vmUuid": "vm-pending"})))
        self.assertEqual("guest-fsfreeze", guest_rsp["handler"])
        self.assertEqual("pause", pause_rsp["handler"])
        self.assertFalse(start_rsp["success"])
        self.assertEqual(
            "ZRM_RUNTIME_RECOVERY_IN_PROGRESS", start_rsp["errorCode"])

    def test_stop_cancels_background_target_recovery(self):
        stop_event = _ControllableStopEvent()
        joined = []

        class RunningRecoveryThread(object):
            @staticmethod
            def is_alive():
                return True

            @staticmethod
            def join(timeout):
                joined.append(timeout)

        self.plugin._ensure_runtime_state()
        self.plugin._target_recovery_stop_event = stop_event
        self.plugin._target_recovery_thread = RunningRecoveryThread()

        self.plugin.stop()

        self.assertTrue(stop_event.is_set())
        self.assertEqual(
            [zrm_plugin._TARGET_RECOVERY_STOP_JOIN_SECONDS], joined)

    def test_recovery_guard_blocks_only_unreconciled_vm(self):
        self.plugin._ensure_runtime_state()
        self.plugin._target_recovery_discovery_complete = True
        self.plugin._target_recovery_pending_vms = set(["vm-pending"])
        self.plugin._target_recovery_errors = {
            "vm-pending": "QMP command timed out"}
        handled = []

        def handler(req):
            handled.append(self.plugin._request_vm_uuid(req))
            return json.dumps({"success": True})

        guarded = self.plugin._guard_target_recovery(handler)
        pending_rsp = json.loads(guarded(self._make_req({
            "vmUuid": "vm-pending"})))
        ready_rsp = json.loads(guarded(self._make_req({
            "vmUuid": "vm-ready"})))

        self.assertFalse(pending_rsp["success"])
        self.assertEqual(
            "ZRM_RUNTIME_RECOVERY_IN_PROGRESS",
            pending_rsp["errorCode"])
        self.assertTrue(pending_rsp["retryable"])
        self.assertTrue(ready_rsp["success"])
        self.assertEqual(["vm-ready"], handled)

    def test_background_recovery_retries_bad_vm_without_blocking_good_vm(self):
        attempts = {"vm-bad": 0, "vm-good": 0}
        stop_event = _ControllableStopEvent()
        self.plugin._ensure_runtime_state()
        self.plugin._runtime_stopping = False
        self.plugin._target_recovery_vm_uuids = lambda: [
            "vm-bad", "vm-good"]

        def recover(vm_uuid):
            attempts[vm_uuid] += 1
            if vm_uuid == "vm-bad":
                if attempts[vm_uuid] == 4:
                    stop_event.set()
                raise RuntimeError("monitor timeout")

        self.plugin._recover_mirror_target_nodes_for_vm = recover
        self.plugin._run_mirror_target_recovery(stop_event)

        self.assertTrue(self.plugin._target_recovery_discovery_complete)
        self.assertNotIn(
            "vm-good", self.plugin._target_recovery_pending_vms)
        self.assertIn("vm-bad", self.plugin._target_recovery_pending_vms)
        self.assertEqual(1, attempts["vm-good"])
        self.assertEqual(4, attempts["vm-bad"])
        self.assertEqual([1, 2, 4], stop_event.waits)

    def test_background_recovery_keeps_retrying_vm_discovery(self):
        stop_event = _ControllableStopEvent()
        discovery_attempts = []
        recovered = []
        self.plugin._ensure_runtime_state()

        def discover():
            discovery_attempts.append(len(discovery_attempts) + 1)
            if len(discovery_attempts) <= 3:
                raise RuntimeError("libvirt temporarily unavailable")
            return ["vm-ready"]

        self.plugin._target_recovery_vm_uuids = discover
        self.plugin._recover_mirror_target_nodes_for_vm = recovered.append
        self.plugin._run_mirror_target_recovery(stop_event)

        self.assertEqual([1, 2, 3, 4], discovery_attempts)
        self.assertEqual([1, 2, 4], stop_event.waits)
        self.assertEqual(["vm-ready"], recovered)
        self.assertTrue(self.plugin._target_recovery_discovery_complete)
        self.assertEqual(set(), self.plugin._target_recovery_pending_vms)

    def test_target_recovery_uses_bounded_vm_concurrency(self):
        vm_uuids = ["vm-%s" % index for index in range(8)]
        state_lock = threading.Lock()
        state = {"active": 0, "max_active": 0}
        self.plugin._ensure_runtime_state()
        self.plugin._target_recovery_pending_vms = set(vm_uuids)
        self.plugin._target_recovery_errors = {}

        def recover(unused_vm_uuid):
            with state_lock:
                state["active"] += 1
                state["max_active"] = max(
                    state["max_active"], state["active"])
            threading.Event().wait(0.02)
            with state_lock:
                state["active"] -= 1

        self.plugin._recover_mirror_target_nodes_for_vm = recover
        self.plugin._recover_pending_target_vms(
            vm_uuids, threading.Event())

        self.assertGreater(state["max_active"], 1)
        self.assertLessEqual(
            state["max_active"], zrm_plugin._TARGET_RECOVERY_WORKERS)
        self.assertEqual(set(), self.plugin._target_recovery_pending_vms)

    def test_stale_recovery_generation_cannot_update_new_state(self):
        vm_uuids = ["vm-old-success", "vm-old-error"]
        entered = threading.Event()
        release = threading.Event()
        entered_lock = threading.Lock()
        entered_count = [0]
        old_stop_event = threading.Event()
        self.plugin._ensure_runtime_state()
        with self.plugin._runtime_state_init_lock:
            self.plugin._target_recovery_generation = 1
            self.plugin._target_recovery_stop_event = old_stop_event
            self.plugin._target_recovery_pending_vms = set(vm_uuids)
            self.plugin._target_recovery_errors = {}

        def recover(vm_uuid):
            with entered_lock:
                entered_count[0] += 1
                if entered_count[0] == len(vm_uuids):
                    entered.set()
            if not release.wait(1):
                raise AssertionError("stale recovery worker was not released")
            if vm_uuid == "vm-old-error":
                raise RuntimeError("old generation failure")

        self.plugin._recover_mirror_target_nodes_for_vm = recover
        supervisor = threading.Thread(target=lambda:
            self.plugin._recover_pending_target_vms(
                vm_uuids, old_stop_event, generation=1))
        supervisor.start()
        self.assertTrue(entered.wait(1))

        new_stop_event = threading.Event()
        with self.plugin._runtime_state_init_lock:
            self.plugin._target_recovery_generation = 2
            self.plugin._target_recovery_stop_event = new_stop_event
            self.plugin._target_recovery_pending_vms = set(vm_uuids)
            self.plugin._target_recovery_errors = {"new-generation": "keep"}
        release.set()
        supervisor.join(2)

        self.assertFalse(supervisor.is_alive())
        self.assertEqual(set(vm_uuids), self.plugin._target_recovery_pending_vms)
        self.assertEqual(
            {"new-generation": "keep"}, self.plugin._target_recovery_errors)

    def test_new_generation_waits_for_inflight_old_vm_recovery(self):
        vm_uuid = "vm-generation-serialization"
        old_entered = threading.Event()
        release_old = threading.Event()
        new_entered = threading.Event()
        invocation_lock = threading.Lock()
        invocation_count = [0]
        old_stop_event = threading.Event()
        new_stop_event = threading.Event()
        self.plugin._ensure_runtime_state()
        with self.plugin._runtime_state_init_lock:
            self.plugin._target_recovery_generation = 1
            self.plugin._target_recovery_stop_event = old_stop_event
            self.plugin._target_recovery_pending_vms = set([vm_uuid])

        def recover(unused_vm_uuid):
            with invocation_lock:
                invocation_count[0] += 1
                invocation = invocation_count[0]
            if invocation == 1:
                old_entered.set()
                release_old.wait(1)
            else:
                new_entered.set()

        self.plugin._recover_mirror_target_nodes_for_vm = recover
        old_supervisor = threading.Thread(target=lambda:
            self.plugin._recover_pending_target_vms(
                [vm_uuid], old_stop_event, generation=1))
        old_supervisor.start()
        self.assertTrue(old_entered.wait(1))

        with self.plugin._runtime_state_init_lock:
            self.plugin._target_recovery_generation = 2
            self.plugin._target_recovery_stop_event = new_stop_event
            self.plugin._target_recovery_pending_vms = set([vm_uuid])
        new_supervisor = threading.Thread(target=lambda:
            self.plugin._recover_pending_target_vms(
                [vm_uuid], new_stop_event, generation=2))
        new_supervisor.start()
        self.assertFalse(new_entered.wait(0.05))
        self.assertIn(vm_uuid, self.plugin._target_recovery_pending_vms)

        release_old.set()
        old_supervisor.join(2)
        new_supervisor.join(2)

        self.assertTrue(new_entered.is_set())
        self.assertFalse(old_supervisor.is_alive())
        self.assertFalse(new_supervisor.is_alive())
        self.assertNotIn(vm_uuid, self.plugin._target_recovery_pending_vms)

    def test_mirror_target_map_iteration_is_serialized_with_writers(self):
        iteration_started = threading.Event()
        release_iteration = threading.Event()
        writer_started = threading.Event()
        writer_done = threading.Event()
        cleanup_result = []
        thread_errors = []
        vm_uuid = "vm-map-lock"
        target_node = "zrm-tgt-map-lock"
        self.plugin._ensure_runtime_state()

        class BlockingItemsDict(dict):
            def __init__(self, *args, **kwargs):
                dict.__init__(self, *args, **kwargs)
                self.items_calls = 0

            def items(self):
                self.items_calls += 1
                if self.items_calls != 1:
                    return dict.items(self)
                live_iterator = iter(dict.items(self))

                def blocking_iterator():
                    first = next(live_iterator)
                    iteration_started.set()
                    if not release_iteration.wait(1):
                        raise AssertionError("map iteration was not released")
                    yield first
                    for item in live_iterator:
                        yield item

                return blocking_iterator()

        self.plugin._mirror_target_nodes = BlockingItemsDict({
            (vm_uuid, "job-a"): target_node,
            (vm_uuid, "job-b"): target_node,
        })
        self.plugin._query_zrm_block_jobs = lambda unused_vm_uuid, \
            command_timeout=None: ({}, None)

        writer_node = "zrm-tgt-writer"
        target_lock = self.plugin._get_mirror_target_lock(
            vm_uuid, target_node)
        while self.plugin._get_mirror_target_lock(
                vm_uuid, writer_node) is target_lock:
            writer_node += "x"

        def cleanup():
            try:
                cleanup_result.append(self.plugin._cleanup_mirror_target_node(
                    vm_uuid, "job-a", node_name=target_node,
                    queue_retry=False))
            except Exception as ex:
                thread_errors.append(ex)

        def write_other_node():
            writer_started.set()
            try:
                self.plugin._remember_mirror_target_node(
                    vm_uuid, "writer-job", writer_node)
            except Exception as ex:
                thread_errors.append(ex)
            finally:
                writer_done.set()

        with mock.patch.object(
                zrm_plugin, "execute_qmp_command_raw"), \
             mock.patch.object(
                 zrm_plugin.qmp, "execute_qmp_command", return_value=[]):
            cleanup_thread = threading.Thread(target=cleanup)
            cleanup_thread.start()
            self.assertTrue(iteration_started.wait(1))
            writer_thread = threading.Thread(target=write_other_node)
            writer_thread.start()
            self.assertTrue(writer_started.wait(1))
            writer_was_blocked = not writer_done.wait(0.05)
            release_iteration.set()
            cleanup_thread.join(2)
            writer_thread.join(2)

        self.assertTrue(writer_was_blocked)
        self.assertFalse(cleanup_thread.is_alive())
        self.assertFalse(writer_thread.is_alive())
        self.assertEqual([], thread_errors)
        self.assertEqual([(True, None)], cleanup_result)
        self.assertEqual(
            writer_node,
            self.plugin._mirror_target_nodes[(vm_uuid, "writer-job")])

    def test_target_recovery_qmp_calls_have_deadline(self):
        query_timeouts = []
        execute_timeouts = []
        raw_timeouts = []
        orphan_node = "zrm-tgt-orphan-node"
        node_queries = iter([
            [{"node-name": orphan_node}],
            [],
        ])

        def query_jobs(unused_vm_uuid, command_timeout=None):
            query_timeouts.append(command_timeout)
            return {}, None

        def execute(unused_vm_uuid, command, raise_exception=True, **kwargs):
            self.assertEqual("query-named-block-nodes", command)
            execute_timeouts.append(kwargs.get("command_timeout"))
            return next(node_queries)

        def execute_raw(unused_vm_uuid, command, raise_exception=False,
                        **kwargs):
            self.assertEqual("blockdev-del", json.loads(command)["execute"])
            raw_timeouts.append(kwargs.get("command_timeout"))

        self.plugin._query_zrm_block_jobs = query_jobs
        with mock.patch.object(
                zrm_plugin.qmp, "execute_qmp_command",
                side_effect=execute), \
             mock.patch.object(
                 zrm_plugin, "execute_qmp_command_raw",
                 side_effect=execute_raw):
            self.plugin._recover_mirror_target_nodes_for_vm("vm-timeout")

        self.assertEqual(
            [zrm_plugin._TARGET_RECOVERY_QMP_TIMEOUT_SECONDS] * 2,
            query_timeouts)
        self.assertEqual(
            [zrm_plugin._TARGET_RECOVERY_QMP_TIMEOUT_SECONDS] * 2,
            execute_timeouts)
        self.assertEqual(
            [zrm_plugin._TARGET_RECOVERY_QMP_TIMEOUT_SECONDS],
            raw_timeouts)

    def test_recovery_binds_legacy_target_to_live_job_for_cleanup(self):
        vm_uuid = "vm-legacy"
        job_id = "zrm-mirror-12345678"
        legacy_node = self.plugin._legacy_target_node_for_job(job_id)
        fake_vm_plugin = types.ModuleType("kvmagent.plugins.vm_plugin")
        fake_vm_plugin.get_all_vm_states = lambda: {vm_uuid: "running"}
        job_queries = iter([
            ({job_id: {"status": "running"}}, None),
            ({job_id: {"status": "running"}}, None),
            ({}, None),
            ({}, None),
            ({}, None),
        ])
        node_queries = iter([
            [{"node-name": legacy_node}],
            [],
        ])
        self.plugin._query_zrm_block_jobs = lambda unused_vm_uuid, \
            command_timeout=None: next(job_queries)
        with mock.patch.dict(
                sys.modules,
                {"kvmagent.plugins.vm_plugin": fake_vm_plugin}), \
             mock.patch.object(
                 zrm_plugin.qmp, "execute_qmp_command",
                 side_effect=lambda *args, **kwargs: next(node_queries)):
            self.plugin._recover_mirror_target_nodes()

            self.assertEqual(
                legacy_node,
                self.plugin._mirror_target_nodes[(vm_uuid, job_id)])

            raw_commands = []
            with mock.patch.object(
                    zrm_plugin, "execute_qmp_command_raw",
                    side_effect=lambda unused_vm_uuid, command,
                    raise_exception=False: raw_commands.append(
                        json.loads(command))), \
                 mock.patch.object(zrm_plugin.qmp, "block_job_cancel"):
                body = json.loads(self.plugin._replication_stop(
                    self._make_req({"vmUuid": vm_uuid})))

        self.assertTrue(body["success"])
        self.assertEqual("blockdev-del", raw_commands[0]["execute"])
        self.assertEqual(
            legacy_node,
            raw_commands[0]["arguments"]["node-name"])

    def test_cleanup_discovers_target_when_runtime_map_is_empty(self):
        vm_uuid = "vm-map-miss"
        job_id = self.plugin._mirror_job_id(
            "0123456789abcdef0123456789abcdef",
            "session-a", "nbd://target-a:10809")
        target_node = self.plugin._target_node_for_job(job_id)
        node_queries = iter([
            [{"node-name": target_node}],
            [],
        ])
        raw_commands = []

        self.plugin._query_zrm_block_jobs = lambda unused_vm_uuid: ({}, None)
        with mock.patch.object(
                zrm_plugin.qmp, "execute_qmp_command",
                side_effect=lambda *args, **kwargs: next(node_queries)), \
             mock.patch.object(
                 zrm_plugin, "execute_qmp_command_raw",
                 side_effect=lambda unused_vm_uuid, command,
                 raise_exception=False: raw_commands.append(json.loads(command))):
            cleaned, cleanup_error = self.plugin._cleanup_mirror_target_node(
                vm_uuid, job_id)

        self.assertTrue(cleaned, cleanup_error)
        self.assertEqual("blockdev-del", raw_commands[0]["execute"])
        self.assertEqual(
            target_node,
            raw_commands[0]["arguments"]["node-name"])

    def test_start_replaces_job_owned_by_another_session(self):
        volume_uuid = "0123456789abcdef0123456789abcdef"
        old_job = self.plugin._mirror_job_id(
            volume_uuid, "session-a", "nbd://target-a:10809")
        query_results = iter([
            {old_job: {"status": "running"}},
            {old_job: {"status": "running"}},
            {},
        ])
        cancelled = []
        mirror_calls = []
        self.plugin._query_blocks_for_vm = lambda vm_uuid: [{}]
        self.plugin._find_block_entry_for_volume = lambda blocks, vol_uuid: ("drive-vda", "node-vda")
        self.plugin._build_mirror_candidates = lambda *args: ["drive-vda"]
        self.plugin._has_dirty_bitmap = lambda *args: False
        self.plugin._add_dirty_bitmap = lambda *args: True

        def fake_execute(vm_uuid, command, raise_exception=True, **kwargs):
            if command == "drive-mirror":
                mirror_calls.append(kwargs)

        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               side_effect=lambda vm_uuid: next(query_results)), \
             mock.patch.object(zrm_plugin.qmp, "block_job_cancel",
                               side_effect=lambda vm_uuid, job_id: cancelled.append(job_id)), \
             mock.patch.object(zrm_plugin.qmp, "execute_qmp_command",
                               side_effect=fake_execute), \
             mock.patch.object(zrm_plugin.time, "sleep"):
            error = self.plugin._start_mirrors_for_zr(
                "vm-a", [volume_uuid], "nbd://target-b:10809",
                session_uuid="session-b")

        self.assertIsNone(error)
        self.assertEqual([old_job], cancelled)
        self.assertEqual(1, len(mirror_calls))
        self.assertNotEqual(old_job, mirror_calls[0]["job_id"])
        owner = self.plugin._mirror_job_owners[("vm-a", mirror_calls[0]["job_id"])]
        self.assertEqual("session-b", owner["sessionUuid"])
        self.assertEqual("nbd://target-b:10809", owner["targetNbdUrl"])

    def test_blockdev_mirror_failure_deletes_created_target_node(self):
        raw_commands = []

        def fake_raw(vm_uuid, command, raise_exception=False):
            raw_commands.append(json.loads(command))

        def fake_execute(vm_uuid, command, raise_exception=True, **kwargs):
            if command == "blockdev-mirror":
                raise RuntimeError("mirror failed")
            if command == "query-named-block-nodes":
                return []

        with mock.patch.object(zrm_plugin, "execute_qmp_command_raw", side_effect=fake_raw), \
             mock.patch.object(zrm_plugin.qmp, "execute_qmp_command", side_effect=fake_execute), \
             mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device", return_value={}):
            success, error = self.plugin._try_blockdev_mirror_to_nbd(
                "vm-a", "node-a", "nbd://target-a:10809/vol-a",
                "zrm-mirror-vol-a", "full", None)

        self.assertFalse(success)
        self.assertIn("mirror failed", error)
        self.assertEqual("blockdev-add", raw_commands[1]["execute"])
        self.assertEqual("blockdev-del", raw_commands[-1]["execute"])
        self.assertNotIn(
            ("vm-a", "zrm-mirror-vol-a"), self.plugin._mirror_target_nodes)

    def test_blockdev_cleanup_failure_keeps_ownership_and_retries_bounded(self):
        job_id = "zrm-mirror-vol-a"
        target_node = self.plugin._target_node_for_job(job_id)
        raw_commands = []
        delete_calls = {"count": 0}
        node_queries = {"count": 0}

        def fake_raw(vm_uuid, command, raise_exception=False):
            qmp_command = json.loads(command)
            raw_commands.append(qmp_command)
            if qmp_command["execute"] == "blockdev-del" and raise_exception:
                delete_calls["count"] += 1
                if delete_calls["count"] > 1:
                    raise RuntimeError("node is busy")

        def fake_execute(vm_uuid, command, raise_exception=True, **kwargs):
            if command == "blockdev-mirror":
                raise RuntimeError("mirror failed")
            if command == "query-named-block-nodes":
                node_queries["count"] += 1
                if node_queries["count"] == 1:
                    return []
                return [{"node-name": target_node}]
            raise AssertionError(command)

        _ControllableTimer.reset()
        with mock.patch.object(zrm_plugin.threading, "Timer", _ControllableTimer), \
             mock.patch.object(zrm_plugin, "execute_qmp_command_raw", side_effect=fake_raw), \
             mock.patch.object(zrm_plugin.qmp, "execute_qmp_command", side_effect=fake_execute), \
             mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device", return_value={}):
            success, error = self.plugin._try_blockdev_mirror_to_nbd(
                "vm-a", "node-a", "nbd://target-a:10809/vol-a",
                job_id, "full", None)

            self.assertFalse(success)
            self.assertIn("target node cleanup failed", error)
            self.assertEqual(
                target_node, self.plugin._mirror_target_nodes[("vm-a", job_id)])
            self.assertIn(("vm-a", job_id), self.plugin._mirror_target_cleanup_retries)

            retry_count = 0
            while ("vm-a", job_id) in self.plugin._mirror_target_cleanup_retries:
                retry_timer = self.plugin._mirror_target_cleanup_retries[
                    ("vm-a", job_id)]["timer"]
                retry_timer.fire()
                retry_count += 1

        self.assertEqual(zrm_plugin._MIRROR_TARGET_CLEANUP_RETRIES, retry_count)
        self.assertNotIn(("vm-a", job_id), self.plugin._mirror_target_cleanup_retries)
        self.assertEqual(
            target_node, self.plugin._mirror_target_nodes[("vm-a", job_id)])

    def test_retry_start_keeps_cleanup_queued_until_old_node_is_absent(self):
        vm_uuid = "vm-retry-start"
        job_id = "zrm-mirror-vol-retry"
        target_node = self.plugin._target_node_for_job(job_id)
        raw_commands = []

        def fake_raw(unused_vm_uuid, command, raise_exception=False):
            qmp_command = json.loads(command)
            raw_commands.append(qmp_command)
            if qmp_command["execute"] == "blockdev-del":
                raise RuntimeError("node is busy")

        _ControllableTimer.reset()
        self.plugin._ensure_runtime_state()
        self.plugin._mirror_target_nodes[(vm_uuid, job_id)] = target_node
        with mock.patch.object(
                zrm_plugin.threading, "Timer", _ControllableTimer):
            self.plugin._schedule_mirror_target_cleanup_retry(
                vm_uuid, job_id, target_node)

            with mock.patch.object(
                    zrm_plugin, "execute_qmp_command_raw",
                    side_effect=fake_raw), \
                 mock.patch.object(
                     zrm_plugin.qmp, "query_block_jobs_by_device",
                     return_value={}), \
                 mock.patch.object(
                     zrm_plugin.qmp, "execute_qmp_command",
                     return_value=[{"node-name": target_node}]):
                success, error = self.plugin._try_blockdev_mirror_to_nbd(
                    vm_uuid, "source-node",
                    "nbd://target-a:10809/vol-a",
                    job_id, "full", None)

        self.assertFalse(success)
        self.assertIn("cannot prepare blockdev-mirror target", error)
        self.assertIn(
            (vm_uuid, job_id), self.plugin._mirror_target_cleanup_retries)
        self.assertFalse(any(
            command["execute"] == "blockdev-add"
            for command in raw_commands))

    def test_start_surfaces_fallback_cleanup_error(self):
        self.plugin._query_blocks_for_vm = lambda vm_uuid: [{}]
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {}
        self.plugin._find_block_entry_for_volume = lambda blocks, volume_uuid: (
            "drive-vda", "node-vda")
        self.plugin._build_mirror_candidates = lambda *args: ["drive-vda"]
        self.plugin._has_dirty_bitmap = lambda *args: False
        self.plugin._add_dirty_bitmap = lambda *args: True
        self.plugin._diagnose_block_topology = lambda *args: (None, "test topology")
        self.plugin._try_blockdev_mirror_to_nbd = lambda *args: (
            False, "target node cleanup failed: node is busy")

        with mock.patch.object(
                zrm_plugin.qmp, "execute_qmp_command",
                side_effect=RuntimeError("drive-mirror failed")):
            error = self.plugin._start_mirrors_for_zr(
                "vm-a", ["vol-a"], "nbd://target-a:10809",
                session_uuid="session-a")

        self.assertIn("target node cleanup failed: node is busy", error)

    def test_throttle_fails_when_expected_job_disappears(self):
        device = "zrm-mirror-vol-a"
        query_results = iter([
            {device: {"status": "running"}},
            {},
        ])
        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               side_effect=lambda vm_uuid: next(query_results)), \
             mock.patch.object(zrm_plugin.qmp, "block_job_set_speed"), \
             mock.patch.object(zrm_plugin.time, "time", side_effect=[0, 0]):
            body = json.loads(self.plugin._replication_throttle(self._make_req({
                "vmUuid": "vm-a", "speed": 0, "waitReadyTimeout": 10
            })))

        self.assertFalse(body["success"])
        self.assertFalse(body["allReady"])
        self.assertEqual([device], body["missingJobs"])

    def test_pause_fails_closed_when_job_query_fails(self):
        with mock.patch.object(zrm_plugin.qmp, "query_block_jobs_by_device",
                               side_effect=RuntimeError("QMP disconnected")):
            body = json.loads(self.plugin._replication_pause(self._make_req({
                "vmUuid": "vm-a", "sessionUuid": "session-a"
            })))
        self.assertFalse(body["success"])
        self.assertTrue(body["queryBlockJobsFailed"])

    def test_linux_freeze_lease_auto_thaws(self):
        class FakeQga(object):
            vm_uuid = "vm-freeze"
            os = "linux"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            }

            def __init__(self):
                self.status = "thawed"

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    return self.status
                if command == "guest-fsfreeze-freeze":
                    self.status = "frozen"
                    return 2
                if command == "guest-fsfreeze-thaw":
                    self.status = "thawed"
                    return 2
                raise AssertionError(command)

        qga = FakeQga()
        self.plugin._get_vm_qga = lambda vm_uuid: (qga, None)
        _ControllableTimer.reset()
        with mock.patch.object(zrm_plugin.threading, "Timer", _ControllableTimer):
            body = json.loads(self.plugin._replication_guest_fsfreeze(self._make_req({
                "vmUuid": qga.vm_uuid,
                "action": "freeze",
                "timeoutSeconds": 5,
                "leaseTimeoutSeconds": 30,
            })))
            self.assertTrue(body["success"])
            self.assertEqual("frozen", qga.status)
            watchdog = self.plugin._fsfreeze_watchdogs[qga.vm_uuid]["timer"]
            watchdog.fire()

        self.assertEqual("thawed", qga.status)
        self.assertNotIn(qga.vm_uuid, self.plugin._fsfreeze_watchdogs)

    def test_freeze_lease_is_persisted_before_qga_freeze(self):
        class SimulatedProcessExit(BaseException):
            pass

        events = []

        class FakeQga(object):
            vm_uuid = "vm-freeze-crash"
            os = "linux"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            }

            def __init__(self):
                self.status_calls = 0

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    self.status_calls += 1
                    if self.status_calls == 1:
                        return "thawed"
                    raise SimulatedProcessExit()
                if command == "guest-fsfreeze-freeze":
                    events.append("freeze")
                    return 2
                raise AssertionError(command)

        def fake_persist(vm_uuid, lease_id, deadline):
            events.append("persist")

        _ControllableTimer.reset()
        with mock.patch.object(zrm_plugin.threading, "Timer", _ControllableTimer), \
             mock.patch.object(self.plugin, "_persist_fsfreeze_lease",
                               side_effect=fake_persist):
            with self.assertRaises(SimulatedProcessExit):
                self.plugin._linux_guest_fsfreeze(
                    FakeQga(), "freeze", 5, lease_timeout_seconds=30)

        self.assertEqual(["persist", "freeze"], events)
        self.assertIn("vm-freeze-crash", self.plugin._fsfreeze_watchdogs)

    def test_freeze_is_not_issued_when_lease_persistence_fails(self):
        freeze_calls = []

        class FakeQga(object):
            vm_uuid = "vm-freeze-persist-failure"
            os = "linux"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            }

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    return "thawed"
                if command == "guest-fsfreeze-freeze":
                    freeze_calls.append(command)
                    return 1
                raise AssertionError(command)

        with mock.patch.object(
                self.plugin, "_persist_fsfreeze_lease",
                side_effect=IOError("disk full")):
            body = json.loads(self.plugin._linux_guest_fsfreeze(
                FakeQga(), "freeze", 5, lease_timeout_seconds=30))

        self.assertFalse(body["success"])
        self.assertEqual([], freeze_calls)
        self.assertNotIn(
            "vm-freeze-persist-failure",
            getattr(self.plugin, "_fsfreeze_watchdogs", {}))

    def test_fsfreeze_recovery_does_not_overwrite_concurrent_new_lease(self):
        vm_uuid = "vm-recovery-race"
        old_lease = {
            "vmUuid": vm_uuid,
            "leaseId": "lease-a",
            "deadline": 100,
        }
        new_lease = {
            "vmUuid": vm_uuid,
            "leaseId": "lease-b",
            "deadline": 200,
        }
        disk_lease = {"value": old_lease}
        new_timer = _ControllableTimer(1, lambda: None)

        class InstallNewLeaseLock(object):
            def __enter__(unused_self):
                self.plugin._ensure_runtime_state()
                disk_lease["value"] = new_lease
                self.plugin._fsfreeze_watchdogs[vm_uuid] = {
                    "leaseId": new_lease["leaseId"],
                    "deadline": new_lease["deadline"],
                    "timer": new_timer,
                }
                return unused_self

            def __exit__(unused_self, unused_type, unused_value,
                         unused_traceback):
                return False

        def fake_open(unused_path, unused_mode):
            return io.StringIO(json.dumps(disk_lease["value"]))

        self.plugin._get_fsfreeze_vm_lock = lambda unused_vm_uuid: (
            InstallNewLeaseLock())
        with mock.patch.object(zrm_plugin.os, "name", "posix"), \
             mock.patch.object(zrm_plugin.os.path, "isdir", return_value=True), \
             mock.patch.object(zrm_plugin.os, "listdir",
                               return_value=["lease.json"]), \
             mock.patch.object(zrm_plugin, "open", side_effect=fake_open,
                               create=True), \
             mock.patch.object(
                 self.plugin, "_arm_fsfreeze_watchdog") as arm_watchdog:
            self.plugin._recover_fsfreeze_leases()

        arm_watchdog.assert_not_called()
        self.assertFalse(new_timer.cancelled)
        self.assertEqual(
            new_lease["leaseId"],
            self.plugin._fsfreeze_watchdogs[vm_uuid]["leaseId"])

    def test_stale_fsfreeze_timer_does_not_thaw_or_remove_new_lease(self):
        vm_uuid = "vm-renewed-freeze"
        old_lease_id = "old-lease"
        new_lease_id = "new-lease"
        entered = threading.Event()
        release = threading.Event()
        qga_lookups = []

        class GateLock(object):
            def __enter__(self):
                entered.set()
                release.wait(2)
                return self

            def __exit__(self, unused_type, unused_value, unused_traceback):
                return False

        self.plugin._ensure_runtime_state()
        old_timer = _ControllableTimer(1, lambda: None)
        new_timer = _ControllableTimer(1, lambda: None)
        self.plugin._fsfreeze_watchdogs[vm_uuid] = {
            "leaseId": old_lease_id, "deadline": 1, "timer": old_timer}
        self.plugin._get_fsfreeze_vm_lock = lambda unused_vm_uuid: GateLock()
        self.plugin._get_vm_qga = lambda unused_vm_uuid: (
            qga_lookups.append(unused_vm_uuid), None)

        with mock.patch.object(
                self.plugin, "_remove_fsfreeze_lease_file") as remove_lease:
            callback = threading.Thread(
                target=self.plugin._auto_thaw_linux_guest,
                args=(vm_uuid, old_lease_id))
            callback.start()
            entered.wait(2)
            self.assertTrue(entered.is_set())
            self.plugin._fsfreeze_watchdogs[vm_uuid] = {
                "leaseId": new_lease_id, "deadline": 2, "timer": new_timer}
            release.set()
            callback.join(2)

            self.assertFalse(callback.is_alive())
            self.assertEqual([], qga_lookups)
            self.assertEqual(
                new_lease_id,
                self.plugin._fsfreeze_watchdogs[vm_uuid]["leaseId"])
            self.assertFalse(
                self.plugin._cancel_fsfreeze_watchdog(vm_uuid, old_lease_id))
            remove_lease.assert_not_called()


if __name__ == '__main__':
    unittest.main()
