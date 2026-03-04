from __future__ import annotations

# Models and pure functions (no external dependencies) - import immediately
from .address import PCI_ADDRESS_PATTERN, PciError, fmt_pci_address, parse_pci_address


def __getattr__(name: str):
    """Lazy import functions that depend on external modules."""
    _device_exports = {
        "PciDevice", "get_device", "get_iommu_group", "scan_devices"
    }
    _passthrough_exports = {
        "bind_device_to_vfio", "create_iommu_unsafe_interrupts_conf",
        "enable_iommu_in_grub", "get_iommu_type", "is_iommu_enabled",
        "load_vfio_modules", "unbind_device_from_vfio"
    }

    if name in _device_exports:
        from . import device
        val = getattr(device, name)
        globals()[name] = val
        return val
    elif name in _passthrough_exports:
        from . import passthrough
        val = getattr(passthrough, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PCI_ADDRESS_PATTERN",
    "PciError",
    "fmt_pci_address",
    "parse_pci_address",
    "PciDevice",
    "get_device",
    "get_iommu_group",
    "scan_devices",
    "bind_device_to_vfio",
    "create_iommu_unsafe_interrupts_conf",
    "enable_iommu_in_grub",
    "get_iommu_type",
    "is_iommu_enabled",
    "load_vfio_modules",
    "unbind_device_from_vfio",
]
