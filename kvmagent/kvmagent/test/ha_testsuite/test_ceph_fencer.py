import os
import mock
import unittest
import helper
from kvmagent.plugins import ha_plugin
from mock import patch
from zstacklib.utils import linux
from zstacklib.utils import jsonobject
from zstacklib.utils import ceph

cache_object = None
cache_content = None

class TestCephFencerManager(unittest.TestCase):
    class FakeFencerCmd(object):
        def __init__(self):
            self.uuid = "fake_uuid"
            self.interval = 1
            self.maxAttempts = 1
            self.storageCheckerTimeout = 1
            self.fail_if_no_path = False
            self.checkIo = False
            self.strategy = "Force"
            self.fencers = []
            self.poolNames = ["fake_pool_name"]
            self.hostUuid = "fake_host_uuid"

    def setUp(self):
        self.fake_cmd = self.FakeFencerCmd()
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = ha_plugin.CephFencer("fencer_name", "pool_name", self.fake_cmd)
        self.fencer.ioctx = self.get_fake_ioctx()

    def tearDown(self):
        self.fencer.stop()

    def get_fake_ioctx(self):
        class FakeCompletion(object):
            def is_complete(self):
                return True

        class FakeIoctx(object):
            def __init__(self):
                self.object = None
                self.content = None
                self.ioError = False

            def close(self):
                pass

            def aio_write_full(self, object, content):
                global cache_object
                global cache_content
                print("aio_write_full: %s, %s" % (object, content))
                if self.ioError:
                    raise Exception("on purpose failure")

                cache_object = object
                cache_content = content
                return FakeCompletion()

        return FakeIoctx()

    def test_do_check(self):
        helper.mock_vm_running_on_ps(["fake_uuid"])

        self.fencer.do_check()

        global cache_object
        global cache_content
        # check heartbeat file created
        self.assertIsNotNone(cache_object)
        self.assertIsNotNone(cache_content)

        self.assertTrue("heartbeat_count" in cache_content)
        self.assertTrue("fake_uuid" in cache_content)

    def test_failed_to_write_heartbeat_file(self):
        self.fencer.ioctx.ioError = False
        # confirm success and prepare hb file
        self.assertTrue(self.fencer.do_check())

        self.fencer.ioctx.ioError = True
        try:
            self.fencer.do_check()
        except Exception as e:
            self.assertEqual(str(e), "on purpose failure")

        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.FAILURE)

        # check heartbeat file created
        self.fencer.ioctx.ioError = False
        self.assertEqual(self.fencer.check(), ha_plugin.FencerResult.SUCCESS)

    def test_register_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['fencer_name'], self.fencer)

    def test_unregister_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.unregister_fencer('fencer_name')
        self.assertEqual(self.fencer_manager.fencers, {})

    def test_get_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.get_fencer('fencer_name'), self.fencer)

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fencer_name')
        self.assertTrue(self.fencer_manager.get_fencer_status('fencer_name'))