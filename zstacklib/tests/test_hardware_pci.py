"""Tests for hardware.pci module."""

import pytest

from zstacklib.hardware.pci.address import (
    PciError,
    fmt_pci_address,
    parse_pci_address,
)


class TestFmtPciAddress:
    def test_format_full_address(self):
        pci_device = {
            "domain": 0,
            "bus": 0x1f,
            "slot": 0x00,
            "function": 0,
        }
        result = fmt_pci_address(pci_device)
        assert result == "0000:1f:00.0"

    def test_format_with_string_values(self):
        pci_device = {
            "domain": "0",
            "bus": "1f",
            "slot": "00",
            "function": "0",
        }
        result = fmt_pci_address(pci_device)
        assert result == "0000:1f:00.0"

    def test_format_with_hex_prefix(self):
        pci_device = {
            "domain": "0x0000",
            "bus": "0x1f",
            "slot": "0x00",
            "function": "0",
        }
        result = fmt_pci_address(pci_device)
        assert result == "0000:1f:00.0"

    def test_format_without_domain(self):
        pci_device = {
            "bus": 0x00,
            "slot": 0x1a,
            "function": 3,
        }
        result = fmt_pci_address(pci_device)
        assert result == "0000:00:1a.3"

    def test_format_missing_bus_raises(self):
        pci_device = {"slot": 0, "function": 0}
        with pytest.raises(PciError, match="missing pci address field"):
            fmt_pci_address(pci_device)

    def test_format_invalid_value_raises(self):
        pci_device = {"bus": "invalid", "slot": 0, "function": 0}
        with pytest.raises(PciError, match="invalid pci address field"):
            fmt_pci_address(pci_device)


class TestParsePciAddress:
    def test_parse_full_address(self):
        domain, bus, slot, function = parse_pci_address("0000:1f:00.0")
        assert domain == "0000"
        assert bus == "1f"
        assert slot == "00"
        assert function == "0"

    def test_parse_uppercase(self):
        domain, bus, slot, function = parse_pci_address("0000:1F:0A.7")
        assert domain == "0000"
        assert bus == "1f"
        assert slot == "0a"
        assert function == "7"

    def test_parse_without_domain(self):
        domain, bus, slot, function = parse_pci_address("1f:00.0")
        assert domain == "0000"
        assert bus == "1f"
        assert slot == "00"
        assert function == "0"

    def test_parse_with_whitespace(self):
        domain, bus, _, _ = parse_pci_address("  0000:1f:00.0  ")
        assert domain == "0000"
        assert bus == "1f"

    def test_parse_invalid_format_raises(self):
        with pytest.raises(PciError, match="invalid pci address"):
            parse_pci_address("invalid")

    def test_parse_empty_raises(self):
        with pytest.raises(PciError, match="invalid pci address"):
            parse_pci_address("")

    def test_parse_invalid_function_raises(self):
        with pytest.raises(PciError, match="invalid pci address"):
            parse_pci_address("0000:1f:00.8")


class TestPciAddressRoundTrip:
    def test_roundtrip_format_then_parse(self):
        original = {"domain": 0, "bus": 0x1f, "slot": 0x0a, "function": 3}
        formatted = fmt_pci_address(original)
        domain, bus, slot, function = parse_pci_address(formatted)
        assert domain == "0000"
        assert bus == "1f"
        assert slot == "0a"
        assert function == "3"
