import unittest
from kvmagent.plugins import ha_plugin

class DummyFencer(ha_plugin.Fencer):
    def __init__(self, name):
        self.name = name
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_started(self):
        return self.started

    def get_status(self):
        return 'running' if self.started else 'stopped'

    def get_position(self):
        return ha_plugin.FencerPosition.BEFORE

    def get_name(self):
        return self.name

class TestFencerManager(unittest.TestCase):
    def setUp(self):
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = DummyFencer('fencer1')

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

    def test_start_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fencer1')
        self.assertTrue(self.fencer.is_started())

    def test_stop_fencer(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fencer1')
        self.fencer_manager.stop_fencer('fencer1')
        self.assertFalse(self.fencer.is_started())

    def test_get_fencer_status(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.fencer_manager.start_fencer('fencer1')
        self.assertEqual(self.fencer_manager.get_fencer_status('fencer1'), 'running')

    def test_get_fencer_position(self):
        self.assertEqual(self.fencer_manager.get_fencer_position(), ha_plugin.FencerPosition.BEFORE)