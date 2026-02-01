"""Hardware management modules for ZStack.

This package provides unified APIs for hardware management:
- pci: PCI device discovery, addressing, and VFIO passthrough
- gpu: GPU/vGPU management with vendor-specific adapters (NVIDIA, AMD, Intel)
- sriov: SR-IOV Physical/Virtual Function management
- usb: USB device management (planned)
"""

from . import gpu, pci, sriov

__all__ = [
    "pci",
    "gpu",
    "sriov",
]
