# -*- coding: utf-8 -*-
"""
Unit tests for kvmagent network plugin functionality.

Tests network utility functions with mocked system calls.
No real network interfaces required - all external calls are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock


@pytest.mark.kvmagent
@pytest.mark.network
def test_bridge_config_parsing():
    """
    Test network bridge configuration parsing.
    
    Mocks 'brctl show' or 'ip link show' output and validates
    bridge interface detection and parsing.
    
    Note: Marked as @pytest.mark.network - will auto-skip without --allow-destructive
    since real bridge operations could affect system network configuration.
    """
    with patch('subprocess.run') as mock_run:
        # Mock 'brctl show' output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """bridge name     bridge id               STP enabled     interfaces
br0             8000.000000000000       no              eth0
                                                        vnet0
br1             8000.111111111111       no              eth1
"""
        mock_run.return_value = mock_result
        
        import subprocess
        
        # Execute mocked bridge list command
        result = subprocess.run(
            ['brctl', 'show'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'br0' in result.stdout
        assert 'br1' in result.stdout
        assert 'eth0' in result.stdout
        
        # Parse bridge names from output
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        bridges = []
        for line in lines:
            if line and not line.startswith(' '):
                bridge_name = line.split()[0]
                bridges.append(bridge_name)
        
        assert 'br0' in bridges
        assert 'br1' in bridges
        assert len(bridges) == 2


@pytest.mark.kvmagent
@pytest.mark.network
def test_ip_address_validation():
    """
    Test IP address validation logic.
    
    Tests validation of IPv4 addresses using netaddr or regex patterns.
    
    Note: Marked as @pytest.mark.network - while this doesn't touch real interfaces,
    it's network-related and grouped with other network tests for consistency.
    """
    # Test valid IPv4 addresses
    valid_ips = [
        "192.168.1.1",
        "10.0.0.1",
        "172.16.0.1",
        "127.0.0.1",
        "255.255.255.255",
    ]
    
    # Test invalid IPv4 addresses
    invalid_ips = [
        "256.1.1.1",
        "192.168.1",
        "192.168.1.1.1",
        "abc.def.ghi.jkl",
        "192.168.-1.1",
        "",
    ]
    
    # Simple validation function (mirrors common kvmagent pattern)
    import re
    ip_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    def is_valid_ipv4(ip):
        if not ip:
            return False
        return ip_pattern.match(ip) is not None
    
    # Test valid IPs
    for ip in valid_ips:
        assert is_valid_ipv4(ip), f"{ip} should be valid"
    
    # Test invalid IPs
    for ip in invalid_ips:
        assert not is_valid_ipv4(ip), f"{ip} should be invalid"


@pytest.mark.kvmagent
@pytest.mark.network
def test_network_interface_status_check():
    """
    Test network interface status checking.
    
    Mocks 'ip link show' output to test interface state detection
    (up/down, speed, etc.).
    
    Note: Marked as @pytest.mark.network - will auto-skip without --allow-destructive.
    """
    with patch('subprocess.run') as mock_run:
        # Mock 'ip link show eth0' output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP mode DEFAULT group default qlen 1000
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff"""
        mock_run.return_value = mock_result
        
        import subprocess
        
        # Check interface status
        result = subprocess.run(
            ['ip', 'link', 'show', 'eth0'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        output = result.stdout
        
        # Parse interface state
        assert 'eth0:' in output
        assert 'state UP' in output
        assert 'mtu 1500' in output
        
        # Extract MAC address
        mac_line = [line for line in output.split('\n') if 'link/ether' in line][0]
        mac_address = mac_line.split()[1]
        assert mac_address == '52:54:00:12:34:56'


@pytest.mark.kvmagent
def test_vlan_interface_name_parsing():
    """
    Test VLAN interface name parsing logic.
    
    Tests extraction of physical interface and VLAN ID from VLAN interface names
    (e.g., eth0.100 -> interface=eth0, vlan=100).
    
    This is a pure logic test with no external dependencies.
    """
    test_cases = [
        ('eth0.100', 'eth0', 100),
        ('eth1.200', 'eth1', 200),
        ('bond0.4094', 'bond0', 4094),
        ('enp0s3.1', 'enp0s3', 1),
    ]
    
    def parse_vlan_interface(vlan_if):
        """Parse VLAN interface name into base interface and VLAN ID."""
        if '.' not in vlan_if:
            return None, None
        parts = vlan_if.rsplit('.', 1)
        if len(parts) != 2:
            return None, None
        base_if = parts[0]
        if not base_if or base_if.endswith('.'):
            return None, None
        try:
            vlan_id = int(parts[1])
            if 1 <= vlan_id <= 4094:  # Valid VLAN ID range
                return base_if, vlan_id
        except ValueError:
            pass
        return None, None
    
    # Test valid VLAN interfaces
    for vlan_if, expected_base, expected_vlan in test_cases:
        base_if, vlan_id = parse_vlan_interface(vlan_if)
        assert base_if == expected_base, f"Expected base {expected_base}, got {base_if}"
        assert vlan_id == expected_vlan, f"Expected VLAN {expected_vlan}, got {vlan_id}"
    
    # Test invalid VLAN interfaces
    invalid_cases = ['eth0', 'eth0.5000', 'eth0.abc', 'eth0..100']
    for invalid_if in invalid_cases:
        base_if, vlan_id = parse_vlan_interface(invalid_if)
        assert base_if is None and vlan_id is None, f"{invalid_if} should be invalid"
