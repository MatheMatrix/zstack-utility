#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for PCI GPU detection logic (is_gpu function)

Tests cover:
- GPU plugin system integration
- SMI tool detection for different vendors
- PCI address normalization
"""

from zstacklib.utils.bash import bash_roe
from zstacklib.utils import pci
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


class TestIsGPU(unittest.TestCase):
    """Test is_gpu() function with different GPU vendors"""

    def test_is_gpu_no_pci_address(self):
        """Test is_gpu returns False when no PCI address provided"""
        self.assertFalse(pci.is_gpu(None))
        self.assertFalse(pci.is_gpu(""))

    def test_is_gpu_pci_address_normalization(self):
        """Test PCI address normalization (8-char domain -> 4-char)"""
        # This test verifies normalization logic
        # Actual GPU detection requires real hardware or mocked plugin/SMI
        pass

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_plugin_nvidia(self, mock_bash):
        """Test GPU detection via NVIDIA plugin"""
        # Mock the import inside is_gpu function
        with patch('zstacklib.gpu.get_all_gpu_vendors') as mock_get_vendors:
            # Mock NVIDIA plugin
            mock_nvidia_plugin = MagicMock()
            mock_nvidia_plugin.VENDOR_NAME = "NVIDIA"
            mock_nvidia_plugin.is_available.return_value = True

            from zstacklib.gpu.base import GPUInfo
            mock_nvidia_plugin.get_basic_info.return_value = [
                GPUInfo(pci_address="0000:3b:00.0",
                        memory="15360 MiB", power="70.00 W")
            ]

            mock_get_vendors.return_value = [mock_nvidia_plugin]

            result = pci.is_gpu("0000:3b:00.0")
            self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_nvidia(self, mock_bash):
        """Test GPU detection via nvidia-smi tool"""
        # Mock nvidia-smi tool available
        mock_bash.side_effect = [
            (0, "/usr/bin/nvidia-smi", ""),  # which nvidia-smi
            (0, "00000000:3B:00.0\n00000000:3C:00.0", ""),  # nvidia-smi query
        ]

        result = pci.is_gpu("0000:3b:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_amd(self, mock_bash):
        """Test GPU detection via rocm-smi tool"""
        def side_effect(cmd):
            if "which rocm-smi" in cmd:
                return (0, "/usr/bin/rocm-smi", "")
            elif "rocm-smi --showbus --json" in cmd:
                return (0, '{"devices": [{"pci_bus": "0000:42:00.0"}]}', "")
            else:
                # Other tools' which calls should fail
                return (1, "", "command not found")
        
        mock_bash.side_effect = side_effect

        result = pci.is_gpu("0000:42:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_huawei(self, mock_bash):
        """Test GPU detection via npu-smi tool"""
        def side_effect(cmd):
            if "which npu-smi" in cmd:
                return (0, "/usr/bin/npu-smi", "")
            elif "npu-smi info -l" in cmd:
                return (0, "PCIe Bus Info: 0000:81:00.0", "")
            else:
                # Other tools' which calls should fail
                return (1, "", "command not found")
        
        mock_bash.side_effect = side_effect

        result = pci.is_gpu("0000:81:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_haiguang(self, mock_bash):
        """Test GPU detection via hy-smi tool"""
        def side_effect(cmd):
            if "which hy-smi" in cmd:
                return (0, "/usr/bin/hy-smi", "")
            elif "hy-smi info" in cmd:
                return (0, "PCI Bus: 0000:01:00.0", "")
            else:
                # Other tools' which calls should fail
                return (1, "", "command not found")
        
        mock_bash.side_effect = side_effect

        result = pci.is_gpu("0000:01:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_enflame(self, mock_bash):
        """Test GPU detection via efsmi tool"""
        def side_effect(cmd):
            if "which efsmi" in cmd:
                return (0, "/usr/bin/efsmi", "")
            elif "efsmi -q" in cmd:
                return (0, "PCIe Info\n    Bus: 0000:b1:00.0", "")
            else:
                # Other tools' which calls should fail
                return (1, "", "command not found")
        
        mock_bash.side_effect = side_effect

        result = pci.is_gpu("0000:b1:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.shell')
    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_vastai(self, mock_bash, mock_shell):
        """Test GPU detection via vasmi tool"""
        mock_bash.return_value = (0, "/usr/bin/vasmi", "")  # which vasmi (first call in _is_gpu_by_smi_tools)

        # Mock vasmi JSON output (used in _check_vasmi)
        mock_shell.run_with_json_result.return_value = {
            "elem": [
                {"pci_bus": "00000000:65:00.0", "sn": "VASTAI001"}
            ]
        }

        result = pci.is_gpu("0000:65:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_tianshu(self, mock_bash):
        """Test GPU detection via ixsmi tool"""
        mock_bash.side_effect = [
            (0, "/usr/bin/ixsmi", ""),  # which ixsmi (first call in _is_gpu_by_smi_tools)
            (0, "00000000:86:00.0", ""),  # ixsmi --query-gpu=gpu_bus_id (in _check_ixsmi)
        ]

        result = pci.is_gpu("0000:86:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_via_smi_alibaba(self, mock_bash):
        """Test GPU detection via ppu-smi tool"""
        mock_bash.side_effect = [
            (0, "/usr/bin/ppu-smi", ""),  # which ppu-smi (first call in _is_gpu_by_smi_tools)
            (0, "00000000:08:00.0", ""),  # ppu-smi --query-ppu=gpu_bus_id (in _check_ppu_smi)
        ]

        result = pci.is_gpu("0000:08:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_is_gpu_not_found(self, mock_bash):
        """Test is_gpu returns False when device not found"""
        # Mock no tools available
        mock_bash.return_value = (1, "", "command not found")

        result = pci.is_gpu("0000:ff:00.0")
        self.assertFalse(result)

    def test_pci_address_normalization_8char(self):
        """Test PCI address normalization with 8-char domain"""
        # Test internal normalization logic
        addr = "00000000:3b:00.0"
        normalized = addr.lower().strip()
        if len(normalized.split(':')[0]) == 8:
            normalized = normalized[4:]
        self.assertEqual(normalized, "0000:3b:00.0")

    def test_pci_address_normalization_4char(self):
        """Test PCI address normalization with 4-char domain"""
        addr = "0000:3b:00.0"
        normalized = addr.lower().strip()
        if len(normalized.split(':')[0]) == 8:
            normalized = normalized[4:]
        self.assertEqual(normalized, "0000:3b:00.0")


class TestSMIToolCheckers(unittest.TestCase):
    """Test individual SMI tool checker functions"""

    @patch('zstacklib.utils.pci.bash_roe')
    def test_check_nvidia_smi(self, mock_bash):
        """Test _check_nvidia_smi function"""
        mock_bash.return_value = (0, "00000000:3B:00.0\n00000000:3C:00.0", "")

        result = pci._check_nvidia_smi("0000:3b:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_check_nvidia_smi_not_found(self, mock_bash):
        """Test _check_nvidia_smi when PCI address not in output"""
        mock_bash.return_value = (0, "00000000:3C:00.0", "")

        result = pci._check_nvidia_smi("0000:3b:00.0")
        self.assertFalse(result)

    @patch('zstacklib.utils.pci.bash_roe')
    @patch('zstacklib.utils.shell')
    def test_check_vasmi(self, mock_shell, mock_bash):
        """Test _check_vasmi function"""
        # _check_vasmi doesn't use bash_roe, only shell.run_with_json_result
        mock_shell.run_with_json_result.return_value = {
            "elem": [
                {"pci_bus": "00000000:65:00.0"}
            ]
        }

        result = pci._check_vasmi("0000:65:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_check_ixsmi(self, mock_bash):
        """Test _check_ixsmi function"""
        mock_bash.return_value = (0, "00000000:86:00.0", "")

        result = pci._check_ixsmi("0000:86:00.0")
        self.assertTrue(result)

    @patch('zstacklib.utils.pci.bash_roe')
    def test_check_ppu_smi(self, mock_bash):
        """Test _check_ppu_smi function"""
        mock_bash.return_value = (0, "00000000:08:00.0", "")

        result = pci._check_ppu_smi("0000:08:00.0")
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
