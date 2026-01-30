#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for PCI utility functions

Tests cover:
- PCI address normalization
- Vendor name simplification
"""

from zstacklib.utils import pci
import unittest


class TestPCINormalization(unittest.TestCase):
    """Test PCI address normalization functions"""

    def test_normalize_pci_address_8char_domain(self):
        """Test PCI address normalization with 8-char domain"""
        addr = "00000000:3b:00.0"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:3b:00.0")

    def test_normalize_pci_address_4char_domain(self):
        """Test PCI address normalization with 4-char domain"""
        addr = "0000:3b:00.0"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:3b:00.0")

    def test_normalize_pci_address_uppercase(self):
        """Test PCI address normalization with uppercase"""
        addr = "0000:3B:00.0"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:3b:00.0")

    def test_normalize_pci_address_without_domain(self):
        """Test PCI address normalization without domain"""
        addr = "3b:00.0"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:3b:00.0")

    def test_normalize_pci_address_invalid(self):
        """Test PCI address normalization with invalid format"""
        self.assertIsNone(pci.normalize_pci_address("invalid"))
        self.assertIsNone(pci.normalize_pci_address(""))
        self.assertIsNone(pci.normalize_pci_address(None))

    def test_normalize_pci_address_function_0(self):
        """Test PCI address normalization with function 0"""
        addr = "0000:34:00.0"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:34:00.0")

    def test_normalize_pci_address_function_1(self):
        """Test PCI address normalization with function 1"""
        addr = "0000:34:00.1"
        normalized = pci.normalize_pci_address(addr)
        self.assertEqual(normalized, "0000:34:00.1")
        # Function 1 should be normalized correctly but should NOT match function 0
        self.assertNotEqual(normalized, "0000:34:00.0")


class TestVendorNameSimplification(unittest.TestCase):
    """Test vendor name simplification functions"""

    def test_simplify_vendor_name_nvidia(self):
        """Test NVIDIA vendor name simplification"""
        result = pci.simplify_vendor_name("NVIDIA Corporation", None)
        self.assertEqual(result, "NVIDIA")

    def test_simplify_vendor_name_amd(self):
        """Test AMD vendor name simplification"""
        result = pci.simplify_vendor_name("Advanced Micro Devices", None)
        self.assertEqual(result, "AMD")

    def test_simplify_vendor_name_intel(self):
        """Test Intel vendor name simplification"""
        result = pci.simplify_vendor_name("Intel Corporation", None)
        self.assertEqual(result, "Intel")

    def test_simplify_vendor_name_with_vendor_id(self):
        """Test vendor name simplification with vendor ID fallback"""
        # Test Alibaba vendor ID
        result = pci.simplify_vendor_name("Unknown Vendor", "1ded")
        self.assertEqual(result, "Alibaba")

    def test_simplify_vendor_name_unknown(self):
        """Test vendor name simplification for unknown vendor"""
        result = pci.simplify_vendor_name("Some Co., Ltd Vendor", None)
        # Should clean common suffixes
        self.assertNotIn("Co., Ltd", result)


class TestPciDeviceProbeContext(unittest.TestCase):
    """Test pci_device_probe passes context to ops.probe (ZSTAC-81489)"""

    def test_probe_receives_context(self):
        """Probe function is called with (pci_device_to, context) so matcher can use gpu_info_map"""
        from zstacklib.utils import pci

        probe_calls = []

        def my_probe(pci_device_to, context):
            probe_calls.append((pci_device_to, context))
            return False

        class MockTO(object):
            pciDeviceAddress = "0000:3b:00.0"

        class MockContext(object):
            gpu_info_map = {}

        ops = pci.PciDeviceOps(probe=my_probe, init=lambda to, ctx: False)
        try:
            pci.pci_register_device_ops(ops)
            pci.pci_device_probe(MockTO(), MockContext())
            self.assertEqual(len(probe_calls), 1)
            self.assertIs(probe_calls[0][1].gpu_info_map, MockContext.gpu_info_map)
        finally:
            pci._pci_device_ops_list.remove(ops)


if __name__ == '__main__':
    unittest.main()
