from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional

from zstacklib.utils.bash import bash_roe
from zstacklib.utils.log import get_logger

from .address import PciError, fmt_pci_address, parse_pci_address

logger = get_logger(__name__)


@dataclass
class PciDevice:
    """PCI device information container."""

    address: str
    vendor_id: str
    device_id: str
    device_type: str
    iommu_group: Optional[str]
    driver: Optional[str]
    class_name: str = ""
    vendor_name: str = ""
    device_name: str = ""
    subvendor_id: str = ""
    subdevice_id: str = ""
    description: str = ""


def _simplify_vendor_name(name: str) -> str:
    """Simplify vendor name."""
    if "Intel Corporation" in name:
        return "Intel"
    if "Advanced Micro Devices" in name:
        return "AMD"
    if "NVIDIA Corporation" in name:
        return "NVIDIA"
    return name.replace("Co., Ltd ", "")


def _infer_device_type(description: str, class_name: str) -> str:
    """Infer device type."""
    gpu_vendors = ["NVIDIA", "AMD"]
    if any(vendor in description for vendor in gpu_vendors) and "VGA compatible controller" in class_name:
        return "GPU_Video_Controller"
    if any(vendor in description for vendor in gpu_vendors) and "Audio device" in class_name:
        return "GPU_Audio_Controller"
    if any(vendor in description for vendor in gpu_vendors) and "USB controller" in class_name:
        return "GPU_USB_Controller"
    if any(vendor in description for vendor in gpu_vendors) and "Serial bus controller" in class_name:
        return "GPU_Serial_Controller"
    if any(vendor in description for vendor in gpu_vendors) and "3D controller" in class_name:
        return "GPU_3D_Controller"
    if "Ethernet controller" in class_name:
        return "Ethernet_Controller"
    if "Audio device" in class_name:
        return "Audio_Controller"
    if "USB controller" in class_name:
        return "USB_Controller"
    if "Serial controller" in class_name:
        return "Serial_Controller"
    if "Moxa Technologies" in class_name:
        return "Moxa_Device"
    if "Host bridge" in class_name:
        return "Host_Bridge"
    if "PCI bridge" in class_name:
        return "PCI_Bridge"
    return "Generic"


def _normalize_address(address: str) -> str:
    """Normalize address."""
    domain, bus, slot, function = parse_pci_address(address)
    return fmt_pci_address({
        "domain": int(domain, 16),
        "bus": int(bus, 16),
        "slot": int(slot, 16),
        "function": int(function, 16),
    })


def get_iommu_group(address: str) -> Optional[str]:
    """Get IOMMU group for a PCI device.

    Args:
        address: PCI address string.

    Returns:
        Real path to iommu_group, or None if not available.
    """
    try:
        normalized = _normalize_address(address)
    except PciError:
        logger.debug("invalid pci address for iommu group: %s", address)
        return None

    group_path = os.path.join("/sys/bus/pci/devices", normalized, "iommu_group")
    if not os.path.exists(group_path):
        return None
    return os.path.realpath(group_path)


def _parse_lspci_output(output: str) -> List[PciDevice]:
    """Parse lspci output into PCI device list.

    Args:
        output: Output from lspci -Dmmnnv.

    Returns:
        List of PciDevice instances.
    """
    devices: List[PciDevice] = []
    for part in output.split("\n\n"):
        if not part.strip():
            continue
        address = ""
        vendor_id = ""
        device_id = ""
        subvendor_id = ""
        subdevice_id = ""
        class_name = ""
        vendor_name = ""
        device_name = ""
        description = ""
        driver = None

        for line in part.split("\n"):
            if len(line.split(":")) < 2:
                continue
            title, content = line.split(":", 1)
            title = title.strip()
            content = content.strip()
            if title == "Slot":
                address = content
            elif title == "Class":
                class_name = content.split("[")[0].strip()
                description = class_name + ": "
            elif title == "Vendor":
                vendor_name = _simplify_vendor_name("[".join(content.split("[")[:-1]).strip())
                vendor_id = content.split("[")[-1].strip("]")
                description += vendor_name + " "
            elif title == "Device":
                device_name = _simplify_vendor_name("[".join(content.split("[")[:-1]).strip())
                device_id = content.split("[")[-1].strip("]")
                description += device_name
            elif title == "SVendor":
                subvendor_id = content.split("[")[-1].strip("]")
            elif title == "SDevice":
                subdevice_id = content.split("[")[-1].strip("]")
            elif title == "Driver":
                driver = content

        if not address:
            continue
        device_type = _infer_device_type(description, class_name)
        iommu_group = get_iommu_group(address)

        devices.append(
            PciDevice(
                address=address,
                vendor_id=vendor_id,
                device_id=device_id,
                device_type=device_type,
                iommu_group=iommu_group,
                driver=driver,
                class_name=class_name,
                vendor_name=vendor_name,
                device_name=device_name,
                subvendor_id=subvendor_id,
                subdevice_id=subdevice_id,
                description=description,
            )
        )
    return devices


def scan_devices(vendor_id: str = None) -> List[PciDevice]:
    """Scan PCI devices on host.

    Args:
        vendor_id: Optional vendor id filter (hex string).

    Returns:
        List of PciDevice entries.

    Raises:
        PciError: When lspci fails.
    """
    r, o, e = bash_roe("lspci -Dmmnnv")
    if r != 0:
        raise PciError("failed to run lspci: %s, %s" % (e, o))

    devices = _parse_lspci_output(o)
    if vendor_id is None:
        return devices
    target = vendor_id.strip().lower()
    return [device for device in devices if device.vendor_id.lower() == target]


def get_device(address: str) -> Optional[PciDevice]:
    """Get a single PCI device by address.

    Args:
        address: PCI address string.

    Returns:
        PciDevice if found, otherwise None.
    """
    try:
        normalized = _normalize_address(address)
    except PciError:
        return None

    for device in scan_devices():
        try:
            if _normalize_address(device.address) == normalized:
                return device
        except PciError:
            continue
    return None
