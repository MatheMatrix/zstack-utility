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

from zstacklib.gpu.base import PCI_CLASS_PROCESSING_ACCEL


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

    def test_get_pci_only_candidates_3d_controller(self):
        """NVIDIA get_pci_only_candidates returns 10de + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.nvidia import NVIDIA

        device_ids = {"0000:3b:00.0": {"Vendor": "10de", "Class": "030200", "Device": "1eb8"}}
        device_names = {
            "0000:3b:00.0": {
                "Class": "3D controller",
                "Vendor": "NVIDIA Corporation",
                "Device": "TU104",
            },
        }
        candidates = NVIDIA.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:3b:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """NVIDIA get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.nvidia import NVIDIA

        device_ids = {"0000:3b:00.1": {"Vendor": "10de", "Class": "030200", "Device": "1eb8"}}
        device_names = {
            "0000:3b:00.1": {"Class": "3D controller", "Vendor": "NVIDIA Corporation", "Device": "TU104"},
        }
        candidates = NVIDIA.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


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

    def test_get_pci_only_candidates(self):
        """AMD get_pci_only_candidates returns 1002 + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.amd import AMD

        device_ids = {"0000:03:00.0": {"Vendor": "1002", "Class": "030200", "Device": "7310"}}
        device_names = {
            "0000:03:00.0": {
                "Class": "3D controller",
                "Vendor": "Advanced Micro Devices, Inc.",
                "Device": "Navi 10",
            },
        }
        candidates = AMD.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:03:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """AMD get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.amd import AMD

        device_ids = {"0000:03:00.1": {"Vendor": "1002", "Class": "030200", "Device": "7310"}}
        device_names = {
            "0000:03:00.1": {"Class": "3D controller", "Vendor": "Advanced Micro Devices, Inc.", "Device": "Navi 10"},
        }
        candidates = AMD.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


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

    def test_get_pci_only_candidates_processing_accelerators(self):
        """Huawei get_pci_only_candidates returns 19e5 + Processing accelerators when device name is valid."""
        from zstacklib.gpu.vendors.huawei import Huawei

        device_ids = {
            "0000:82:00.0": {"Vendor": "19e5", "Class": "120000", "Device": "d802"},
        }
        device_names = {
            "0000:82:00.0": {
                "Class": PCI_CLASS_PROCESSING_ACCEL,
                "Vendor": "Huawei Technologies Co., Ltd.",
                "Device": "Device d802",
            },
        }
        candidates = Huawei.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:82:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_invalid_device_name(self):
        """Huawei get_pci_only_candidates returns empty when device name fails is_valid_processing_accelerator."""
        from zstacklib.gpu.vendors.huawei import Huawei

        device_ids = {
            "0000:82:00.0": {"Vendor": "19e5", "Class": "120000", "Device": "unknown"},
        }
        device_names = {
            "0000:82:00.0": {
                "Class": PCI_CLASS_PROCESSING_ACCEL,
                "Vendor": "Huawei Technologies Co., Ltd.",
                "Device": "Unknown accelerator XYZ",
            },
        }
        candidates = Huawei.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Huawei get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.huawei import Huawei

        device_ids = {
            "0000:82:00.1": {"Vendor": "19e5", "Class": "120000", "Device": "d802"},
        }
        device_names = {
            "0000:82:00.1": {
                "Class": PCI_CLASS_PROCESSING_ACCEL,
                "Vendor": "Huawei Technologies Co., Ltd.",
                "Device": "Device d802",
            },
        }
        candidates = Huawei.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestHaiguangGetPciOnlyCandidates(unittest.TestCase):
    """Test Haiguang get_pci_only_candidates."""

    def test_get_pci_only_candidates(self):
        """Haiguang get_pci_only_candidates returns 1d94 + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.haiguang import Haiguang

        device_ids = {"0000:18:00.0": {"Vendor": "1d94", "Class": "030200", "Device": "0010"}}
        device_names = {
            "0000:18:00.0": {"Class": "3D controller", "Vendor": "Haiguang", "Device": "DCU"},
        }
        candidates = Haiguang.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:18:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Haiguang get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.haiguang import Haiguang

        device_ids = {"0000:18:00.1": {"Vendor": "1d94", "Class": "030200", "Device": "0010"}}
        device_names = {"0000:18:00.1": {"Class": "3D controller", "Vendor": "Haiguang", "Device": "DCU"}}
        candidates = Haiguang.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestKunlunxinGetPciOnlyCandidates(unittest.TestCase):
    """Test Kunlunxin get_pci_only_candidates."""

    def test_get_pci_only_candidates(self):
        """Kunlunxin get_pci_only_candidates returns 2057 + Processing accelerators when slot is function 0."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        device_ids = {"0000:21:00.0": {"Vendor": "2057", "Class": "120000", "Device": "a000"}}
        device_names = {
            "0000:21:00.0": {
                "Class": PCI_CLASS_PROCESSING_ACCEL,
                "Vendor": "Kunlunxin",
                "Device": "XPU",
            },
        }
        candidates = Kunlunxin.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:21:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Kunlunxin get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        device_ids = {"0000:21:00.1": {"Vendor": "2057", "Class": "120000", "Device": "a000"}}
        device_names = {
            "0000:21:00.1": {"Class": PCI_CLASS_PROCESSING_ACCEL, "Vendor": "Kunlunxin", "Device": "XPU"},
        }
        candidates = Kunlunxin.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


