from __future__ import annotations

import os
import re
import subprocess
import tempfile

from .exceptions import UsbNotFoundError, UsbOperationError
from .models import UsbAttachSpec, UsbDevice


def _usb_device_xml(vendor_id: str, product_id: str, bus: str, dev: str) -> str:
    return (
        "<hostdev mode='subsystem' type='usb' managed='yes'>\n"
        "  <source>\n"
        "    <vendor id='0x{vendor_id}'/>\n"
        "    <product id='0x{product_id}'/>\n"
        "    <address bus='{bus}' device='{dev}'/>\n"
        "  </source>\n"
        "</hostdev>\n"
    ).format(vendor_id=vendor_id, product_id=product_id, bus=bus, dev=dev)


USB_RE = re.compile(r"^Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.+)$")


def _parse_lsusb(output: str) -> list[UsbDevice]:
    devices: list[UsbDevice] = []
    for line in output.splitlines():
        match = USB_RE.match(line.strip())
        if not match:
            continue
        bus, device, vendor_id, product_id, desc = match.groups()
        devices.append(
            UsbDevice(
                bus=bus,
                device=device,
                vendor_id=vendor_id.lower(),
                product_id=product_id.lower(),
                description=desc,
            )
        )
    return devices


def list_usb_devices() -> list[UsbDevice]:
    result = subprocess.run(["lsusb"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise UsbOperationError("host", "list", result.stderr.strip())
    return _parse_lsusb(result.stdout)


def find_usb_device(vendor_id: str, product_id: str) -> UsbDevice | None:
    vendor_id = vendor_id.lower()
    product_id = product_id.lower()
    for device in list_usb_devices():
        if device.vendor_id == vendor_id and device.product_id == product_id:
            return device
    return None


def attach_usb_device(spec: UsbAttachSpec) -> None:
    device = find_usb_device(spec.vendor_id, spec.product_id)
    if device is None:
        raise UsbNotFoundError(f"{spec.vendor_id}:{spec.product_id}")

    bus = spec.host_bus or device.bus
    dev = spec.host_device or device.device
    xml = _usb_device_xml(spec.vendor_id, spec.product_id, bus, dev)
    fd, xml_path = tempfile.mkstemp(suffix='.xml')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(xml)
        cmd = ["virsh", "attach-device", spec.vm_id, xml_path, "--persistent"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise UsbOperationError(spec.vm_id, "attach", result.stderr.strip())
    finally:
        os.remove(xml_path)


def detach_usb_device(spec: UsbAttachSpec) -> None:
    device = find_usb_device(spec.vendor_id, spec.product_id)
    if device is None:
        raise UsbNotFoundError(f"{spec.vendor_id}:{spec.product_id}")

    bus = spec.host_bus or device.bus
    dev = spec.host_device or device.device
    xml = _usb_device_xml(spec.vendor_id, spec.product_id, bus, dev)
    fd, xml_path = tempfile.mkstemp(suffix='.xml')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(xml)
        cmd = ["virsh", "detach-device", spec.vm_id, xml_path, "--persistent"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise UsbOperationError(spec.vm_id, "detach", result.stderr.strip())
    finally:
        os.remove(xml_path)
