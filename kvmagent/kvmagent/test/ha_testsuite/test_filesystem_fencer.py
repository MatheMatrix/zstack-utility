import os
import mock
import unittest
import helper
from kvmagent.plugins import ha_plugin
from mock import patch
from zstacklib.utils import shell
from zstacklib.utils import linux

class TestFileSystemFencer(unittest.TestCase):
    def setUp(self):
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = ha_plugin.FileSystemFencer(
            "fencer1",
            1,
            1,
            1,
            "Force",
            "fake_uuid",
            helper.unittest_filesystem_mount_point)

        # create heartbeat directory
        linux.mkdir(self.fencer.heartbeat_file_dir)

    def tearDown(self):
        self.fencer.stop()
        linux.rm_file_force(self.fencer.heartbeat_file_path)

    def test_do_check(self):
        helper.mock_vm_running_on_ps(["fake_uuid"])

        self.fencer.do_check()

        # check heartbeat file created
        self.assertTrue(os.path.exists(self.fencer.heartbeat_file_path))

        # check heartbeat contains the correct uuid
        with open(self.fencer.heartbeat_file_path, 'r') as f:
            self.assertTrue("fake_uuid" in f.read())

    def shell_failure_mock(self, is_exception=True, logcmd=True):
        self.return_code = 1
        self.stdout = None
        self.stderr = "on purpose failure"

        return self.stdout

    @patch.object(shell.ShellCmd, '__call__', shell_failure_mock)
    def test_failed_touch_heartbeat_file(self):
        self.assertFalse(self.fencer.do_check())

        # check heartbeat file not created
        self.assertFalse(os.path.exists(self.fencer.heartbeat_file_path))

    def test_failed_to_write_heartbeat_file(self):
        # confirm success and prepare hb file
        self.assertTrue(self.fencer.do_check())

        # mock f.write(json.dumps(content)) failure
        with mock.patch('__builtin__.open', mock.mock_open()) as m:
            m.side_effect = IOError("on purpose failure")

            # expect IOError
            try:
                self.fencer.do_check()
            except IOError as e:
                self.assertEqual(str(e), "on purpose failure")

            # check fencer result Failure
            self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.FAILURE)

        # check heartbeat file created
        self.assertTrue(os.path.exists(self.fencer.heartbeat_file_path))
        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.SUCCESS)

    # TODO: fix this test
    def test_retry_to_recover_storage(self):
        self.fencer.mount_point.mounted_by_zstack = False
        # not mounted by zstack will be skipped
        self.assertFalse(self.fencer.retry_to_recover_storage())

        self.fencer.mount_point.mounted_by_zstack = True
        self.assertTrue(self.fencer.retry_to_recover_storage())

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['fencer1'], self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer('fencer1')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer('fencer1'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fencer1')
        self.assertTrue(self.fencer_manager.get_fencer_status('fencer1'))