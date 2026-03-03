
import os
import re
from typing import List, Optional, Tuple

from zstacklib.utils.bash import bash_roe
from zstacklib.utils.log import get_logger

from zstacklib.hardware.pci import bind_device_to_vfio, unbind_device_from_vfio

from .models import SriovError, VirtualFunction

logger = get_logger(__name__)

_PCI_DEVICES_PATH = "/sys/bus/pci/devices"


def _read_sysfs(path: str) -> Optional[str]:
    """Read sysfs."""
    try:
        with open(path, "r") as fd:
            return fd.read().strip()
    except Exception as exc:
        logger.debug("failed to read %s: %s", path, exc)
        return None


def _write_sysfs(path: str, content: str) -> None:
    """Write sysfs."""
    try:
        with open(path, "w") as fd:
            fd.write(content)
    except Exception as exc:
        raise SriovError("failed to write %s: %s" % (path, exc))


def _resolve_device_path(address: str) -> Optional[str]:
    """Resolve device path."""
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
    """Get driver name."""
    driver_link = os.path.join(device_path, "driver")
    if os.path.islink(driver_link):
        return os.path.basename(os.path.realpath(driver_link))
    return None


def _list_vf_entries(device_path: str) -> List[Tuple[int, str]]:
    """List vf entries."""
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


def _find_vf_index(pf_path: str, vf_address: str) -> int:
    """Find vf index."""
    for index, address in _list_vf_entries(pf_path):
        if address == vf_address:
            return index
    return -1


def _build_nodedev_name(address: str) -> Optional[str]:
    """Build nodedev name."""
    addr = address
    if len(addr.split(":")) != 3:
        addr = "0000:" + addr
    parts = re.split(r":|\.", addr)
    if len(parts) != 4:
        return None
    return "pci_%s_%s_%s_%s" % tuple(parts)


def _check_allocated_virtual_functions(pf_address: str) -> Optional[str]:
    """Check allocated virtual functions."""
    pf_node = _build_nodedev_name(pf_address)
    if not pf_node:
        return "invalid pci address for PF: %s" % pf_address

    r, vf_lines, e = bash_roe("virsh nodedev-dumpxml %s | grep 'address domain'" % pf_node)
    if r != 0:
        return "failed to run `virsh nodedev-dumpxml %s`: %s" % (pf_node, e)

    pattern = re.compile(r".*0x([0-9a-f]*).*0x([0-9a-f]*).*0x([0-9a-f]*).*0x([0-9a-f]*).*")
    for vf_line in vf_lines.splitlines():
        vf_line = vf_line.strip()
        match = pattern.match(vf_line)
        if not match:
            continue
        vf_node = "pci_%s_%s_%s_%s" % tuple(match.groups())
        r, _, _ = bash_roe("virsh nodedev-dumpxml %s | grep vfio-pci" % vf_node)
        if r == 0:
            return "virtual function %s of pf %s still allocated to some vm" % (vf_node, pf_node)
    return None


def enable_sriov(pf_address: str, num_vfs: int) -> List[VirtualFunction]:
    """Enable sriov."""
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        raise SriovError("pci device not found: %s" % pf_address)
    numvfs_path = os.path.join(device_path, "sriov_numvfs")
    if not os.path.exists(numvfs_path):
        raise SriovError("cannot find sriov_numvfs for pci device: %s" % pf_address)
    _write_sysfs(numvfs_path, str(num_vfs))
    return list_vfs(os.path.basename(device_path))


def disable_sriov(pf_address: str) -> None:
    """Disable sriov."""
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        raise SriovError("pci device not found: %s" % pf_address)
    numvfs_path = os.path.join(device_path, "sriov_numvfs")
    if not os.path.exists(numvfs_path):
        raise SriovError("cannot find sriov_numvfs for pci device: %s" % pf_address)

    error = _check_allocated_virtual_functions(os.path.basename(device_path))
    if error:
        raise SriovError(error)

    _write_sysfs(numvfs_path, "0")


def list_vfs(pf_address: str) -> List[VirtualFunction]:
    """List vfs."""
    device_path = _resolve_device_path(pf_address)
    if not device_path:
        return []

    vfs: List[VirtualFunction] = []
    for vf_index, vf_address in _list_vf_entries(device_path):
        vf_path = _resolve_device_path(vf_address)
        if not vf_path:
            continue
        driver = _get_driver_name(vf_path)
        vfs.append(
            VirtualFunction(
                address=vf_address,
                pf_address=os.path.basename(device_path),
                vf_index=vf_index,
                driver=driver,
                is_bound_to_vfio=driver == "vfio-pci",
            )
        )
    return vfs


def get_vf_info(vf_address: str) -> Optional[VirtualFunction]:
    """Get vf info."""
    vf_path = _resolve_device_path(vf_address)
    if not vf_path:
        return None
    physfn_link = os.path.join(vf_path, "physfn")
    if not (os.path.islink(physfn_link) or os.path.exists(physfn_link)):
        return None
    pf_path = os.path.realpath(physfn_link)
    pf_address = os.path.basename(pf_path)
    vf_index = _find_vf_index(pf_path, os.path.basename(vf_path))
    if vf_index < 0:
        logger.debug("cannot resolve vf index for %s under %s", vf_address, pf_address)
        vf_index = 0
    driver = _get_driver_name(vf_path)
    return VirtualFunction(
        address=os.path.basename(vf_path),
        pf_address=pf_address,
        vf_index=vf_index,
        driver=driver,
        is_bound_to_vfio=driver == "vfio-pci",
    )


def bind_vf_to_vfio(vf_address: str) -> None:
    """Bind vf to vfio."""
    try:
        bind_device_to_vfio(vf_address)
    except Exception as exc:
        raise SriovError("failed to bind vf %s to vfio-pci: %s" % (vf_address, exc))


def unbind_vf_from_vfio(vf_address: str) -> None:
    """Unbind vf from vfio."""
    try:
        unbind_device_from_vfio(vf_address)
    except Exception as exc:
        raise SriovError("failed to unbind vf %s from vfio-pci: %s" % (vf_address, exc))
