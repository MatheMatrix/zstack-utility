
import os
import re
from typing import Optional

from zstacklib.utils.bash import bash_o, bash_roe
from zstacklib.utils.log import get_logger
from zstacklib.utils import linux

from .address import PciError, parse_pci_address
from .device import get_device

logger = get_logger(__name__)

_IOMMU_BLACKLIST = "modprobe.blacklist=snd_hda_intel,amd76x_edac,vga16fb,nouveau,rivafb,nvidiafb,rivatv,amdgpu,radeon"


def get_iommu_type() -> str:
    """Get IOMMU type based on CPU model.

    Returns:
        "amd_iommu" or "intel_iommu".
    """
    _, model_name = linux.get_cpu_model()
    model = model_name.lower()
    return "amd_iommu" if "hygon" in model or "amd" in model else "intel_iommu"


def is_iommu_enabled() -> bool:
    """Check if IOMMU is enabled.

    Returns:
        True if IOMMU is enabled by BIOS and kernel cmdline.
    """
    iommu_folder = "/sys/class/iommu"
    iommu_type = get_iommu_type()
    bios_enabled = os.path.isdir(iommu_folder) and bool(os.listdir(iommu_folder))
    r_kernel, _, _ = bash_roe("grep '%s=on' /proc/cmdline" % iommu_type)
    return bios_enabled and r_kernel == 0


def enable_iommu_in_grub(grub_file: str = "/etc/default/grub") -> bool:
    """Enable IOMMU in GRUB config.

    Args:
        grub_file: Path to GRUB config file.

    Returns:
        True if the operation succeeds.

    Raises:
        PciError: When the grub file cannot be read or written.
    """
    content = linux.read_file(grub_file)
    if content is None:
        raise PciError("failed to read grub file: %s" % grub_file)

    iommu_type = get_iommu_type()
    updated_lines = []
    matched_cmdline = False

    for line in content.splitlines(True):
        if line.strip().startswith("GRUB_CMDLINE_LINUX"):
            matched_cmdline = True
            line = re.sub(r"\b%s\s*=\s*(on|off)\b" % iommu_type, "", line)
            line = re.sub(r"\bmodprobe\.blacklist\s*=\s*\S+", "", line)
            match = re.match(r'(\s*GRUB_CMDLINE_LINUX\s*=\s*")(.*)("\s*)', line)
            if match:
                prefix, cmdline, suffix = match.groups()
                cmdline = cmdline.strip()
                extra = "%s=on %s" % (iommu_type, _IOMMU_BLACKLIST)
                if extra not in cmdline:
                    cmdline = (cmdline + " " + extra).strip() if cmdline else extra
                line = prefix + cmdline + suffix
            updated_lines.append(line)
        else:
            updated_lines.append(line)

    if not matched_cmdline:
        updated_lines.append("GRUB_CMDLINE_LINUX=\"%s=on %s\"\n" % (iommu_type, _IOMMU_BLACKLIST))

    new_content = "".join(updated_lines)
    if new_content != content:
        if linux.write_file(grub_file, new_content, create_if_not_exist=False) is None:
            raise PciError("failed to update grub file: %s" % grub_file)

    return True


def create_iommu_unsafe_interrupts_conf() -> None:
    """Create iommu unsafe interrupts config.

    Raises:
        PciError: When the config cannot be written.
    """
    conf_file = "/etc/modprobe.d/iommu_unsafe_interrupts.conf"
    conf_text = "options vfio_iommu_type1 allow_unsafe_interrupts=1"
    content = linux.read_file(conf_file)
    if content and conf_text in content:
        return
    if content:
        new_content = content.rstrip("\n") + "\n" + conf_text + "\n"
    else:
        new_content = conf_text + "\n"
    if linux.write_file(conf_file, new_content, create_if_not_exist=True) is None:
        raise PciError("failed to create %s" % conf_file)


def load_vfio_modules() -> None:
    """Load vfio related kernel modules.

    Raises:
        PciError: When module loading fails.
    """
    r, o, e = bash_roe("modprobe vfio && modprobe vfio-pci")
    if r != 0:
        raise PciError("failed to load vfio modules: %s, %s" % (e, o))


def _normalize_address(address: str) -> str:
    domain, bus, slot, function = parse_pci_address(address)
    return "%s:%s:%s.%s" % (domain, bus, slot, function)


def _write_sysfs(path: str, content: str) -> None:
    try:
        with open(path, "w") as fd:
            fd.write(content)
    except Exception as exc:
        raise PciError("failed to write %s: %s" % (path, exc))


def bind_device_to_vfio(address: str) -> None:
    """Bind PCI device to vfio-pci.

    Args:
        address: PCI address string.

    Raises:
        PciError: When binding fails.
    """
    normalized = _normalize_address(address)
    device_path = os.path.join("/sys/bus/pci/devices", normalized)
    if not os.path.exists(device_path):
        raise PciError("pci device not found: %s" % normalized)

    load_vfio_modules()

    driver_link = os.path.join(device_path, "driver")
    if os.path.islink(driver_link):
        current_driver = os.path.basename(os.path.realpath(driver_link))
        if current_driver == "vfio-pci":
            return
        _write_sysfs(os.path.join(driver_link, "unbind"), normalized)

    _write_sysfs(os.path.join(device_path, "driver_override"), "vfio-pci")
    _write_sysfs("/sys/bus/pci/drivers/vfio-pci/bind", normalized)

    device = get_device(normalized)
    if device and device.driver != "vfio-pci":
        logger.debug("pci device %s bound to vfio-pci", normalized)


def unbind_device_from_vfio(address: str) -> None:
    """Unbind PCI device from vfio-pci.

    Args:
        address: PCI address string.

    Raises:
        PciError: When unbinding fails.
    """
    normalized = _normalize_address(address)
    device_path = os.path.join("/sys/bus/pci/devices", normalized)
    if not os.path.exists(device_path):
        raise PciError("pci device not found: %s" % normalized)

    driver_link = os.path.join(device_path, "driver")
    if os.path.islink(driver_link):
        current_driver = os.path.basename(os.path.realpath(driver_link))
        if current_driver != "vfio-pci":
            return
        _write_sysfs(os.path.join(driver_link, "unbind"), normalized)

    _write_sysfs(os.path.join(device_path, "driver_override"), "")
