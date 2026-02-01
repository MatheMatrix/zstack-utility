
from dataclasses import dataclass


class GpuError(Exception):
    pass


class MdevError(GpuError):
    pass


@dataclass
class VgpuType:
    type_id: str
    name: str
    max_instances: int
    framebuffer_mb: int


@dataclass
class MdevType:
    type_id: str
    name: str
    available_instances: int
    description: str


@dataclass
class MdevDevice:
    uuid: str
    type_id: str
    pci_address: str
    status: str
