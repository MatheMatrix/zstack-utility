
from abc import ABC, abstractmethod
from typing import List

from .models import MdevDevice, MdevType, VgpuType


class GpuAdapter(ABC):
    VENDOR_ID: str

    def __init__(self, pci_address: str):
        self.pci_address = pci_address

    @abstractmethod
    def get_driver_version(self) -> str:
        ...

    @abstractmethod
    def get_vgpu_types(self) -> List[VgpuType]:
        ...

    @abstractmethod
    def get_mdev_supported_types(self) -> List[MdevType]:
        ...

    @abstractmethod
    def create_mdev(self, type_id: str, uuid: str) -> MdevDevice:
        ...

    @abstractmethod
    def destroy_mdev(self, uuid: str) -> None:
        ...
