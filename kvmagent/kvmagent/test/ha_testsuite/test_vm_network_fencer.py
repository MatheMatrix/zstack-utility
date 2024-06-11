import os
import mock
import unittest
import helper
from kvmagent.plugins import ha_plugin
from mock import patch
from zstacklib.utils import shell

fail_on_purpose = False

class TestVmNetworkFencer(unittest.TestCase):
    class FakeFencerCmd(object):
        def __init__(self):
            self.uuid = "global_network_fencer"
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
        self.fencer = ha_plugin.VmNetworkFencer("global_network_fencer", self.fake_cmd)

    def tearDown(self):
        self.fencer.stop()

    def shell_mock_result(self, is_exception=True, logcmd=True):
        if "virsh list" in self.cmd:
            self.return_code = 0
            self.stdout = "fake_uuid"
            self.stderr = None
        elif "virsh domiflist" in self.cmd:
            self.return_code = 0
            self.stdout = "bridge xx:xx:xx:xx br_fakenic.233"
            self.stderr = None
        elif "ps x |" in self.cmd:
            self.return_code = 0
            self.stdout = "fake_pid"
            self.stderr = None
    
        return self.stdout

    @patch.object(shell.ShellCmd, '__call__', shell_mock_result)
    def test_network_card_down(self):
        self.fencer.falut_nic_count['fakenic'] = 2
        # confirm success and prepare hb file
        self.assertFalse(self.fencer.do_check())
        self.assertEqual(self.fencer.check(), None)

        self.fencer.falut_nic_count['fakenic'] = 0
        self.assertTrue(self.fencer.do_check())
        # check heartbeat file created
        self.assertEqual(self.fencer.check(), None)

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['global_network_fencer'], self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer('global_network_fencer')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer('global_network_fencer'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('global_network_fencer')
        self.assertTrue(self.fencer_manager.get_fencer_status('global_network_fencer'))