#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GPU Vendor Plugin System - Unit Tests

Run with: python -m pytest tests/test_gpu_vendors.py -v
Or simply: python tests/test_gpu_vendors.py
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGPUBase(unittest.TestCase):
    """Test base class functionality"""
    
    def test_normalize_pci_address_8char_domain(self):
        """Test PCI address normalization with 8-char domain"""
        from zstacklib.gpu.base import GPUBase
        
        result = GPUBase.normalize_pci_address("00000000:3B:00.0")
        self.assertEqual(result, "0000:3b:00.0")
    
    def test_normalize_pci_address_4char_domain(self):
        """Test PCI address normalization with 4-char domain"""
        from zstacklib.gpu.base import GPUBase
        
        result = GPUBase.normalize_pci_address("0000:3B:00.0")
        self.assertEqual(result, "0000:3b:00.0")
    
    def test_parse_unit_value(self):
        """Test unit value parsing"""
        from zstacklib.gpu.base import GPUBase
        
        # Test various formats
        self.assertEqual(GPUBase.parse_unit_value("15360 MiB"), 15360.0)
        self.assertEqual(GPUBase.parse_unit_value("70.00 W"), 70.0)
        self.assertEqual(GPUBase.parse_unit_value("45.5"), 45.5)
        self.assertIsNone(GPUBase.parse_unit_value(""))
        self.assertIsNone(GPUBase.parse_unit_value(None))
    
    def test_parse_unit_value_with_target_unit(self):
        """Test unit value parsing with target_unit validation"""
        from zstacklib.gpu.base import GPUBase
        
        # Test matching units
        self.assertEqual(GPUBase.parse_unit_value("15360 MiB", "MiB"), 15360.0)
        self.assertEqual(GPUBase.parse_unit_value("70.00 W", "W"), 70.0)
        self.assertEqual(GPUBase.parse_unit_value("45.5 %", "%"), 45.5)
        self.assertEqual(GPUBase.parse_unit_value("40 C", "C"), 40.0)
        
        # Test case-insensitive matching
        self.assertEqual(GPUBase.parse_unit_value("15360 mib", "MiB"), 15360.0)
        self.assertEqual(GPUBase.parse_unit_value("70.00 w", "W"), 70.0)
        
        # Test unit mismatch - should return None
        self.assertIsNone(GPUBase.parse_unit_value("15360 MiB", "W"))
        self.assertIsNone(GPUBase.parse_unit_value("70.00 W", "MiB"))
        self.assertIsNone(GPUBase.parse_unit_value("45.5", "W"))  # No unit when expected
        
        # Test without target_unit - should work as before
        self.assertEqual(GPUBase.parse_unit_value("15360 MiB"), 15360.0)
        self.assertEqual(GPUBase.parse_unit_value("70.00 W"), 70.0)


