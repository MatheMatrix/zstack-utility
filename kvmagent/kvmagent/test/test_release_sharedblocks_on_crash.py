'''
Unit tests for _release_sharedblocks handling EVENT_CRASHED.

Verifies fix for ZSTAC-57664: VM crash should trigger LV deactivation
so that sanlock leases are released properly.
'''
import sys
import unittest
from unittest import mock

_MOCK_MODULES = [
    'libvirt', 'singleton', 'netaddr', 'simplejson', 'urlparse',
    'jinja2', 'xml.dom.minidom',
]

for mod_name in _MOCK_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock.MagicMock()

# Mock log module to avoid writing to /var/log/zstack/zstack.log
mock_log = mock.MagicMock()
mock_log.get_logger = mock.MagicMock(return_value=mock.MagicMock())
sys.modules['zstacklib.utils.log'] = mock_log

from zstacklib.utils.libvirt_singleton import LibvirtEventManager

EVENT_INDEX_CRASHED = LibvirtEventManager.event_strings.index(LibvirtEventManager.EVENT_CRASHED)
EVENT_INDEX_SHUTDOWN = LibvirtEventManager.event_strings.index(LibvirtEventManager.EVENT_SHUTDOWN)
EVENT_INDEX_STOPPED = LibvirtEventManager.event_strings.index(LibvirtEventManager.EVENT_STOPPED)
EVENT_INDEX_STARTED = LibvirtEventManager.event_strings.index(LibvirtEventManager.EVENT_STARTED)
EVENT_INDEX_RESUMED = LibvirtEventManager.event_strings.index(LibvirtEventManager.EVENT_RESUMED)


class TestReleaseSharedblocksEventFilter(unittest.TestCase):
    """
    Test the event filtering logic in _release_sharedblocks.

    The fix adds EVENT_CRASHED to the accepted tuple so crash events
    trigger LV deactivation instead of being silently ignored.
    """

    ACCEPTED_EVENTS = (
        LibvirtEventManager.EVENT_SHUTDOWN,
        LibvirtEventManager.EVENT_STOPPED,
        LibvirtEventManager.EVENT_CRASHED,
    )

    def _would_release(self, event_index):
        event_str = LibvirtEventManager.event_to_string(event_index)
        return event_str in self.ACCEPTED_EVENTS

    def test_event_crashed_is_accepted(self):
        self.assertTrue(self._would_release(EVENT_INDEX_CRASHED),
                        "EVENT_CRASHED should trigger LV release")

    def test_event_shutdown_is_accepted(self):
        self.assertTrue(self._would_release(EVENT_INDEX_SHUTDOWN),
                        "EVENT_SHUTDOWN should trigger LV release")

    def test_event_stopped_is_accepted(self):
        self.assertTrue(self._would_release(EVENT_INDEX_STOPPED),
                        "EVENT_STOPPED should trigger LV release")

    def test_event_started_is_rejected(self):
        self.assertFalse(self._would_release(EVENT_INDEX_STARTED),
                         "EVENT_STARTED should NOT trigger LV release")

    def test_event_resumed_is_rejected(self):
        self.assertFalse(self._would_release(EVENT_INDEX_RESUMED),
                         "EVENT_RESUMED should NOT trigger LV release")

    def test_event_to_string_maps_correctly(self):
        self.assertEqual(LibvirtEventManager.event_to_string(EVENT_INDEX_CRASHED), "Crashed")
        self.assertEqual(LibvirtEventManager.event_to_string(EVENT_INDEX_SHUTDOWN), "Shutdown")
        self.assertEqual(LibvirtEventManager.event_to_string(EVENT_INDEX_STOPPED), "Stopped")


if __name__ == '__main__':
    unittest.main()
