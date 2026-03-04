
import re
from typing import Dict, Tuple, Union

from zstacklib.utils.log import get_logger

logger = get_logger(__name__)

PCI_ADDRESS_PATTERN = re.compile(
    r"^(?:(?P<domain>[0-9a-fA-F]{4}):)?(?P<bus>[0-9a-fA-F]{2})"
    r":(?P<slot>[0-9a-fA-F]{2})\.(?P<function>[0-7])$"
)


class PciError(Exception):
    """Base exception for PCI address errors."""
    pass


def _to_int(value: Union[str, int, None]) -> int:
    """Convert a string or int to int, treating hex-like strings as base-16."""
    if isinstance(value, int):
        return value
    if value is None:
        raise PciError("pci address component is None")
    value_str = str(value).strip()
    if value_str.lower().startswith("0x"):
        return int(value_str, 16)
    if re.fullmatch(r"[0-9a-fA-F]+", value_str) and not value_str.isdigit():
        return int(value_str, 16)
    return int(value_str, 10)


def fmt_pci_address(pci_device: Dict[str, Union[str, int]]) -> str:
    """Format PCI address from dict.

    Args:
        pci_device: Dict with domain/bus/slot/function keys.

    Returns:
        PCI address string like "0000:00:1f.0".

    Raises:
        PciError: When pci_device is missing required fields.
    """
    try:
        domain = _to_int(pci_device.get("domain", 0))
        bus = _to_int(pci_device["bus"])
        slot = _to_int(pci_device["slot"])
        function = _to_int(pci_device["function"])
    except KeyError as exc:
        raise PciError("missing pci address field: %s" % exc)
    except (TypeError, ValueError) as exc:
        raise PciError("invalid pci address field: %s" % exc)

    return "%s:%s:%s.%s" % (
        format(domain, "04x"),
        format(bus, "02x"),
        format(slot, "02x"),
        format(function, "x"),
    )


def parse_pci_address(addr: str) -> Tuple[str, str, str, str]:
    """Parse PCI device address into components.

    Args:
        addr: PCI address string (with or without domain).

    Returns:
        Tuple of (domain, bus, slot, function) as hex strings.

    Raises:
        PciError: When the address format is invalid.
    """
    match = PCI_ADDRESS_PATTERN.match(addr.strip())
    if not match:
        raise PciError("invalid pci address: %s" % addr)

    domain = match.group("domain") or "0000"
    return domain.lower(), match.group("bus").lower(), match.group("slot").lower(), match.group("function").lower()