XPU_SMI_SAMPLE_OUTPUT = """\
==============XPUSMI LOG==============

Timestamp                                 : Tue Feb  3 18:20:01 2026
Driver Version                            : 5.0.21.26
XPU-RT Version                            : 10.2

Attached XPUs                             : 2
XPU 00000000:01:00.0
    Product Name                          : P800 PCIe
    Product Brand                         : KUNLUNXIN
    Serial Number                         : 02K0MA0258D0007R
    PCI
        Bus Id                            : 00000000:01:00.0
    Memory Usage
        Total                             : 98304 MiB
        Used                              : 0 MiB
    Utilization
        Xpu                               : 0 %
    Temperature
        XPU Current Temp                  : 46 C
    Power Readings
        Enforced Power Limit              : 350.00 W
        Power Draw                        : 76.00 W
"""


class TestKunlunxinParseBasicInfo(unittest.TestCase):
    """Test Kunlunxin parse_basic_info (vendor plugin path) - ZSTAC-81958."""

    def test_parse_basic_info_extracts_product_name(self):
        """productName should appear in GPUInfo.extra after parsing xpu-smi output."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].extra.get("productName"), "P800 PCIe")

    def test_parse_basic_info_extracts_pci_address(self):
        """PCI address should be normalized."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(infos[0].pci_address, "0000:01:00.0")

    def test_parse_basic_info_extracts_memory(self):
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(infos[0].memory, "98304 MiB")

    def test_parse_basic_info_extracts_serial_number(self):
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(infos[0].serial_number, "02K0MA0258D0007R")

    def test_parse_basic_info_extracts_power(self):
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(infos[0].power, "350.00 W")

    def test_parse_basic_info_empty_output(self):
        """Empty output should return no GPUInfo."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        infos = Kunlunxin.parse_basic_info("")
        self.assertEqual(infos, [])

    def test_parse_basic_info_no_product_name(self):
        """If xpu-smi omits Product Name, extra should be empty dict."""
        from zstacklib.gpu.vendors.kunlunxin import Kunlunxin

        output = """\
XPU 00000000:02:00.0
    Serial Number                         : ABC123
    PCI
        Bus Id                            : 00000000:02:00.0
    Memory Usage
        Total                             : 32768 MiB
