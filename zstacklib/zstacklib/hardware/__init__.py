"""Hardware management modules for ZStack.

This package provides unified APIs for hardware management:
- pci: PCI device discovery, addressing, and VFIO passthrough
- gpu: GPU/vGPU management with vendor-specific adapters (NVIDIA, AMD, Intel)
- sriov: SR-IOV Physical/Virtual Function management
- usb: USB device management (planned)

Submodules are lazily imported to avoid loading heavy dependencies at import time.
"""

from __future__ import annotations


def __getattr__(name: str):
    """Lazy import submodules on first access."""
    if name == "pci":
        from . import pci as _pci
        return _pci
    elif name == "gpu":
        from . import gpu as _gpu
        return _gpu
    elif name == "sriov":
        from . import sriov as _sriov
        return _sriov
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "pci",
    "gpu",
    "sriov",
]
