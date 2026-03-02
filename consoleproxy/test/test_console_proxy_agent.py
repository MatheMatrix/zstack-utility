# -*- coding: utf-8 -*-
"""
Characterization tests for consoleproxy — written BEFORE refactoring.
These tests lock down the current behavior so the refactoring can't
accidentally break it.

After refactoring:
  ConsoleTokenFile, ConsoleTokenFileController  → plugins.vnc
  VncPlugin (token helpers + availability)       → plugins.vnc
  NginxPlugin                                    → plugins.nginx
  ConsoleProxyAgent                              → console_proxy_agent (wiring only)
"""
import unittest
import sys
import os
import json
import time
from unittest.mock import MagicMock, patch, call

# conftest.py handles all mock setup before this runs


class TestConsoleTokenFile(unittest.TestCase):
    """ConsoleTokenFile: pure value object, no I/O."""

    def setUp(self):
        from consoleproxy.plugins.vnc import ConsoleTokenFile
        self.ConsoleTokenFile = ConsoleTokenFile

    def test_get_absolute_path_combines_dir_and_token(self):
        tf = self.ConsoleTokenFile(token='abc-123', directory='/tmp/tokens')
        self.assertEqual(tf.get_absolute_path(), '/tmp/tokens/abc-123')

    def test_get_absolute_path_uses_default_dir(self):
        tf = self.ConsoleTokenFile(token='my-token')
        self.assertIn('my-token', tf.get_absolute_path())

    def test_token_is_stored(self):
        tf = self.ConsoleTokenFile(token='tok-xyz', directory='/tmp')
        self.assertEqual(tf.token, 'tok-xyz')


class TestTokenNameHelpers(unittest.TestCase):
    """Token name parsing helpers now live on VncPlugin."""

    def setUp(self):
        from consoleproxy.plugins.vnc import VncPlugin
        self.plugin = VncPlugin(db=MagicMock(), token_ctrl=MagicMock())

    def test_get_token_name_prefix_returns_first_two_parts(self):
        cmd = MagicMock()
        cmd.token = 'host_vm_extra_more'
        result = self.plugin._get_token_name_prefix(cmd)
        self.assertEqual(result, 'host_vm')

    def test_get_token_name_prefix_with_two_part_token(self):
        cmd = MagicMock()
        cmd.token = 'aaa_bbb'
        result = self.plugin._get_token_name_prefix(cmd)
        self.assertEqual(result, 'aaa_bbb')

    def test_make_token_file_name_combines_prefix_and_expiry(self):
        before = time.time()
        name = self.plugin._make_token_file_name('pfx', 300)
        after = time.time()
        parts = name.split('_')
        self.assertEqual(parts[0], 'pfx')
        expiry = float(parts[1])
        self.assertGreaterEqual(expiry, before + 300)
        self.assertLessEqual(expiry, after + 300)


class TestSchemaRouting(unittest.TestCase):
    """_check_proxy_availability on the agent routes vnc vs http to correct handlers."""

    def setUp(self):
        from consoleproxy.console_proxy_agent import ConsoleProxyAgent
        self.agent = ConsoleProxyAgent.__new__(ConsoleProxyAgent)

    def test_vnc_schema_routes_to_vnc_handler(self):
        self.agent._check_vnc_proxy_availability = MagicMock(return_value=True)
        self.agent._check_http_proxy_availability = MagicMock(return_value=True)
        result = self.agent._check_proxy_availability({'targetSchema': 'vnc'})
        self.agent._check_vnc_proxy_availability.assert_called_once()
        self.agent._check_http_proxy_availability.assert_not_called()
        self.assertTrue(result)

    def test_http_schema_routes_to_http_handler(self):
        self.agent._check_vnc_proxy_availability = MagicMock(return_value=False)
        self.agent._check_http_proxy_availability = MagicMock(return_value=True)
        result = self.agent._check_proxy_availability({'targetSchema': 'http'})
        self.agent._check_http_proxy_availability.assert_called_once()
        self.agent._check_vnc_proxy_availability.assert_not_called()
        self.assertTrue(result)

    def test_unknown_schema_returns_false(self):
        self.agent._check_vnc_proxy_availability = MagicMock(return_value=True)
        self.agent._check_http_proxy_availability = MagicMock(return_value=True)
        result = self.agent._check_proxy_availability({'targetSchema': 'rdp'})
        self.assertFalse(result)