"""
        infos = Kunlunxin.parse_basic_info(output)
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].extra, {})


class TestKunlunxinLegacyParse(unittest.TestCase):
    """Test legacy parse_kunlunxin_gpu_output_by_npu_id (gpu.py path) - ZSTAC-81958."""

    def test_legacy_parse_extracts_product_name(self):
        """Legacy parser should put productName at top level of dict."""
        from zstacklib.utils.gpu import parse_kunlunxin_gpu_output_by_npu_id

        infos = parse_kunlunxin_gpu_output_by_npu_id(XPU_SMI_SAMPLE_OUTPUT)
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].get("productName"), "P800 PCIe")

    def test_legacy_parse_extracts_all_fields(self):
        """Legacy parser should extract pciAddress, memory, serialNumber, temperature, etc."""
        from zstacklib.utils.gpu import parse_kunlunxin_gpu_output_by_npu_id

        infos = parse_kunlunxin_gpu_output_by_npu_id(XPU_SMI_SAMPLE_OUTPUT)
        info = infos[0]
        self.assertEqual(info.get("pciAddress"), "0000:01:00.0")
        self.assertEqual(info.get("memory"), "98304 MiB")
        self.assertEqual(info.get("memoryUsage"), "0 MiB")
        self.assertEqual(info.get("serialNumber"), "02K0MA0258D0007R")
        self.assertEqual(info.get("temperature"), "46 C")
        self.assertEqual(info.get("power"), "350.00 W")
        self.assertEqual(info.get("powerDraw"), "76.00 W")
        self.assertEqual(info.get("xpuUtilization"), "0 %")

    def test_legacy_parse_no_product_name(self):
        """If output has no Product Name line, key should be absent."""
        from zstacklib.utils.gpu import parse_kunlunxin_gpu_output_by_npu_id

        output = """\
XPU 00000000:02:00.0
    Serial Number                         : XYZ
    PCI
        Bus Id                            : 00000000:02:00.0
"""
        infos = parse_kunlunxin_gpu_output_by_npu_id(output)
        self.assertNotIn("productName", infos[0])


class TestVastaiGetPciOnlyCandidates(unittest.TestCase):
    """Test Vastai get_pci_only_candidates."""

    def test_get_pci_only_candidates(self):
        """Vastai get_pci_only_candidates returns 1edb + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.vastai import Vastai

        device_ids = {"0000:17:00.0": {"Vendor": "1edb", "Class": "030200", "Device": "0001"}}
        device_names = {
            "0000:17:00.0": {"Class": "3D controller", "Vendor": "Vastai", "Device": "GPU"},
        }
        candidates = Vastai.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:17:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Vastai get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.vastai import Vastai

        device_ids = {"0000:17:00.1": {"Vendor": "1edb", "Class": "030200", "Device": "0001"}}
        device_names = {"0000:17:00.1": {"Class": "3D controller", "Vendor": "Vastai", "Device": "GPU"}}
        candidates = Vastai.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestEnflame(unittest.TestCase):
    """Test Enflame (燧原) vendor plugin; efsmi -q new driver uses Total Size."""

    def test_parse_basic_info_new_driver_total_size(self):
        """parse_basic_info accepts Total Size (new efsmi) and exact Dev key (not Device ID)."""
        from zstacklib.gpu.vendors.enflame import Enflame

        output = """
DEV ID 0
    Device Info
        Dev Name                : S60
        Dev SN                  : A0A1650510676
    PCIe Info
        Vendor ID               : 1e36
        Device ID               : c035
        Domain                  : 0000
        Bus                     : 17
        Dev                     : 00
        Func                    : 0
    Power Info
        Power Capa              : 300 W
    Device Mem Info
        Total Size              : 42976 MiB
"""
        infos = Enflame.parse_basic_info(output)
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].pci_address, "0000:17:00.0")
        self.assertEqual(infos[0].serial_number, "A0A1650510676")
        self.assertEqual(infos[0].memory, "42976 MiB")
        self.assertEqual(infos[0].power, "300 W")
        self.assertEqual(infos[0].device_name, "S60")

    def test_get_basic_info_cmd_uses_efsmi_q(self):
        """get_basic_info_cmd returns efsmi -q for new driver compatibility."""
        from zstacklib.gpu.vendors.enflame import Enflame

        self.assertEqual(Enflame.get_basic_info_cmd(), "efsmi -q")

    def test_get_pci_only_candidates(self):
        """Enflame get_pci_only_candidates returns 1e36 + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.enflame import Enflame

        device_ids = {"0000:17:00.0": {"Vendor": "1e36", "Class": "030200", "Device": "c035"}}
        device_names = {
            "0000:17:00.0": {"Class": "3D controller", "Vendor": "Enflame", "Device": "S60"},
        }
        candidates = Enflame.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:17:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Enflame get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.enflame import Enflame

        device_ids = {"0000:17:00.1": {"Vendor": "1e36", "Class": "030200", "Device": "c035"}}
        device_names = {"0000:17:00.1": {"Class": "3D controller", "Vendor": "Enflame", "Device": "S60"}}
        candidates = Enflame.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestEnflameMetrics(unittest.TestCase):
    """Test Enflame parse_metrics including powerCap in extra dict."""

    def test_parse_metrics_includes_power_cap(self):
        """parse_metrics should expose Power Capa as extra['powerCap'] for max power display."""
        from zstacklib.gpu.vendors.enflame import Enflame

        output = """