class TestGPUVendorRegistry(unittest.TestCase):
    """Test vendor registration system"""
    
    def test_nvidia_registered(self):
        """Test NVIDIA vendor is registered"""
        from zstacklib.gpu import get_gpu_vendor
        
        vendor = get_gpu_vendor("NVIDIA")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "NVIDIA")
    
    def test_amd_registered(self):
        """Test AMD vendor is registered"""
        from zstacklib.gpu import get_gpu_vendor
        
        vendor = get_gpu_vendor("AMD")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "AMD")
    
    def test_huawei_registered(self):
        """Test Huawei vendor is registered"""
        from zstacklib.gpu import get_gpu_vendor
        
        vendor = get_gpu_vendor("Huawei")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "Huawei")
    
    def test_get_all_vendors(self):
        """Test getting all registered vendors"""
        from zstacklib.gpu import get_all_gpu_vendors
        
        vendors = get_all_gpu_vendors()
        # In Python 2 values() returns a list, in Python 3 it returns a view
        self.assertTrue(len(vendors) >= 8)
        
        vendor_names = [v.VENDOR_NAME for v in vendors]
        self.assertIn("NVIDIA", vendor_names)
        self.assertIn("AMD", vendor_names)
        self.assertIn("Huawei", vendor_names)
        self.assertIn("Tianshu", vendor_names)
        self.assertIn("Vastai", vendor_names)
        self.assertIn("Enflame", vendor_names)
        self.assertIn("Haiguang", vendor_names)
        self.assertIn("Alibaba", vendor_names)

    def test_get_vendor_by_id(self):
        """Test finding vendor by PCI ID"""
        from zstacklib.gpu import get_vendor_by_id
        
        # NVIDIA
        vendor = get_vendor_by_id("10de")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "NVIDIA")
        
        # AMD
        vendor = get_vendor_by_id("1002")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "AMD")

        # Tianshu
        vendor = get_vendor_by_id("1e3e")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "Tianshu")

        # Vastai
        vendor = get_vendor_by_id("1edb")
        self.assertIsNotNone(vendor)
        self.assertEqual(vendor.VENDOR_NAME, "Vastai")

    def test_get_vendor_enum_mapping(self):
        """Test dynamic VendorEnum mapping"""
        from zstacklib.gpu import get_vendor_enum_mapping
        
        mapping = get_vendor_enum_mapping()
        self.assertIsInstance(mapping, dict)
        self.assertEqual(mapping.get("NVIDIA"), "NVIDIA")
        self.assertEqual(mapping.get("AMD"), "AMD")
        self.assertEqual(mapping.get("TianShu"), "Tianshu")
        self.assertEqual(mapping.get("Vastai"), "Vastai")


class TestNVIDIA(unittest.TestCase):
    """Test NVIDIA vendor implementation"""
    
    def test_vendor_config(self):
        """Test NVIDIA vendor configuration"""
        from zstacklib.gpu.vendors.nvidia import NVIDIA
        
        self.assertEqual(NVIDIA.VENDOR_NAME, "NVIDIA")
        self.assertIn("10de", NVIDIA.VENDOR_IDS)
        self.assertEqual(NVIDIA.CLI_TOOL, "nvidia-smi")
    
    def test_parse_basic_info(self):
        """Test NVIDIA basic info parsing"""
        from zstacklib.gpu.vendors.nvidia import NVIDIA

        output = """00000000:3B:00.0, 15360 MiB, 70.00 W, 1322519087621
00000000:86:00.0, 15360 MiB, 70.00 W, 1322519087622"""

        infos = NVIDIA.parse_basic_info(output)

        self.assertEqual(len(infos), 2)
        self.assertEqual(infos[0].pci_address, "0000:3b:00.0")
        self.assertEqual(infos[0].memory, "15360 MiB")
        self.assertEqual(infos[0].power, "70.00 W")
        self.assertEqual(infos[0].serial_number, "1322519087621")

    def test_parse_basic_info_with_function_1(self):
        """Test NVIDIA basic info parsing with function 1 devices (should only return function 0)"""
        from zstacklib.gpu.vendors.nvidia import NVIDIA

        # Simulate nvidia-smi returning both function 0 and function 1
        # Note: In reality, nvidia-smi should only return function 0, but we test the edge case
        output = """00000000:34:00.0, 15360 MiB, 70.00 W, 1322519087621
00000000:34:00.1, 15360 MiB, 70.00 W, 1322519087621
00000000:9e:00.0, 15360 MiB, 70.00 W, 1322519087622"""

        infos = NVIDIA.parse_basic_info(output)

        # All devices are parsed, but in get_all_gpu_infos_by_pci() we should filter to only function 0
        self.assertEqual(len(infos), 3)
        # Verify function numbers are preserved
        self.assertEqual(infos[0].pci_address, "0000:34:00.0")
        self.assertEqual(infos[1].pci_address, "0000:34:00.1")
        self.assertEqual(infos[2].pci_address, "0000:9e:00.0")
    
    def test_parse_metrics(self):
        """Test NVIDIA metrics parsing"""
        from zstacklib.gpu.vendors.nvidia import NVIDIA
        
        # Format: gpu_bus_id,utilization.gpu,utilization.memory,temperature.gpu,power.draw,index,gpu_serial
        # Note: index is required (7 fields total)
        output = "00000000:3B:00.0, 45 %, 62 %, 58, 65.23, 0, ABC123"
        
        metrics = NVIDIA.parse_metrics(output)
        
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.pci_address, "0000:3b:00.0")
        self.assertEqual(m.serial_number, "ABC123")
        self.assertEqual(m.power_draw, 65.23)
        self.assertEqual(m.temperature, 58.0)
        self.assertEqual(m.utilization, 45.0)
        self.assertEqual(m.memory_utilization, 62.0)


