
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SriovDevice:
    pf_address: str
    total_vfs: int
    num_vfs: int
    vf_addresses: List[str]
    driver: Optional[str] = None


@dataclass
class VirtualFunction:
    address: str
    pf_address: str
    vf_index: int
    driver: Optional[str] = None
    is_bound_to_vfio: bool = False


class SriovError(Exception):
    pass
