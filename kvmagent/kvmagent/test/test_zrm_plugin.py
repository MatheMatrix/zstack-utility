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


if __name__ == '__main__':
    unittest.main()