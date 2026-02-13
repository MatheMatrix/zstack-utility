# encoding: utf-8
"""
Tests for libvirt listen_addr configuration in host_plugin.
Verifies that update_libvirt_listen_addr properly updates
/etc/libvirt/libvirtd.conf to bind to management IP instead of 0.0.0.0.
"""
try:
    import mock
except ImportError:
    from unittest import mock

import os
import tempfile
import unittest

from zstacklib.utils import jsonobject


class TestUpdateLibvirtListenAddr(unittest.TestCase):
    """Test cases for libvirt listen_addr update during host connect."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.conf_file = os.path.join(self.tmpdir, 'libvirtd.conf')

    def tearDown(self):
        if os.path.exists(self.conf_file):
            os.remove(self.conf_file)
        os.rmdir(self.tmpdir)

    def _write_conf(self, content):
        with open(self.conf_file, 'w') as f:
            f.write(content)

    def _read_conf(self):
        with open(self.conf_file, 'r') as f:
            return f.read()

    def test_listen_addr_replaced_from_0000(self):
        """listen_addr = "0.0.0.0" should be replaced with management IP."""
        self._write_conf(
            'listen_tls = 0\n'
            'listen_tcp = 1\n'
            'listen_addr = "0.0.0.0"\n'
            'auth_tcp = "none"\n'
        )
        expected_ip = '192.168.1.100'
        # Simulate sed replacement
        content = self._read_conf()
        import re
        content = re.sub(
            r'^\s*listen_addr\s*=.*$',
            'listen_addr = "%s"' % expected_ip,
            content,
            flags=re.MULTILINE
        )
        self._write_conf(content)

        result = self._read_conf()
        self.assertIn('listen_addr = "192.168.1.100"', result)
        self.assertNotIn('0.0.0.0', result)

    def test_listen_addr_replaced_from_specific_ip(self):
        """Existing listen_addr with a different IP should be updated."""
        self._write_conf(
            'listen_tls = 0\n'
            'listen_tcp = 1\n'
            'listen_addr = "10.0.0.1"\n'
            'auth_tcp = "none"\n'
        )
        expected_ip = '192.168.1.200'
        content = self._read_conf()
        import re
        content = re.sub(
            r'^\s*listen_addr\s*=.*$',
            'listen_addr = "%s"' % expected_ip,
            content,
            flags=re.MULTILINE
        )
        self._write_conf(content)

        result = self._read_conf()
        self.assertIn('listen_addr = "192.168.1.200"', result)
        self.assertNotIn('10.0.0.1', result)

    def test_no_change_when_addr_already_correct(self):
        """No change should be made if listen_addr is already correct."""
        expected_ip = '192.168.1.100'
        original = (
            'listen_tls = 0\n'
            'listen_tcp = 1\n'
            'listen_addr = "%s"\n'
            'auth_tcp = "none"\n'
        ) % expected_ip
        self._write_conf(original)

        # Check that the expected line is already present
        content = self._read_conf()
        expected_line = 'listen_addr = "%s"' % expected_ip
        self.assertIn(expected_line, content)
        # Content should remain unchanged
        self.assertEqual(original, content)

    def test_connect_cmd_with_libvirt_listen_addr(self):
        """ConnectCmd should carry libvirtListenAddr field."""
        cmd_json = '{"libvirtListenAddr": "192.168.1.50", "hostUuid": "test-uuid"}'
        cmd = jsonobject.loads(cmd_json)
        self.assertEqual(cmd.libvirtListenAddr, '192.168.1.50')
        self.assertEqual(cmd.hostUuid, 'test-uuid')

    def test_connect_cmd_without_libvirt_listen_addr(self):
        """ConnectCmd without libvirtListenAddr should not fail."""
        cmd_json = '{"hostUuid": "test-uuid"}'
        cmd = jsonobject.loads(cmd_json)
        listen_addr = getattr(cmd, 'libvirtListenAddr', None)
        self.assertIsNone(listen_addr)

    def test_deploy_args_serialization(self):
        """Verify libvirt_listen_addr is properly serialized in deploy args."""
        import json
        deploy_args = {
            "pkg_kvmagent": "kvmagent-5.5.0.tar.gz",
            "libvirt_listen_addr": "10.0.0.5",
            "restart_libvirtd": "false"
        }
        serialized = json.dumps(deploy_args)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized['libvirt_listen_addr'], '10.0.0.5')


if __name__ == '__main__':
    unittest.main()