class TestVncAvailabilityLogic(unittest.TestCase):
    """VncPlugin.check_availability: documented failure conditions."""

    def setUp(self):
        from consoleproxy.plugins.vnc import VncPlugin
        self.plugin = VncPlugin(db=MagicMock(), token_ctrl=MagicMock())

    def test_returns_false_when_no_process_on_port(self):
        self.plugin._get_pid_on_port = MagicMock(return_value=None)
        result = self.plugin.check_availability({
            'proxyPort': 6000, 'targetHostname': 'host', 'targetPort': 5900, 'token': 't'
        })
        self.assertFalse(result)

    def test_returns_false_when_process_is_not_websockify(self):
        self.plugin._get_pid_on_port = MagicMock(return_value=1234)
        mock_open = unittest.mock.mock_open(read_data='nginx\x00something')
        with patch('builtins.open', mock_open):
            result = self.plugin.check_availability({
                'proxyPort': 6000, 'targetHostname': 'host', 'targetPort': 5900, 'token': 't'
            })
        self.assertFalse(result)

    def test_returns_false_when_token_not_in_db(self):
        self.plugin._get_pid_on_port = MagicMock(return_value=1234)
        mock_open = unittest.mock.mock_open(read_data='websockify\x00stuff')
        self.plugin.db.get = MagicMock(return_value=None)
        with patch('builtins.open', mock_open):
            result = self.plugin.check_availability({
                'proxyPort': 6000, 'targetHostname': 'host', 'targetPort': 5900, 'token': 'tok'
            })
        self.assertFalse(result)

    def test_returns_true_when_all_metadata_matches(self):
        self.plugin._get_pid_on_port = MagicMock(return_value=1234)
        mock_open = unittest.mock.mock_open(read_data='websockify\x00stuff')
        info = {'token': 'tok', 'targetPort': 5900, 'targetHostname': 'host'}
        self.plugin.db.get = MagicMock(return_value=json.dumps(info))
        with patch('builtins.open', mock_open):
            result = self.plugin.check_availability({
                'proxyPort': 6000, 'targetHostname': 'host', 'targetPort': 5900, 'token': 'tok'
            })
        self.assertTrue(result)


class TestConsoleTokenFileController(unittest.TestCase):
    """ConsoleTokenFileController timer management."""

    def setUp(self):
        import consoleproxy.plugins.vnc as m
        self._linux = sys.modules['zstacklib.utils.linux']
        self._linux.rm_dir_force = MagicMock()
        self._linux.mkdir = MagicMock()

        with patch('os.path.exists', return_value=True):
            from consoleproxy.plugins.vnc import ConsoleTokenFileController
            self.ctrl = ConsoleTokenFileController(token_dir='/tmp/fake')

    def test_cancel_delete_stops_running_timer(self):
        from consoleproxy.plugins.vnc import ConsoleTokenFile
        tf = ConsoleTokenFile('tok1', '/tmp')
        mock_timer = MagicMock()
        mock_timer.is_alive.return_value = True
        self.ctrl.timers['tok1'] = mock_timer

        self.ctrl.cancel_delete_token_task(tf)
        mock_timer.cancel.assert_called_once()

    def test_cancel_delete_noop_when_no_timer(self):
        from consoleproxy.plugins.vnc import ConsoleTokenFile
        tf = ConsoleTokenFile('nonexistent', '/tmp')
        # Should not raise
        self.ctrl.cancel_delete_token_task(tf)

    def test_submit_creates_timer_for_token(self):
        from consoleproxy.plugins.vnc import ConsoleTokenFile
        tf = ConsoleTokenFile('tok2', '/tmp')
        future_ms = (time.time() + 60) * 1000

        with patch('threading.Timer') as mock_timer_cls:
            mock_t = MagicMock()
            mock_timer_cls.return_value = mock_t
            self.ctrl.submit_delete_token_task(tf, future_ms)
            mock_t.start.assert_called_once()
            self.assertIn('tok2', self.ctrl.timers)


class TestNginxPlugin(unittest.TestCase):
    """NginxPlugin: nginx-based HTTP proxy for BM2 instances."""

    def setUp(self):
        from consoleproxy.plugins.nginx import NginxPlugin
        self.plugin = NginxPlugin(conf_dir='/tmp/nginx-test')

    def test_check_availability_true_when_service_running(self):
        self.plugin._ensure_service_running = MagicMock(return_value=True)
        result = self.plugin.check_availability({})
        self.assertTrue(result)

    def test_check_availability_false_when_service_not_running(self):
        self.plugin._ensure_service_running = MagicMock(return_value=False)
        result = self.plugin.check_availability({})
        self.assertFalse(result)

    def test_establish_writes_conf_and_returns_proxy_port(self):
        cmd = MagicMock()
        cmd.vmUuid = 'vm-001'
        cmd.token = 'tok-abc'
        cmd.targetHostname = '192.168.1.1'
        cmd.targetPort = 8080
        cmd.proxyPort = 9090

        mock_bash = sys.modules['zstacklib.utils.bash']
        mock_bash.bash_roe = MagicMock(return_value=(0, '', ''))

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            result = self.plugin.establish(cmd)

        self.assertEqual(result, 9090)
        mock_file.assert_called_once_with('/tmp/nginx-test/vm-001.conf', 'w')
        written = mock_file().write.call_args[0][0]
        self.assertIn('tok-abc', written)
        self.assertIn('192.168.1.1', written)

    def test_delete_removes_conf_file(self):
        cmd = MagicMock()
        cmd.vmUuid = 'vm-002'

        mock_bash = sys.modules['zstacklib.utils.bash']
        mock_bash.bash_roe = MagicMock(return_value=(0, '', ''))

        with patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            self.plugin.delete(cmd)

        mock_remove.assert_called_once_with('/tmp/nginx-test/vm-002.conf')


if __name__ == '__main__':
    unittest.main()
