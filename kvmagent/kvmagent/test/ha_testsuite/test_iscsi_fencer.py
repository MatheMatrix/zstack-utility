import os
import mock
import unittest
import helper
from kvmagent.plugins import ha_plugin
from mock import patch
from zstacklib.utils import shell
from zstacklib.utils import linux

fail_on_purpose = False

class TestIscsiFencer(unittest.TestCase):
    class FakeFencerCmd(object):
        def __init__(self):
            self.uuid = "fake_uuid"
            self.interval = 1
            self.maxAttempts = 1
            self.storageCheckerTimeout = 1
            self.strategy = "Force"
            self.fencers = []
            self.heartbeat_path = "/tmp/heartbeat-iscsi"
            self.covering_paths = ["/tmp/heartbeat-iscsi"]
            self.hostId = 1024

    def setUp(self):
        self.fake_cmd = self.FakeFencerCmd()
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = ha_plugin.IscsiFencer(self.fake_cmd, self.fake_cmd.heartbeat_path, self.fake_cmd.covering_paths)
        linux.write_file(self.fake_cmd.heartbeat_path, "test_heartbeat", True)

    def tearDown(self):
        self.fencer.stop()

    def shell_failure_mock(self, is_exception=True, logcmd=True):
        global fail_on_purpose

        if fail_on_purpose:
            self.return_code = 1
            self.stdout = None
            self.stderr = "on purpose failure"
        else:
            self.return_code = 0
            self.stdout = None
            self.stderr = None

        return self.stdout

    @patch.object(shell.ShellCmd, '__call__', shell_failure_mock)
    # @patch('zstacklib.utils.bash.bash_roe', return_value=tuple([0, '', '']))
    def test_do_check(self):
        helper.mock_vm_running_on_ps(["fake_uuid"])

        self.fencer.do_check()

    @patch.object(shell.ShellCmd, '__call__', shell_failure_mock)
    def test_failed_to_write_heartbeat_file(self):
        global fail_on_purpose
        fail_on_purpose = False
        # confirm success and prepare hb file
        self.assertTrue(self.fencer.do_check())

        fail_on_purpose = True
        try:
            self.fencer.do_check()
        except Exception as e:
            self.assertEqual(str(e), "on purpose failure")

        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.FAILURE)

        fail_on_purpose = False
        # check heartbeat file created
        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.SUCCESS)

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['fake_uuid'], self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer('fake_uuid')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer('fake_uuid'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fake_uuid')
        self.assertTrue(self.fencer_manager.get_fencer_status('fake_uuid'))