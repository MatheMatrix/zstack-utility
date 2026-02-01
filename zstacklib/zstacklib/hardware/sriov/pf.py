
import os
import re
from typing import List, Optional, Tuple

from zstacklib.utils.log import get_logger

from .models import SriovDevice

logger = get_logger(__name__)

_PCI_DEVICES_PATH = "/sys/bus/pci/devices"


def _read_sysfs(path: str) -> Optional[str]:
    try:
        with open(path, "r") as fd:
            return fd.read().strip()
    except Exception as exc:
        logger.debug("failed to read %s: %s", path, exc)
        return None


def _read_int(path: str) -> int:
    content = _read_sysfs(path)
    if not content:
        return 0
    match = re.search(r"(\d+)", content)
    return int(match.group(1)) if match else 0


def _resolve_device_path(address: str) -> Optional[str]:
    if not address:
        return None
    device_path = os.path.join(_PCI_DEVICES_PATH, address)
    if os.path.exists(device_path):
        return device_path
    if not os.path.isdir(_PCI_DEVICES_PATH):
        return None
    for entry in os.listdir(_PCI_DEVICES_PATH):
        if entry.endswith(address):
            candidate = os.path.join(_PCI_DEVICES_PATH, entry)
            if os.path.exists(candidate):
                return candidate
    return None


def _get_driver_name(device_path: str) -> Optional[str]:
    driver_link = os.path.join(device_path, "driver")
    if os.path.islink(driver_link):
        return os.path.basename(os.path.realpath(driver_link))
    return None


def _list_vf_entries(device_path: str) -> List[Tuple[int, str]]:
    vf_entries: List[Tuple[int, str]] = []
    if not os.path.isdir(device_path):
        return vf_entries
    for entry in os.listdir(device_path):
        if not entry.startswith("virtfn"):
            continue
        match = re.match(r"virtfn(\d+)", entry)
        if not match:
            continue
        vf_index = int(match.group(1))
        vf_link = os.path.join(device_path, entry)
        if not (os.path.islink(vf_link) or os.path.exists(vf_link)):
            continue
        vf_address = os.path.basename(os.path.realpath(vf_link))
        vf_entries.append((vf_index, vf_address))
    return sorted(vf_entries, key=lambda item: item[0])


def is_sriov_capable(pf_address: str) -> bool:
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        return False
    total_path = os.path.join(device_path, "sriov_totalvfs")
    if not os.path.exists(total_path):
        return False
    return _read_int(total_path) > 0


def get_total_vfs(pf_address: str) -> int:
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        return 0
    return _read_int(os.path.join(device_path, "sriov_totalvfs"))


def get_num_vfs(pf_address: str) -> int:
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        return 0
    return _read_int(os.path.join(device_path, "sriov_numvfs"))


def get_pf_info(pf_address: str) -> Optional[SriovDevice]:
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        return None
    total_path = os.path.join(device_path, "sriov_totalvfs")
    if not os.path.exists(total_path):
        return None
    total_vfs = _read_int(total_path)
    if total_vfs <= 0:
        return None
    num_vfs = _read_int(os.path.join(device_path, "sriov_numvfs"))
    vf_entries = _list_vf_entries(device_path)
    vf_addresses = [vf_address for _, vf_address in vf_entries]
    return SriovDevice(
        pf_address=os.path.basename(device_path),
        total_vfs=total_vfs,
        num_vfs=num_vfs,
        vf_addresses=vf_addresses,
        driver=_get_driver_name(device_path),
    )


def list_sriov_devices() -> List[SriovDevice]:
    devices: List[SriovDevice] = []
    if not os.path.isdir(_PCI_DEVICES_PATH):
        return devices
    for entry in sorted(os.listdir(_PCI_DEVICES_PATH)):
        device = get_pf_info(entry)
        if device is None:
            continue
        devices.append(device)
    return devices
