# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for cross-module testing.

This module provides reusable fixtures that can be used across all test modules
in the zstack-utility monorepo.

Available fixtures:
- project_root: Returns monorepo root Path (session scope)
- tmp_test_dir: Creates temporary test directory (function scope)
- sample_vm_xml: Returns minimal libvirt VM XML template (session scope)
- fake_zstack_config: Returns mock ZStack config dict (function scope)
- isolated_env: Isolates environment variables for tests (function scope)
"""
import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root():
    """
    Return the root directory of the zstack-utility monorepo as Path object.
    
    Scope: session (shared across all tests, created once per test session)
    
    Usage:
        def test_something(project_root):
            config_file = project_root / "pyproject.toml"
            assert config_file.exists()
    
    Returns:
        Path: Absolute path to monorepo root
    """
    return Path(__file__).parent.parent.parent


@pytest.fixture
def tmp_test_dir(tmp_path):
    """
    Provide a temporary test directory that cleans up automatically after tests.
    
    Scope: function (new temp dir for each test)
    
    Uses pytest's built-in tmp_path fixture, which automatically cleans up
    after the test completes.
    
    Usage:
        def test_file_creation(tmp_test_dir):
            test_file = tmp_test_dir / "test.txt"
            test_file.write_text("content")
            assert test_file.exists()
        # Directory is automatically cleaned up after test
    
    Returns:
        Path: Temporary directory path (unique per test)
    """
    return tmp_path


@pytest.fixture(scope="session")
def sample_vm_xml():
    """
    Return a minimal but valid libvirt VM XML template string.
    
    Scope: session (shared across all tests)
    
    This provides a basic VM domain XML that can be used for testing
    VM-related functionality (mocking libvirt.virDomain, XML parsing, etc.).
    Tests can modify this template for their specific needs.
    
    Based on patterns from kvmagent/kvmagent/test/libvirt_testsuite/
    
    Usage:
        def test_vm_xml_parsing(sample_vm_xml):
            from xml.etree import ElementTree as ET
            root = ET.fromstring(sample_vm_xml)
            assert root.tag == "domain"
            assert root.get("type") == "kvm"
    
    Returns:
        str: Minimal libvirt domain XML template
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
<domain type='kvm'>
  <name>test-vm-uuid</name>
  <uuid>12345678-1234-1234-1234-123456789abc</uuid>
  <description>test-vm-for-unit-tests</description>
  <memory unit='KiB'>1048576</memory>
  <currentMemory unit='KiB'>1048576</currentMemory>
  <vcpu placement='static'>2</vcpu>
  <os>
    <type arch='x86_64' machine='pc'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-kvm</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2' cache='none'/>
      <source file='/tmp/test-disk.qcow2'/>
      <target dev='vda' bus='virtio'/>
      <serial>test-disk-serial</serial>
    </disk>
    <interface type='bridge'>
      <mac address='52:54:00:12:34:56'/>
      <source bridge='br0'/>
      <model type='virtio'/>
    </interface>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
  </devices>
</domain>"""


@pytest.fixture
def fake_zstack_config():
    """
    Return a mock ZStack configuration dictionary.
    
    Scope: function (new config dict for each test)
    
    This provides a realistic ZStack config structure for testing without
    loading actual config files. Based on common patterns from kvmagent tests.
    
    Tests can modify the returned dict as needed.
    
    Usage:
        def test_config_loading(fake_zstack_config):
            assert fake_zstack_config['log_dir'] == '/tmp/zstack-test-logs'
            fake_zstack_config['custom_key'] = 'custom_value'
    
    Returns:
        dict: Mock ZStack configuration with common keys
    """
    return {
        'log_dir': '/tmp/zstack-test-logs',
        'data_dir': '/tmp/zstack-test-data',
        'var_lib_dir': '/var/lib/zstack',
        'usr_local_dir': '/usr/local/zstack',
        'properties': {
            'host_uuid': 'test-host-uuid',
            'management_ip': '127.0.0.1',
            'api_port': 8080,
        },
        'agent_type': 'kvmagent',
        'debug_mode': True,
    }


@pytest.fixture
def isolated_env():
    """
    Isolate environment variables - restore original env after test.
    
    Scope: function (isolates env for each test)
    
    This fixture saves the current os.environ state, yields it for test
    modifications, then restores the original environment after the test.
    
    Prevents environment variable pollution between tests.
    
    Usage:
        def test_env_modification(isolated_env):
            os.environ['TEST_VAR'] = 'test_value'
            assert os.environ['TEST_VAR'] == 'test_value'
        # Original env is restored after test
        
        def test_env_is_clean():
            assert 'TEST_VAR' not in os.environ  # passes
    
    Yields:
        dict: os.environ (tests can modify directly)
    """
    original = os.environ.copy()
    yield os.environ
    # Restore original environment
    os.environ.clear()
    os.environ.update(original)