DEV ID 0
    Device Info
        Dev Name                : S60
        Dev SN                  : A0A1650510676
    PCIe Info
        Domain                  : 0000
        Bus                     : 17
        Dev                     : 00
        Func                    : 0
    Power Info
        Cur Power               : 102 W
        Power Capa              : 300 W
    Device Mem Info
        Total Size              : 42976 MiB
        Used Size               : 1024 MiB
    GCU Info
        GCU Temp                : 45 C
        GCU Usage               : 30 %
"""
        metrics = Enflame.parse_metrics(output)
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.pci_address, "0000:17:00.0")
        # power_draw should be current power (Cur Power)
        self.assertEqual(m.power_draw, 102.0)
        # temperature
        self.assertEqual(m.temperature, 45.0)
        # utilization
        self.assertEqual(m.utilization, 30.0)
        # powerCap should be in extra dict (max power for "最大功耗")
        self.assertIn("powerCap", m.extra)
        self.assertEqual(m.extra["powerCap"], 300.0)

    def test_parse_metrics_no_power_cap(self):
        """parse_metrics should handle missing Power Capa gracefully."""
        from zstacklib.gpu.vendors.enflame import Enflame

        output = """
DEV ID 0
    PCIe Info
        Domain                  : 0000
        Bus                     : 17
        Dev                     : 00
        Func                    : 0
    Power Info
        Cur Power               : 50 W
    GCU Info
        GCU Temp                : 38 C
