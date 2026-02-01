
import re
from typing import Dict, List

from zstacklib.utils.bash import bash_o, bash_roe
from zstacklib.utils.log import get_logger

from .base import GpuAdapter
from .mdev import create_mdev_device, destroy_mdev_device, scan_mdev_types
from .models import MdevDevice, MdevType, VgpuType

logger = get_logger(__name__)


def _parse_nvidia_smi_output(output: str) -> List[VgpuType]:
    entries: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    for line in output.splitlines():
        if ":" not in line:
            continue
        title, content = line.split(":", 1)
        title = title.strip()
        content = content.strip()
        if title == "vGPU Type ID":
            if current:
                entries.append(current)
            current = {"vGPU Type ID": content}
            continue
        if not current:
            continue
        current[title] = content

    if current:
        entries.append(current)

    def _parse_int(value: str) -> int:
        if not value:
            return 0
        match = re.search(r"(\d+)", value)
        return int(match.group(1)) if match else 0

    vgpu_types: List[VgpuType] = []
    for item in entries:
        type_id = item.get("vGPU Type ID", "")
        name = item.get("vGPU Type Name") or item.get("vGPU Type") or ""
        max_instances = _parse_int(item.get("Max vGPUs per GPU", ""))
        framebuffer_mb = _parse_int(item.get("Frame Buffer Size", ""))
        vgpu_types.append(
            VgpuType(
                type_id=type_id,
                name=name,
                max_instances=max_instances,
                framebuffer_mb=framebuffer_mb,
            )
        )
    return vgpu_types


class NvidiaGpuAdapter(GpuAdapter):
    VENDOR_ID = "10de"

    def _has_nvidia_smi(self) -> bool:
        return bool(bash_o("which nvidia-smi").strip())

    def _normalize_type_id(self, type_id: str) -> str:
        if type_id.startswith("nvidia-"):
            return type_id
        if type_id.isdigit():
            return "nvidia-%s" % type_id
        return type_id

    def get_driver_version(self) -> str:
        if not self._has_nvidia_smi():
            return ""
        r, o, e = bash_roe(
            "nvidia-smi --query-gpu=driver_version --format=csv,noheader -i %s" % self.pci_address
        )
        if r != 0:
            logger.debug("failed to query nvidia driver version: %s, %s", e, o)
            return ""
        return o.strip().splitlines()[0] if o.strip() else ""

    def get_vgpu_types(self) -> List[VgpuType]:
        if not self._has_nvidia_smi():
            return []
        r, o, e = bash_roe("nvidia-smi vgpu -i %s -v -c" % self.pci_address)
        if r != 0:
            logger.debug("failed to query nvidia vgpu types: %s, %s", e, o)
            return []
        return _parse_nvidia_smi_output(o)

    def get_mdev_supported_types(self) -> List[MdevType]:
        return scan_mdev_types(self.pci_address)

    def create_mdev(self, type_id: str, uuid: str) -> MdevDevice:
        normalized = self._normalize_type_id(type_id)
        return create_mdev_device(self.pci_address, normalized, uuid)

    def destroy_mdev(self, uuid: str) -> None:
        destroy_mdev_device(uuid)
