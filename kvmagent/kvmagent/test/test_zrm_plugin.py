import itertools
import json
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from zstacklib.utils import http
from zstacklib.utils import jsonobject

from kvmagent.plugins import zrm_plugin


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
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {
            "zrm-mirror-volready": {
                "status": "ready",
                "ready": True,
                "offset": 128,
                "len": 256
            }
        }
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
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {
            "zrm-mirror-voltimeo": {
                "status": "running",
                "ready": False,
                "offset": 64,
                "len": 256
            }
        }
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

    def test_wait_initial_concluded_returns_failure_and_dismisses_job(self):
        dismiss_calls = []
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {
            "zrm-mirror-volconcl": {
                "status": "concluded",
                "ready": False,
                "offset": 32,
                "len": 512,
                "error": "Input/output error"
            }
        }

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


class TestZrmPluginReplicationStop(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_block_job_cancel = zrm_plugin.qmp.block_job_cancel

    def tearDown(self):
        zrm_plugin.qmp.block_job_cancel = self._orig_block_job_cancel

    def _make_req(self, body_dict):
        return {http.REQUEST_BODY: json.dumps(body_dict)}

    def _load_rsp(self, rsp_json):
        return json.loads(rsp_json)

    def test_cancel_failure_returns_error_with_failed_job(self):
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {
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
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {
            "zrm-mirror-volfail": {"status": "running"}
        }

        with mock.patch.object(zrm_plugin.qmp, "block_job_cancel",
                               side_effect=RuntimeError("QMP connection lost")), \
             mock.patch.object(self.plugin, "_vm_shutdown_and_isolate",
                               return_value=(True, None)) as isolate:
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))

        self.assertFalse(body["success"])
        self.assertIn("replication_stop failed", body["error"])
        self.assertIn("failed to cancel ZRM mirror jobs", body["error"])
        isolate.assert_not_called()

    def test_stale_jobs_aborts(self):
        stop_rsp = json.dumps({"success": True,
                               "staleJobs": [{"device": "vda", "status": "active"}]})
        with mock.patch.object(self.plugin, "_replication_stop", return_value=stop_rsp):
            body = self._load_rsp(self.plugin.zrm_recovery_prepare(
                self._make_req({"vmUuid": "vm-1", "sessionUuid": "sess-1"})))
        self.assertFalse(body["success"])
        self.assertIn("stale mirror jobs", body["error"])


if __name__ == '__main__':
    unittest.main()