"""
        metrics = Enflame.parse_metrics(output)
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.power_draw, 50.0)
        # No Power Capa in output, extra should be empty
        self.assertNotIn("powerCap", m.extra)


class TestTianshuGetPciOnlyCandidates(unittest.TestCase):
    """Test Tianshu get_pci_only_candidates."""

    def test_get_pci_only_candidates(self):
        """Tianshu get_pci_only_candidates returns 1e3e + 3D controller when slot is function 0."""
        from zstacklib.gpu.vendors.tianshu import Tianshu

        device_ids = {"0000:42:00.0": {"Vendor": "1e3e", "Class": "030200", "Device": "0001"}}
        device_names = {
            "0000:42:00.0": {"Class": "3D controller", "Vendor": "1e3e", "Device": "Tianshu GPU"},
        }
        candidates = Tianshu.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "0000:42:00.0")
        self.assertEqual(candidates[0][1], {"isDriverLoaded": False})

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Tianshu get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.tianshu import Tianshu

        device_ids = {"0000:42:00.1": {"Vendor": "1e3e", "Class": "030200", "Device": "0001"}}
        device_names = {"0000:42:00.1": {"Class": "3D controller", "Vendor": "1e3e", "Device": "Tianshu GPU"}}
        candidates = Tianshu.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestAlibabaGetPciOnlyCandidates(unittest.TestCase):
    """Test Alibaba get_pci_only_candidates with _deviceId."""

    def test_get_pci_only_candidates_returns_device_id(self):
        """Alibaba get_pci_only_candidates returns _deviceId from lspci device_ids."""
        from zstacklib.gpu.vendors.alibaba import Alibaba

        device_ids = {
            "0000:08:00.0": {"Vendor": "1ded", "Class": "030200", "Device": "6001"},
            "0000:09:00.0": {"Vendor": "1ded", "Class": "030200", "Device": "6001"},
        }
        device_names = {
            "0000:08:00.0": {"Class": "3D controller", "Vendor": "Alibaba", "Device": "PPU-ZW810E"},
            "0000:09:00.0": {"Class": "3D controller", "Vendor": "Alibaba", "Device": "PPU-ZW810E"},
        }
        candidates = Alibaba.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(len(candidates), 2)
        for normalized, info in candidates:
            self.assertFalse(info["isDriverLoaded"])
            self.assertEqual(info["_deviceId"], "6001")

    def test_get_pci_only_candidates_skips_non_function_0(self):
        """Alibaba get_pci_only_candidates returns only function 0 slots."""
        from zstacklib.gpu.vendors.alibaba import Alibaba

        device_ids = {"0000:08:00.1": {"Vendor": "1ded", "Class": "030200", "Device": "6001"}}
        device_names = {
            "0000:08:00.1": {"Class": "3D controller", "Vendor": "Alibaba", "Device": "PPU-ZW810E"},
        }
        candidates = Alibaba.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])

    def test_get_pci_only_candidates_skips_wrong_vendor(self):
        """Alibaba get_pci_only_candidates skips non-Alibaba vendors."""
        from zstacklib.gpu.vendors.alibaba import Alibaba

        device_ids = {"0000:08:00.0": {"Vendor": "10de", "Class": "030200", "Device": "1eb8"}}
        device_names = {
            "0000:08:00.0": {"Class": "3D controller", "Vendor": "NVIDIA", "Device": "T4"},
        }
        candidates = Alibaba.get_pci_only_candidates(device_ids, device_names)
        self.assertEqual(candidates, [])


class TestAlibabaEnrichAddonInfo(unittest.TestCase):
    """Test Alibaba enrich_addon_info with device_id-based productName propagation."""

    def _make_gpu_info_map(self):
        """Build a gpu_info_map simulating 3 ppu-smi visible + 2 PCI-only (passthrough'd) devices."""
        return {
            # ppu-smi visible devices (have memory/serial, no isDriverLoaded=False)
            "0000:08:00.0": {"memory": "32768 MiB", "serialNumber": "SN001", "_deviceId": "6001"},
            "0000:09:00.0": {"memory": "32768 MiB", "serialNumber": "SN002", "_deviceId": "6001"},
            "0000:0a:00.0": {"memory": "32768 MiB", "serialNumber": "SN003", "_deviceId": "6001"},
            # PCI-only candidates (passthrough'd, isDriverLoaded=False)
            "0000:0b:00.0": {"isDriverLoaded": False, "_deviceId": "6001", "_vendor": "Alibaba"},
            "0000:0c:00.0": {"isDriverLoaded": False, "_deviceId": "6001", "_vendor": "Alibaba"},
        }

    def test_propagates_product_name_to_pci_only_by_device_id(self):
        """enrich_addon_info propagates productName to PCI-only devices with matching device_id."""
        from zstacklib.gpu.vendors.alibaba import Alibaba
        try:
            from unittest.mock import patch
        except ImportError:
            from mock import patch

        gpu_info_map = self._make_gpu_info_map()
        all_pcis = list(gpu_info_map.keys())

        with patch("zstacklib.gpu.vendors.alibaba.bash_roe",
                   return_value=(0, "Product Name                          : PPU-ZW810E\n", "")):
            Alibaba.enrich_addon_info(gpu_info_map, all_pcis)

        # All 5 devices should have productName
        for pci_addr in all_pcis:
            self.assertEqual(gpu_info_map[pci_addr].get("productName"), "PPU-ZW810E",
                             "productName missing for %s" % pci_addr)

    def test_does_not_propagate_to_mismatched_device_id(self):
        """enrich_addon_info does NOT propagate productName if device_id doesn't match."""
        from zstacklib.gpu.vendors.alibaba import Alibaba
        try:
            from unittest.mock import patch
        except ImportError:
            from mock import patch

        gpu_info_map = {
            "0000:08:00.0": {"memory": "32768 MiB", "_deviceId": "6001"},
            # Different device_id — should NOT get productName
            "0000:0b:00.0": {"isDriverLoaded": False, "_deviceId": "7002", "_vendor": "Alibaba"},
        }
        all_pcis = list(gpu_info_map.keys())

        with patch("zstacklib.gpu.vendors.alibaba.bash_roe",
                   return_value=(0, "Product Name                          : PPU-ZW810E\n", "")):
            Alibaba.enrich_addon_info(gpu_info_map, all_pcis)

        self.assertEqual(gpu_info_map["0000:08:00.0"]["productName"], "PPU-ZW810E")
        self.assertNotIn("productName", gpu_info_map["0000:0b:00.0"])

    def test_no_propagation_when_ppu_smi_fails(self):
        """enrich_addon_info does nothing when ppu-smi command fails."""
        from zstacklib.gpu.vendors.alibaba import Alibaba
        try:
            from unittest.mock import patch
        except ImportError:
            from mock import patch

        gpu_info_map = self._make_gpu_info_map()
        all_pcis = list(gpu_info_map.keys())

        with patch("zstacklib.gpu.vendors.alibaba.bash_roe",
                   return_value=(1, "", "command not found")):
            Alibaba.enrich_addon_info(gpu_info_map, all_pcis)

        for pci_addr in all_pcis:
            self.assertNotIn("productName", gpu_info_map[pci_addr])


class TestEnrichGpuInfoMapPciOnlyInclusion(unittest.TestCase):
    """Test that enrich_gpu_info_map includes PCI-only candidates in vendor dispatch."""

    def test_pci_only_entries_dispatched_to_enrich_addon_info(self):
        """PCI-only entries with _vendor tag are passed to the vendor's enrich_addon_info."""
        try:
            from unittest.mock import patch, MagicMock
        except ImportError:
            from mock import patch, MagicMock

        from zstacklib.gpu import enrich_gpu_info_map, get_gpu_vendor

        gpu_info_map = {
            # PCI-only candidate with _vendor tag (no ppu-smi match)
            "0000:0b:00.0": {"isDriverLoaded": False, "_deviceId": "6001", "_vendor": "Alibaba"},
        }

        alibaba_cls = get_gpu_vendor("Alibaba")
        original_enrich = alibaba_cls.enrich_addon_info
        enrich_calls = []

        def mock_enrich(gmap, pcis):
            enrich_calls.append(pcis)

        with patch.object(alibaba_cls, 'enrich_addon_info', side_effect=mock_enrich):
            with patch.object(alibaba_cls, 'is_available', return_value=False):
                enrich_gpu_info_map(gpu_info_map)

        # enrich_addon_info should be called with the PCI-only address
        self.assertEqual(len(enrich_calls), 1)
        self.assertIn("0000:0b:00.0", enrich_calls[0])


class TestSupplementGpuInfoMapAnnotations(unittest.TestCase):
    """Test _supplement_gpu_info_map_from_pci annotates _vendor and _deviceId."""

    def test_pci_only_candidates_tagged_with_vendor_and_device_id(self):
        """PCI-only candidates from _supplement get _vendor and _deviceId tags."""
        try:
            from unittest.mock import patch
        except ImportError:
            from mock import patch

        from zstacklib.utils.gpu import _supplement_gpu_info_map_from_pci

        lspci_id_output = """Slot:\t0000:08:00.0
Class:\t030200
Vendor:\t1ded
Device:\t6001

Slot:\t0000:09:00.0
Class:\t030200
Vendor:\t1ded
Device:\t6001
"""
        lspci_name_output = """Slot:\t0000:08:00.0
Class:\t3D controller
Vendor:\tAlibaba
Device:\tPPU-ZW810E

Slot:\t0000:09:00.0
Class:\t3D controller
Vendor:\tAlibaba
Device:\tPPU-ZW810E
"""
        gpu_info_map = {}  # Empty — no ppu-smi entries

        with patch("zstacklib.utils.pci.get_pci_device_ids",
                   return_value=(0, lspci_id_output, "")), \
             patch("zstacklib.utils.pci.get_pci_device_names",
                   return_value=(0, lspci_name_output, "")):
            _supplement_gpu_info_map_from_pci(gpu_info_map)

        # Both PCI devices should be added with _vendor and _deviceId
        self.assertIn("0000:08:00.0", gpu_info_map)
        self.assertIn("0000:09:00.0", gpu_info_map)
        for pci_addr in ["0000:08:00.0", "0000:09:00.0"]:
            self.assertEqual(gpu_info_map[pci_addr]["_vendor"], "Alibaba")
            self.assertEqual(gpu_info_map[pci_addr]["_deviceId"], "6001")
            self.assertFalse(gpu_info_map[pci_addr]["isDriverLoaded"])

    def test_existing_entries_annotated_with_device_id(self):
        """Pre-existing gpu_info_map entries (from ppu-smi) get _deviceId from lspci."""
        try:
            from unittest.mock import patch
        except ImportError:
            from mock import patch

        from zstacklib.utils.gpu import _supplement_gpu_info_map_from_pci

        lspci_id_output = """Slot:\t0000:08:00.0
Class:\t030200
Vendor:\t1ded
Device:\t6001
"""
        lspci_name_output = """Slot:\t0000:08:00.0
Class:\t3D controller
Vendor:\tAlibaba
Device:\tPPU-ZW810E
"""
        # Pre-existing entry from ppu-smi (no _deviceId yet)
        gpu_info_map = {
            "0000:08:00.0": {"memory": "32768 MiB", "serialNumber": "SN001"},
        }

        with patch("zstacklib.utils.pci.get_pci_device_ids",
                   return_value=(0, lspci_id_output, "")), \
             patch("zstacklib.utils.pci.get_pci_device_names",
                   return_value=(0, lspci_name_output, "")):
            _supplement_gpu_info_map_from_pci(gpu_info_map)

        # Existing entry should NOT be replaced but should get _deviceId
        self.assertEqual(gpu_info_map["0000:08:00.0"]["memory"], "32768 MiB")
        self.assertEqual(gpu_info_map["0000:08:00.0"]["_deviceId"], "6001")


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

    def test_to_addon_dict_with_driver_not_loaded(self):
        """Test to_addon_dict with isDriverLoaded=False: reserved for real GPU info, driver not loaded (ZSTAC-81489).
        No-match/failure should return None, not this dict."""
        from zstacklib.gpu.base import GPUInfo

        info = GPUInfo(
            pci_address="0000:3b:00.0",
            memory="15360 MiB",
            power="70 W",
            serial_number="ABC123",
            driver_loaded=False,
        )
        addon = info.to_addon_dict()
        self.assertFalse(addon["isDriverLoaded"])
        self.assertEqual(addon["memory"], "15360 MiB")


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