class TestAMD(unittest.TestCase):
    """Test AMD vendor implementation"""
    
    def test_parse_basic_info_json(self):
        """Test AMD JSON parsing"""
        from zstacklib.gpu.vendors.amd import AMD
        
        output = """{
            "card0": {
                "PCI Bus": "0000:03:00.0",
                "VRAM Total Memory (B)": 16106127360,
                "Average Graphics Package Power (W)": "42.0",
                "Serial Number": "ABC123"
            }
        }"""
        
        infos = AMD.parse_basic_info(output)
        
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].pci_address, "0000:03:00.0")
        self.assertEqual(infos[0].serial_number, "ABC123")
        self.assertIn("MiB", infos[0].memory)


class TestHuawei(unittest.TestCase):
    """Test Huawei vendor implementation"""
    
    def test_vendor_config(self):
        """Test Huawei vendor configuration"""
        from zstacklib.gpu.vendors.huawei import Huawei
        
        self.assertEqual(Huawei.VENDOR_NAME, "Huawei")
        self.assertIn("19e5", Huawei.VENDOR_IDS)
        self.assertEqual(Huawei.CLI_TOOL, "npu-smi")
    
    def test_parse_basic_info(self):
        """Test Huawei basic info parsing"""
        from zstacklib.gpu.vendors.huawei import Huawei
        
        output = """
Serial Number : ABC123456
PCIe Bus Info : 0000:3b:00.0
DDR Capacity(MB) : 32768
Power Dissipation : 150 W
"""
        
        infos = Huawei.parse_basic_info(output)
        
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].pci_address, "0000:3b:00.0")
        self.assertEqual(infos[0].serial_number, "ABC123456")
        self.assertEqual(infos[0].memory, "32768 MB")


class TestGPUInfo(unittest.TestCase):
    """Test GPUInfo dataclass"""
    
    def test_to_addon_dict(self):
        """Test conversion to addon dict"""
        from zstacklib.gpu.base import GPUInfo
        
        info = GPUInfo(
            pci_address="0000:3b:00.0",
            memory="15360 MiB",
            power="70 W",
            serial_number="ABC123",
            driver_loaded=True,
        )
        
        addon = info.to_addon_dict()
        
        self.assertEqual(addon["memory"], "15360 MiB")
        self.assertEqual(addon["power"], "70 W")
        self.assertEqual(addon["serialNumber"], "ABC123")
        self.assertTrue(addon["isDriverLoaded"])


class TestIdentifyVendor(unittest.TestCase):
    """Test vendor identification utilities"""
    
    def test_identify_vendor_by_pci_id(self):
        """Test vendor identification by PCI ID"""
        from zstacklib.gpu import identify_vendor
        
        # NVIDIA by vendor ID
        result = identify_vendor("Unknown Device", "10de")
        self.assertEqual(result, "NVIDIA")
        
        # AMD by vendor ID
        result = identify_vendor("Unknown Device", "1002")
        self.assertEqual(result, "AMD")
    
    def test_identify_vendor_by_name(self):
        """Test vendor identification by PCI name"""
        from zstacklib.gpu import identify_vendor
        
        # NVIDIA by name
        result = identify_vendor("NVIDIA Corporation Tesla T4", "ffff")
        self.assertEqual(result, "NVIDIA")
    
    def test_identify_vendor_combined(self):
        """Test vendor identification with both name and ID"""
        from zstacklib.gpu import identify_vendor
        
        # Should match by ID first
        result = identify_vendor("NVIDIA Corporation Tesla T4", "10de")
        self.assertEqual(result, "NVIDIA")


if __name__ == '__main__':
    unittest.main(verbosity=2)
