
from dataclasses import dataclass


class GpuError(Exception):
    """Gpuerror."""
    pass


class MdevError(GpuError):
    """Mdeverror."""
    pass


@dataclass
class VgpuType:
    """Vgputype."""
    type_id: str
    name: str
    max_instances: int
    framebuffer_mb: int


@dataclass
class MdevType:
    """Mdevtype."""
    type_id: str
    name: str
    available_instances: int
    description: str


@dataclass
class MdevDevice:
    """Mdevdevice."""
    uuid: str
    type_id: str
    pci_address: str
    status: str
