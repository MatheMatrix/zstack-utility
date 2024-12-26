import mock
from mock import patch
import os
import time
import unittest

import helper
from kvmagent.plugins import ha_plugin
from zstacklib.utils import linux
from zstacklib.utils import jsonobject


class TestSanlockFencerManager(unittest.TestCase):
    class FakeFencerCmd(object):
        def __init__(self):
            self.interval = 5
            self.maxAttempts = 1
            self.storageCheckerTimeout = 1
            self.fail_if_no_path = False
            self.checkIo = False
            self.strategy = "Force"
            self.fencers = []
            self.vgUuid = "eb65fc94660949e99f638c5160ff8ebb"
            self.uuid = 'eb65fc94660949e99f638c5160ff8ebb'
            self.hostUuid = 'fake_host_uuid'

    def setUp(self):
        self.fake_cmd = self.FakeFencerCmd()
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = ha_plugin.SanlockVolumeGroupFencer(self.fake_cmd)

    def tearDown(self):
        self.fencer.stop()

    def test_do_check_without_cache(self):
        ha_plugin.SanlockCache()._lockspaces = None
        ha_plugin.SanlockCache()._client_status = None
        helper.mock_sanlock_status()

        self.assertFalse(self.fencer.run_fencer())

    def test_cache_expired(self):
        ha_plugin.SanlockCache().add(self.fake_cmd)
        # hack the interval variable
        time.sleep(4)
        ha_plugin.SanlockCache().interval = 1

        self.assertRaises(Exception, self.fencer.run_fencer)

    def test_cache_refresh(self):
        ha_plugin.SanlockCache().add(self.fake_cmd)
        ts = ha_plugin.SanlockCache().timestamp
        time.sleep(2)
        new_ts = ha_plugin.SanlockCache().timestamp
        self.assertNotEqual(ts, new_ts)

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(
            self.fencer_manager.fencers['eb65fc94660949e99f638c5160ff8ebb'],
            self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer(
            'eb65fc94660949e99f638c5160ff8ebb')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer(
            'eb65fc94660949e99f638c5160ff8ebb'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer(self.fencer)
        self.assertTrue(self.fencer_manager.get_fencer_status(
            'eb65fc94660949e99f638c5160ff8ebb'))
        self.fencer_manager.stop_fencer(self.fencer.name)

    def test_cache_remove_vg(self):
        ha_plugin.SanlockCache().add(self.fake_cmd)
        ts = ha_plugin.SanlockCache().timestamp
        ha_plugin.SanlockCache().remove('eb65fc94660949e99f638c5160ff8ebb')
        time.sleep(2)
        new_ts = ha_plugin.SanlockCache().timestamp
        self.assertEqual(ts, new_ts)
