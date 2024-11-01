import os
import mock
import unittest
import helper
from kvmagent.plugins import ha_plugin
from mock import patch
from zstacklib.utils import linux
from zstacklib.utils import jsonobject

class TestSblkFencerManager(unittest.TestCase):
    class FakeFencerCmd(object):
        def __init__(self):
            self.interval = 1
            self.maxAttempts = 1
            self.storageCheckerTimeout = 1
            self.fail_if_no_path = False
            self.checkIo = False
            self.strategy = "Force"
            self.fencers = []
            self.vgUuid = "fake_vg_uuid"

    def setUp(self):
        self.fake_cmd = self.FakeFencerCmd()
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = ha_plugin.SharedBlockStorageFencer(self.fake_cmd)

        # create heartbeat directory
        linux.mkdir(os.path.dirname(ha_plugin.SHAREBLOCK_VM_HA_PARAMS_PATH))

    def tearDown(self):
        self.fencer.stop()
        linux.rm_file_force(ha_plugin.SHAREBLOCK_VM_HA_PARAMS_PATH)

    def test_do_check(self):
        helper.mock_vm_running_on_ps(["fake_uuid"])

        self.fencer.do_check()

        # check heartbeat file created
        self.assertTrue(os.path.exists(ha_plugin.SHAREBLOCK_VM_HA_PARAMS_PATH))

        # check heartbeat contains the correct uuid
        with open(ha_plugin.SHAREBLOCK_VM_HA_PARAMS_PATH, 'r') as f:
            cmd = f.read().strip()
            self.assertEqual(cmd, jsonobject.dumps(self.fake_cmd))

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
        self.assertTrue(os.path.exists(ha_plugin.SHAREBLOCK_VM_HA_PARAMS_PATH))
        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.SUCCESS)

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['fake_vg_uuid'], self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer('fake_vg_uuid')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer('fake_vg_uuid'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fake_vg_uuid')
        self.assertTrue(self.fencer_manager.get_fencer_status('fake_vg_uuid'))