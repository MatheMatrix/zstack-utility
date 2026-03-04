
from dataclasses import dataclass


class GpuError(Exception):
    """Base exception for GPU errors."""
    pass


class MdevError(GpuError):
    """Raised when a mediated device operation fails."""
    pass


@dataclass
class VgpuType:
    """Virtual GPU type metadata."""
    type_id: str
    name: str
    max_instances: int
    framebuffer_mb: int


@dataclass
class MdevType:
    """Mediated device type metadata."""
    type_id: str
    name: str
    available_instances: int
    description: str


@dataclass
class MdevDevice:
    """Mediated device instance."""
    uuid: str
    type_id: str
    pci_address: str
    status: str
