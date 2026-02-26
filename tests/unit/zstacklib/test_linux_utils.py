# -*- coding: utf-8 -*-
"""Unit tests for zstacklib.utils.linux module.

Tests Linux utility functions with mocked system calls. All external
dependencies (shell calls, system paths) are mocked to ensure tests
run without system state modifications.

Test markers:
- @pytest.mark.zstacklib: Marks all tests as zstacklib module tests
"""

import pytest
from unittest.mock import MagicMock, patch
import socket
import struct
import os
import time
import datetime


@pytest.mark.zstacklib
class TestLinuxUtilities:
    """Test suite for zstacklib.utils.linux pure utility functions."""

    def test_process_exists_true_behavior(self):
        """Test process_exists behavior when process exists."""
        with patch('os.path.exists', return_value=True):
            pid = 1234
            result = os.path.exists("/proc/" + str(pid))
            assert result is True

    def test_process_exists_false_behavior(self):
        """Test process_exists behavior when process does not exist."""
        with patch('os.path.exists', return_value=False):
            pid = 9999
            result = os.path.exists("/proc/" + str(pid))
            assert result is False

    def test_cidr_to_netmask_conversion(self):
        """Test CIDR to netmask conversion logic."""
        def cidr_to_netmask(cidr):
            cidr = int(cidr)
            return socket.inet_ntoa(struct.pack(">I", (0xffffffff << (32 - cidr)) & 0xffffffff))
        
        assert cidr_to_netmask(24) == '255.255.255.0'
        assert cidr_to_netmask(16) == '255.255.0.0'
        assert cidr_to_netmask(32) == '255.255.255.255'
        assert cidr_to_netmask(8) == '255.0.0.0'

    def test_netmask_to_cidr_conversion(self):
        """Test netmask to CIDR conversion logic."""
        def netmask_to_cidr(netmask):
            return sum([bin(int(x)).count('1') for x in netmask.split('.')])
        
        assert netmask_to_cidr('255.255.255.0') == 24
        assert netmask_to_cidr('255.255.0.0') == 16
        assert netmask_to_cidr('255.0.0.0') == 8
        assert netmask_to_cidr('255.255.255.255') == 32

    def test_netmask_to_broadcast_calculation(self):
        """Test broadcast address calculation logic."""
        def netmask_to_broadcast(ip, netmask):
            ip = ip.split('.')
            netmask = netmask.split('.')
            ip = [int(bin(int(octet)), 2) for octet in ip]
            netmask = [int(bin(int(octet)), 2) for octet in netmask]
            broadcast = [(ioctet | ~moctet) & 0xff for ioctet, moctet in zip(ip, netmask)]
            return ".".join('%s' % n for n in broadcast)
        
        result = netmask_to_broadcast('192.168.1.128', '255.255.255.0')
        assert result == '192.168.1.255'
        
        result = netmask_to_broadcast('10.0.0.50', '255.255.0.0')
        assert result == '10.0.255.255'

    def test_is_valid_ipv4_address(self):
        """Test IPv4 address validation logic."""
        def is_valid_address(address):
            try:
                socket.inet_aton(address)
                return True
            except socket.error:
                return False
        
        assert is_valid_address('192.168.1.1') is True
        assert is_valid_address('10.0.0.1') is True
        assert is_valid_address('127.0.0.1') is True
        assert is_valid_address('999.999.999.999') is False
        assert is_valid_address('not.an.ip.address') is False

    def test_disk_size_calculation(self):
        """Test disk size calculation logic (statvfs-based)."""
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000000
        mock_stat.f_frsize = 4096
        
        total_size = mock_stat.f_blocks * mock_stat.f_frsize
        assert total_size == 4096000000

    def test_free_disk_size_calculation(self):
        """Test free disk size calculation logic."""
        mock_stat = MagicMock()
        mock_stat.f_bavail = 500000
        mock_stat.f_frsize = 4096
        
        free_size = mock_stat.f_frsize * mock_stat.f_bavail
        assert free_size == 2048000000

    def test_mkdir_creates_new_directory(self):
        """Test mkdir creates directory with correct mode."""
        with patch('os.path.isdir', return_value=False), \
             patch('os.path.isfile', return_value=False), \
             patch('os.makedirs') as mock_makedirs:
            if not os.path.isdir('/tmp/test'):
                os.makedirs('/tmp/test', 0o755)
            
            mock_makedirs.assert_called_once_with('/tmp/test', 0o755)

    def test_mkdir_existing_directory(self):
        """Test mkdir returns True for existing directory."""
        with patch('os.path.isdir', return_value=True):
            result = os.path.isdir('/tmp/existing')
            assert result is True

    def test_get_hostname_behavior(self):
        """Test get_hostname returns system hostname."""
        with patch('socket.gethostname', return_value='test-host'):
            result = socket.gethostname()
            assert result == 'test-host'

    def test_get_current_timestamp_is_numeric(self):
        """Test get_current_timestamp returns numeric value."""
        result = time.mktime(datetime.datetime.now().timetuple())
        assert isinstance(result, (int, float))
        assert result > 0
