
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SriovDevice:
    """SR-IOV physical function device information."""
    pf_address: str
    total_vfs: int
    num_vfs: int
    vf_addresses: List[str]
    driver: Optional[str] = None


@dataclass
class VirtualFunction:
    """SR-IOV virtual function information."""
    address: str
    pf_address: str
    vf_index: int
    driver: Optional[str] = None
    is_bound_to_vfio: bool = False


class SriovError(Exception):
    """Base exception for SR-IOV errors."""
    pass
