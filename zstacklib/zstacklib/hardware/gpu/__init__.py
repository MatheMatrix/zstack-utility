
from typing import Dict, List, Optional, Type

from zstacklib.utils.log import get_logger

from zstacklib.hardware.pci import PciDevice, scan_devices

from .base import GpuAdapter
from .mdev import (
    create_mdev_device,
    destroy_mdev_device,
    get_mdev_device,
    list_mdev_devices,
    scan_mdev_types,
)
from .models import GpuError, MdevDevice, MdevError, MdevType, VgpuType
from .nvidia import NvidiaGpuAdapter

logger = get_logger(__name__)


class AmdGpuAdapter(GpuAdapter):
    VENDOR_ID = "1002"

    def get_driver_version(self) -> str:
        raise NotImplementedError

    def get_vgpu_types(self) -> List[VgpuType]:
        raise NotImplementedError

    def get_mdev_supported_types(self) -> List[MdevType]:
        raise NotImplementedError

    def create_mdev(self, type_id: str, uuid: str) -> MdevDevice:
        raise NotImplementedError

    def destroy_mdev(self, uuid: str) -> None:
        raise NotImplementedError


class IntelGpuAdapter(GpuAdapter):
    VENDOR_ID = "8086"

    def get_driver_version(self) -> str:
        raise NotImplementedError

    def get_vgpu_types(self) -> List[VgpuType]:
        raise NotImplementedError

    def get_mdev_supported_types(self) -> List[MdevType]:
        raise NotImplementedError

    def create_mdev(self, type_id: str, uuid: str) -> MdevDevice:
        raise NotImplementedError

    def destroy_mdev(self, uuid: str) -> None:
        raise NotImplementedError


_ADAPTERS: Dict[str, Type[GpuAdapter]] = {
    NvidiaGpuAdapter.VENDOR_ID: NvidiaGpuAdapter,
    AmdGpuAdapter.VENDOR_ID: AmdGpuAdapter,
    IntelGpuAdapter.VENDOR_ID: IntelGpuAdapter,
}


def _is_gpu_device(device: PciDevice) -> bool:
    return device.device_type.startswith("GPU_")


def _match_address(device_address: str, target_address: str) -> bool:
    if device_address == target_address:
        return True
    return device_address.endswith(target_address)


def _select_adapter(device: PciDevice) -> Optional[GpuAdapter]:
    vendor_id = device.vendor_id.strip().lower()
    adapter_cls = _ADAPTERS.get(vendor_id)
    if not adapter_cls:
        return None
    return adapter_cls(device.address)


def get_gpu_adapter(pci_address: str) -> Optional[GpuAdapter]:
    for device in scan_devices():
        if _match_address(device.address, pci_address):
            if not _is_gpu_device(device):
                return None
            return _select_adapter(device)
    return None


def scan_gpus() -> List[GpuAdapter]:
    adapters: List[GpuAdapter] = []
    for device in scan_devices():
        if not _is_gpu_device(device):
            continue
        adapter = _select_adapter(device)
        if adapter:
            adapters.append(adapter)
    return adapters


__all__ = [
    "GpuAdapter",
    "GpuError",
    "MdevError",
    "MdevDevice",
    "MdevType",
    "VgpuType",
    "NvidiaGpuAdapter",
    "AmdGpuAdapter",
    "IntelGpuAdapter",
    "create_mdev_device",
    "destroy_mdev_device",
    "get_mdev_device",
    "list_mdev_devices",
    "scan_mdev_types",
    "get_gpu_adapter",
    "scan_gpus",
]
