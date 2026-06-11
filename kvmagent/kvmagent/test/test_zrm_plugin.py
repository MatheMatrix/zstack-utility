import json
import unittest

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

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    return "thawed"
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

    def test_guest_fsfreeze_linux_thaw_success(self):
        class FakeQga(object):
            vm_uuid = "vm-linux-2"
            os = "centos"
            supported_commands = {
                "guest-fsfreeze-freeze": True,
                "guest-fsfreeze-thaw": True,
                "guest-fsfreeze-status": True,
            }

            def call_qga_command(self, command, args=None, timeout=3):
                if command == "guest-fsfreeze-status":
                    return "frozen"
                if command == "guest-fsfreeze-thaw":
                    return 2
                if command == "guest-fsfreeze-status":
                    return "thawed"
                raise AssertionError("unexpected command: %s" % command)

        class ThawFakeQga(FakeQga):
            def call_qga_command(self, command, args=None, timeout=3):
                calls = []
                if command == "guest-fsfreeze-status":
                    calls.append("status")
                    return "thawed" if len(calls) > 1 else "frozen"
                if command == "guest-fsfreeze-thaw":
                    return 2
                raise AssertionError("unexpected command: %s" % command)

        thaw_qga = ThawFakeQga()
        status_calls = {"count": 0}

        def fake_call(command, args=None, timeout=3):
            if command == "guest-fsfreeze-status":
                status_calls["count"] += 1
                return "frozen" if status_calls["count"] == 1 else "thawed"
            if command == "guest-fsfreeze-thaw":
                return 2
            raise AssertionError("unexpected command: %s" % command)

        thaw_qga.call_qga_command = fake_call
        self.plugin._get_vm_qga = lambda vm_uuid: (thaw_qga, None)
        rsp_json = self.plugin._replication_guest_fsfreeze(self._make_req({
            "vmUuid": "vm-linux-2",
            "action": "thaw",
            "timeoutSeconds": 10
        }))
        _, body = self._load_rsp(rsp_json)
        self.assertTrue(body.get("success"))
        self.assertEqual("thawed", body.get("fsFreezeStatus"))

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


if __name__ == '__main__':
    unittest.main()