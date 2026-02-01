
import os
import re
from typing import List, Optional

from zstacklib.utils.log import get_logger

from .models import MdevDevice, MdevError, MdevType

logger = get_logger(__name__)

_PCI_DEVICES_PATH = "/sys/bus/pci/devices"
_MDEV_DEVICES_PATH = "/sys/bus/mdev/devices"


def _read_sysfs(path: str) -> Optional[str]:
    try:
        with open(path, "r") as fd:
            return fd.read().strip()
    except Exception as exc:
        logger.debug("failed to read %s: %s", path, exc)
        return None


def _write_sysfs(path: str, content: str) -> None:
    try:
        with open(path, "w") as fd:
            fd.write(content)
    except Exception as exc:
        raise MdevError("failed to write %s: %s" % (path, exc))


def _parse_int(value: Optional[str]) -> int:
    if not value:
        return 0
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else 0


def scan_mdev_types(pci_address: str) -> List[MdevType]:
    supported_path = os.path.join(_PCI_DEVICES_PATH, pci_address, "mdev_supported_types")
    if not os.path.isdir(supported_path):
        return []

    types: List[MdevType] = []
    for type_id in sorted(os.listdir(supported_path)):
        type_path = os.path.join(supported_path, type_id)
        if not os.path.isdir(type_path):
            continue
        name = _read_sysfs(os.path.join(type_path, "name")) or type_id
        available = _parse_int(_read_sysfs(os.path.join(type_path, "available_instances")))
        description = _read_sysfs(os.path.join(type_path, "description")) or ""
        types.append(
            MdevType(
                type_id=type_id,
                name=name,
                available_instances=available,
                description=description,
            )
        )
    return types


def _resolve_mdev_type(device_path: str) -> str:
    type_link = os.path.join(device_path, "mdev_type")
    if os.path.islink(type_link):
        return os.path.basename(os.path.realpath(type_link))
    if os.path.exists(type_link):
        content = _read_sysfs(type_link)
        if content:
            return content
        return os.path.basename(os.path.realpath(type_link))
    return ""


def _resolve_mdev_parent(device_path: str) -> str:
    parent_link = os.path.join(device_path, "device")
    if os.path.islink(parent_link) or os.path.exists(parent_link):
        return os.path.basename(os.path.realpath(parent_link))
    parent_link = os.path.join(device_path, "parent")
    if os.path.islink(parent_link) or os.path.exists(parent_link):
        return os.path.basename(os.path.realpath(parent_link))
    return ""


def get_mdev_device(uuid: str) -> Optional[MdevDevice]:
    device_path = os.path.join(_MDEV_DEVICES_PATH, uuid)
    if not os.path.isdir(device_path):
        return None

    type_id = _resolve_mdev_type(device_path)
    pci_address = _resolve_mdev_parent(device_path)
    status = _read_sysfs(os.path.join(device_path, "state")) or ""
    return MdevDevice(uuid=uuid, type_id=type_id, pci_address=pci_address, status=status)


def list_mdev_devices(pci_address: str = None) -> List[MdevDevice]:
    if not os.path.isdir(_MDEV_DEVICES_PATH):
        return []

    devices: List[MdevDevice] = []
    for uuid in sorted(os.listdir(_MDEV_DEVICES_PATH)):
        device = get_mdev_device(uuid)
        if device is None:
            continue
        if pci_address and device.pci_address != pci_address:
            continue
        devices.append(device)
    return devices


def create_mdev_device(pci_address: str, type_id: str, uuid: str) -> MdevDevice:
    type_path = os.path.join(_PCI_DEVICES_PATH, pci_address, "mdev_supported_types", type_id)
    create_path = os.path.join(type_path, "create")
    if not os.path.exists(create_path):
        raise MdevError("mdev type not found for pci device %s: %s" % (pci_address, type_id))

    _write_sysfs(create_path, uuid)
    device = get_mdev_device(uuid)
    if device is None:
        raise MdevError("failed to create mdev device %s on %s" % (uuid, pci_address))
    return device


def destroy_mdev_device(uuid: str) -> None:
    remove_path = os.path.join(_MDEV_DEVICES_PATH, uuid, "remove")
    if not os.path.exists(remove_path):
        raise MdevError("mdev device not found: %s" % uuid)
    _write_sysfs(remove_path, "1")
