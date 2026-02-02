from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsbDevice:
    bus: str
    device: str
    vendor_id: str
    product_id: str
    description: str

    @property
    def device_id(self) -> str:
        return f"{self.vendor_id}:{self.product_id}"


@dataclass
class UsbAttachSpec:
    vm_id: str
    vendor_id: str
    product_id: str
    host_bus: str | None = None
    host_device: str | None = None
