from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsbDevice:
    """USB device information."""
    bus: str
    device: str
    vendor_id: str
    product_id: str
    description: str

    @property
    def device_id(self) -> str:
        """Device id."""
        return f"{self.vendor_id}:{self.product_id}"


@dataclass
class UsbAttachSpec:
    """Specification for attaching a USB device to a VM."""
    vm_id: str
    vendor_id: str
    product_id: str
    host_bus: str | None = None
    host_device: str | None = None
