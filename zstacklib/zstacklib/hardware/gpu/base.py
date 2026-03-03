
from abc import ABC, abstractmethod
from typing import List

from .models import MdevDevice, MdevType, VgpuType


class GpuAdapter(ABC):
    """Gpuadapter."""
    VENDOR_ID: str

    def __init__(self, pci_address: str):
        """Init."""
        self.pci_address = pci_address

    @abstractmethod
    def get_driver_version(self) -> str:
        """Get driver version."""
        ...

    @abstractmethod
    def get_vgpu_types(self) -> List[VgpuType]:
        """Get vgpu types."""
        ...

    @abstractmethod
    def get_mdev_supported_types(self) -> List[MdevType]:
        """Get mdev supported types."""
        ...

    @abstractmethod
    def create_mdev(self, type_id: str, uuid: str) -> MdevDevice:
        """Create mdev."""
        ...

    @abstractmethod
    def destroy_mdev(self, uuid: str) -> None:
        """Destroy mdev."""
        ...
