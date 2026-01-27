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


if __name__ == '__main__':
    unittest.main()
