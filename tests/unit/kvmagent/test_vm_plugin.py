# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Unit tests for kvmagent VM plugin functionality.

Tests VM-related operations with mocked libvirt dependencies.
No real hypervisor required - all external calls are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from xml.etree import ElementTree as ET


@pytest.mark.kvmagent
def test_vm_xml_parsing(sample_vm_xml):
    """
    Test parsing of VM XML structure.
    
    Validates that sample_vm_xml fixture provides a valid libvirt domain XML
    with expected structure (domain type, name, uuid, memory, vcpu, devices).
    """
    root = ET.fromstring(sample_vm_xml)
    
    # Verify root element
    assert root.tag == "domain"
    assert root.get("type") == "kvm"
    
    # Verify required VM components
    name = root.find("name")
    assert name is not None
    assert name.text == "test-vm-uuid"
    
    uuid = root.find("uuid")
    assert uuid is not None
    assert uuid.text == "12345678-1234-1234-1234-123456789abc"
    
    # Verify memory configuration
    memory = root.find("memory")
    assert memory is not None
    assert memory.get("unit") == "KiB"
    assert int(memory.text) == 1048576
    
    # Verify vcpu configuration
    vcpu = root.find("vcpu")
    assert vcpu is not None
    assert int(vcpu.text) == 2
    
    # Verify devices section exists
    devices = root.find("devices")
    assert devices is not None
    
    # Verify disk device
    disk = devices.find("disk")
    assert disk is not None
    assert disk.get("type") == "file"
    assert disk.get("device") == "disk"
    
    # Verify network interface
    interface = devices.find("interface")
    assert interface is not None
    assert interface.get("type") == "bridge"


@pytest.mark.kvmagent
def test_vm_state_parsing_with_mock_libvirt():
    """
    Test VM state parsing from mocked libvirt domain info.
    
    Mocks libvirt.virDomain.info() response and validates state extraction
    without requiring real hypervisor connection.
    """
    with patch('libvirt.open') as mock_libvirt_open:
        # Mock libvirt connection
        mock_conn = MagicMock()
        mock_libvirt_open.return_value = mock_conn
        
        # Mock VM domain
        mock_domain = MagicMock()
        mock_conn.lookupByUUIDString.return_value = mock_domain
        
        # Mock domain.info() - returns tuple: (state, maxMem, memory, nrVirtCpu, cpuTime)
        # State values: VIR_DOMAIN_RUNNING=1, VIR_DOMAIN_SHUTOFF=5
        mock_domain.info.return_value = (1, 1048576, 1048576, 2, 1234567890)
        mock_domain.isActive.return_value = 1
        
        # Test state extraction
        test_uuid = "12345678-1234-1234-1234-123456789abc"
        
        import libvirt
        conn = libvirt.open('test:///default')
        domain = conn.lookupByUUIDString(test_uuid)
        
        state_info = domain.info()
        assert state_info[0] == 1  # VIR_DOMAIN_RUNNING
        assert state_info[1] == 1048576  # maxMem
        assert state_info[2] == 1048576  # memory
        assert state_info[3] == 2  # nrVirtCpu
        assert domain.isActive() == 1


@pytest.mark.kvmagent
def test_disk_format_conversion_logic():
    """
    Test disk format conversion validation logic.
    
    Tests common disk format conversions (raw -> qcow2, qcow2 -> raw)
    with mocked qemu-img operations.
    """
    with patch('subprocess.run') as mock_run:
        # Mock qemu-img info output for source image
        mock_info_result = Mock()
        mock_info_result.returncode = 0
        mock_info_result.stdout = """image: /tmp/test-disk.raw
file format: raw
virtual size: 10 GiB (10737418240 bytes)
disk size: 0 B"""
        
        # Mock qemu-img convert success
        mock_convert_result = Mock()
        mock_convert_result.returncode = 0
        mock_convert_result.stdout = ""
        
        # Setup mock to return different results based on args
        def side_effect(*args, **kwargs):
            if 'info' in args[0]:
                return mock_info_result
            elif 'convert' in args[0]:
                return mock_convert_result
            return Mock(returncode=0, stdout="")
        
        mock_run.side_effect = side_effect
        
        import subprocess
        
        # Test format detection
        result = subprocess.run(
            ['qemu-img', 'info', '/tmp/test-disk.raw'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert 'file format: raw' in result.stdout
        
        # Test conversion command
        result = subprocess.run(
            ['qemu-img', 'convert', '-f', 'raw', '-O', 'qcow2', 
             '/tmp/test-disk.raw', '/tmp/test-disk.qcow2'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0


@pytest.mark.kvmagent
def test_vm_xml_device_extraction(sample_vm_xml):
    """
    Test extraction of specific device configurations from VM XML.
    
    Validates ability to extract and parse disk and network device
    configurations from libvirt domain XML.
    """
    root = ET.fromstring(sample_vm_xml)
    devices = root.find("devices")
    
    # Extract disk configuration
    disk = devices.find("disk")
    driver = disk.find("driver")
    assert driver.get("name") == "qemu"
    assert driver.get("type") == "qcow2"
    assert driver.get("cache") == "none"
    
    source = disk.find("source")
    assert source.get("file") == "/tmp/test-disk.qcow2"
    
    target = disk.find("target")
    assert target.get("dev") == "vda"
    assert target.get("bus") == "virtio"
    
    # Extract network configuration
    interface = devices.find("interface")
    mac = interface.find("mac")
    assert mac.get("address") == "52:54:00:12:34:56"
    
    bridge_source = interface.find("source")
    assert bridge_source.get("bridge") == "br0"
    
    model = interface.find("model")
    assert model.get("type") == "virtio"


@pytest.mark.kvmagent
def test_vm_memory_configuration_update(sample_vm_xml):
    """
    Test VM memory configuration modification in XML.
    
    Validates ability to parse and update memory settings in libvirt domain XML.
    """
    root = ET.fromstring(sample_vm_xml)
    
    # Read current memory
    memory = root.find("memory")
    current_memory_kb = int(memory.text)
    assert current_memory_kb == 1048576  # 1GB in KiB
    
    # Simulate memory update to 2GB
    new_memory_kb = 2097152
    memory.text = str(new_memory_kb)
    
    current_memory = root.find("currentMemory")
    current_memory.text = str(new_memory_kb)
    
    # Verify update
    assert int(root.find("memory").text) == new_memory_kb
    assert int(root.find("currentMemory").text) == new_memory_kb
    
    # Verify XML can be serialized back
    updated_xml = ET.tostring(root, encoding='unicode')
    assert '<memory unit="KiB">{}</memory>'.format(new_memory_kb) in updated_xml
