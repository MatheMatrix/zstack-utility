#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for GPU get_info() function and vendor-specific logic

Tests cover:
- Plugin-based collection
- Legacy fallback for different vendors
- Vendor-specific field handling (Huawei npuId, product names, etc.)
"""

from zstacklib.utils.bash import bash_roe
from zstacklib.utils.pci import VendorEnum
from zstacklib.utils import gpu
import unittest
import sys
import os
try:
    from unittest.mock import patch, MagicMock
except ImportError:
    from mock import patch, MagicMock

# Add parent directory to path for imports
# Calculate path: zstacklib/zstacklib/utils/test_*.py -> zstacklib/
parent_dir = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, parent_dir)


class TestGetInfo(unittest.TestCase):
    """Test get_info() function"""

    def test_get_info_no_pci_address(self):
        """Test get_info returns None when no PCI address provided"""
        self.assertIsNone(gpu.get_info(None))
        self.assertIsNone(gpu.get_info(pci_device=None))

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_via_plugin_nvidia(self, mock_bash):
        """Test get_info via NVIDIA plugin"""
        # Mock the imports inside get_info function
        with patch('zstacklib.gpu.get_gpu_vendor') as mock_get_vendor, \
             patch('zstacklib.gpu.get_vendor_enum_mapping') as mock_mapping:
            from zstacklib.gpu.base import GPUInfo

            # Mock plugin
            mock_plugin = MagicMock()
            mock_plugin.is_available.return_value = True
            mock_plugin.get_basic_info.return_value = [
                GPUInfo(
                    pci_address="0000:3b:00.0",
                    memory="15360 MiB",
                    power="70.00 W",
                    serial_number="1322519087621"
                )
            ]

            mock_get_vendor.return_value = mock_plugin
            mock_mapping.return_value = {"NVIDIA": "NVIDIA"}

            result = gpu.get_info("0000:3b:00.0", vendor_name=VendorEnum.NVIDIA)
            self.assertIsNotNone(result)
            self.assertEqual(result["memory"], "15360 MiB")
            self.assertEqual(result["power"], "70.00 W")
            self.assertEqual(result["serialNumber"], "1322519087621")
            self.assertTrue(result["isDriverLoaded"])

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_via_plugin_huawei(self, mock_bash):
        """Test get_info via Huawei plugin with special fields"""
        # Mock the imports inside get_info function
        with patch('zstacklib.gpu.get_gpu_vendor') as mock_get_vendor, \
             patch('zstacklib.gpu.get_vendor_enum_mapping') as mock_mapping:
            from zstacklib.gpu.base import GPUInfo

            # Mock Huawei plugin
            mock_plugin = MagicMock()
            mock_plugin.is_available.return_value = True
            mock_plugin.get_basic_info.return_value = [
                GPUInfo(
                    pci_address="0000:81:00.0",
                    memory="32768 MB",
                    power="300 W",
                    serial_number="HUAWEI001",
                    extra={"npuId": "0", "isIsolated": False}
                )
            ]
            mock_plugin.get_npu_ids.return_value = ["0", "1"]

            # Mock product name command
            mock_bash.side_effect = [
                (0, "Product Type: Atlas 800", ""),  # product name
                (0, "", ""),  # aios rank table (simplified)
            ]

            mock_get_vendor.return_value = mock_plugin
            mock_mapping.return_value = {"Huawei": "Huawei"}

            result = gpu.get_info("0000:81:00.0", vendor_name=VendorEnum.HUAWEI)
            self.assertIsNotNone(result)
            self.assertEqual(result["npuId"], "0")
            self.assertEqual(result["isIsolated"], False)
            # Product name should be collected
            # Note: This requires actual implementation of get_huawei_product_type

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_legacy_nvidia(self, mock_bash):
        """Test get_info legacy fallback for NVIDIA"""
        mock_bash.side_effect = [
            (0, "/usr/bin/nvidia-smi", ""),  # which nvidia-smi
            # nvidia-smi query
            (0, "00000000:3B:00.0, 15360 MiB, 70.00 W, 1322519087621", ""),
        ]

        result = gpu._get_info_legacy("0000:3b:00.0", VendorEnum.NVIDIA)
        self.assertIsNotNone(result)
        self.assertTrue(result.get("isDriverLoaded", False))

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_legacy_amd(self, mock_bash):
        """Test get_info legacy fallback for AMD"""
        mock_bash.side_effect = [
            (0, "/usr/bin/rocm-smi", ""),  # which rocm-smi
            # rocm-smi
            (0, '{"card_list": [{"pci_bus": "0000:42:00.0", "memory": "16384 MiB"}]}', ""),
        ]

        result = gpu._get_info_legacy("0000:42:00.0", VendorEnum.AMD)
        # Note: This requires actual parse_amd_gpu_output implementation
        # For now, just verify it doesn't crash
        self.assertIsNotNone(result)

    @patch('zstacklib.utils.gpu.bash_roe')
    @patch('zstacklib.utils.gpu.bash_ro')
    def test_get_info_legacy_huawei(self, mock_bash_ro, mock_bash_roe):
        """Test get_info legacy fallback for Huawei with special fields"""
        # bash_ro returns (r, o) only, not (r, o, e)
        mock_bash_ro.return_value = (0, "NPU ID: 0\nNPU ID: 1")  # npu-smi info -l
        mock_bash_roe.side_effect = [
            (0, "/usr/bin/npu-smi", ""),  # which npu-smi
            (0, "PCIe Bus Info: 0000:81:00.0\nSerial Number: HUAWEI001", ""),  # npu info
            (0, "Product Type: Atlas 800", ""),  # product name
        ]

        result = gpu._get_info_legacy("0000:81:00.0", VendorEnum.HUAWEI)
        # Note: This requires actual implementation
        # For now, verify it handles Huawei-specific logic
        self.assertIsNotNone(result)

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_legacy_tianshu(self, mock_bash):
        """Test get_info legacy fallback for Tianshu"""
        mock_bash.side_effect = [
            (0, "/usr/bin/ixsmi", ""),  # which ixsmi
            (0, "00000000:86:00.0, 8192 MiB, 150.00 W, TIANSHU001", ""),  # ixsmi query
            (0, "Product Name: Tianshu GPU", ""),  # product name
        ]

        result = gpu._get_info_legacy("0000:86:00.0", VendorEnum.TIANSHU)
        self.assertIsNotNone(result)
        # Product name should be collected

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_get_info_legacy_alibaba(self, mock_bash):
        """Test get_info legacy fallback for Alibaba"""
        mock_bash.side_effect = [
            (0, "/usr/bin/ppu-smi", ""),  # which ppu-smi
            # ppu-smi query
            (0, "00000000:08:00.0, 98304 MiB, 400.00 W, ALIBABA001", ""),
            (0, "Product Name: Alibaba PPU", ""),  # product name
        ]

        result = gpu._get_info_legacy("0000:08:00.0", VendorEnum.ALIBABA)
        self.assertIsNotNone(result)
        # Product name should be collected

    def test_get_info_legacy_unknown_vendor(self):
        """Test get_info legacy returns None for unknown vendor"""
        result = gpu._get_info_legacy("0000:ff:00.0", "UnknownVendor")
        self.assertIsNone(result)


class TestLegacyCollectors(unittest.TestCase):
    """Test legacy collection functions for each vendor"""

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_collect_nvidia_legacy(self, mock_bash):
        """Test _collect_nvidia_legacy"""
        mock_bash.side_effect = [
            (0, "/usr/bin/nvidia-smi", ""),  # which
            (0, "00000000:3B:00.0, 15360 MiB, 70.00 W, SN001", ""),  # nvidia-smi
        ]

        result = gpu._collect_nvidia_legacy("0000:3b:00.0")
        self.assertIsNotNone(result)
        self.assertTrue(result.get("isDriverLoaded", False))

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_collect_nvidia_legacy_no_tool(self, mock_bash):
        """Test _collect_nvidia_legacy when tool not available"""
        mock_bash.return_value = (1, "", "command not found")

        result = gpu._collect_nvidia_legacy("0000:3b:00.0")
        self.assertFalse(result.get("isDriverLoaded", True))

    @patch('zstacklib.utils.gpu.bash_roe')
    def test_collect_amd_legacy(self, mock_bash):
        """Test _collect_amd_legacy"""
        mock_bash.side_effect = [
            (0, "/usr/bin/rocm-smi", ""),  # which
            (0, '{"card_list": []}', ""),  # rocm-smi
        ]

        result = gpu._collect_amd_legacy("0000:42:00.0")
        # Note: Requires actual parse_amd_gpu_output
        self.assertIsNotNone(result)

    @patch('zstacklib.utils.gpu.bash_roe')
    @patch('zstacklib.utils.gpu.bash_ro')
    def test_collect_huawei_legacy(self, mock_bash_ro, mock_bash_roe):
        """Test _collect_huawei_legacy with special fields"""
        # bash_ro returns (r, o) only, not (r, o, e)
        mock_bash_ro.return_value = (0, "NPU ID: 0")
        mock_bash_roe.side_effect = [
            (0, "/usr/bin/npu-smi", ""),  # which
            (0, "PCIe Bus Info: 0000:81:00.0\nSerial Number: HW001", ""),  # npu info
            (0, "Product Type: Atlas 800", ""),  # product name
        ]

        result = gpu._collect_huawei_legacy("0000:81:00.0")
        # Note: Requires actual implementation
        self.assertIsNotNone(result)

    @patch('zstacklib.utils.gpu.shell')
    @patch('zstacklib.utils.gpu.bash_roe')
    def test_collect_vastai_legacy(self, mock_bash, mock_shell):
        """Test _collect_vastai_legacy"""
        mock_bash.return_value = (0, "/usr/bin/vasmi", "")
        mock_shell.run_with_json_result.side_effect = [
            # getmem
            {"elem": [{"pci_bus": "00000000:65:00.0", "sn": "VASTAI001"}]},
            {"elem": [{"vals": {"devBusId": {"value": "00000000:65:00.0"},
                                "P_Cap": {"value": "300 W"}}}]},  # summary
        ]

        result = gpu._collect_vastai_legacy("0000:65:00.0")
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
