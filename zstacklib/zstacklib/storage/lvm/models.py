"""Data models for LVM operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class VolumeProvisioningStrategy(str, Enum):
    """Volume provisioning strategy."""
    THIN = "ThinProvisioning"
    THICK = "ThickProvisioning"


class LvmLockType(Enum):
    """LVM lock types for shared storage."""
    NULL = 0
    SHARE = 1
    EXCLUSIVE = 2

    @classmethod
    def from_abbr(cls, abbr: str) -> "LvmLockType":
        """Parse lock type from lvmlockd abbreviation."""
        abbr = abbr.strip()
        mapping = {"sh": cls.SHARE, "ex": cls.EXCLUSIVE, "un": cls.NULL, "": cls.NULL}
        if abbr in mapping:
            return mapping[abbr]
        raise ValueError(f"Unknown lock type abbreviation: {abbr}")


class LvmError(Exception):
    """Base exception for LVM operations."""
    pass


class VgNotFoundError(LvmError):
    """Volume group not found."""
    pass


class LvNotFoundError(LvmError):
    """Logical volume not found."""
    pass


class PvNotFoundError(LvmError):
    """Physical volume not found."""
    pass


class LvmLockError(LvmError):
    """LVM lock operation failed."""
    pass


@dataclass
class PhysicalVolume:
    """Physical Volume information."""
    path: str
    uuid: str
    vg_name: str
    size: int
    free: int
    format: str = "lvm2"
    attrs: str = ""
    
    @property
    def used(self) -> int:
        """Used."""
        return self.size - self.free


@dataclass
class VolumeGroup:
    """Volume Group information."""
    name: str
    uuid: str
    size: int
    free: int
    pv_count: int
    lv_count: int
    attrs: str = ""
    tags: List[str] = field(default_factory=list)
    lock_type: Optional[str] = None
    
    @property
    def used(self) -> int:
        """Used."""
        return self.size - self.free


@dataclass
class LogicalVolume:
    """Logical Volume information."""
    name: str
    vg_name: str
    path: str
    size: int
    attrs: str = ""
    uuid: str = ""
    tags: List[str] = field(default_factory=list)
    pool_lv: Optional[str] = None
    origin: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """Check is active."""
        return len(self.attrs) > 4 and self.attrs[4] == 'a'
    
    @property
    def is_thin(self) -> bool:
        """Check is thin."""
        return len(self.attrs) > 0 and self.attrs[0] == 'V'
    
    @property
    def is_snapshot(self) -> bool:
        """Check is snapshot."""
        return len(self.attrs) > 0 and self.attrs[0] in ('s', 'S')


@dataclass
class ThinPool:
    """Thin pool information."""
    name: str
    vg_name: str
    size: int
    data_percent: float
    metadata_percent: float
    
    @property
    def path(self) -> str:
        """Path."""
        return f"/dev/{self.vg_name}/{self.name}"
    
    @property
    def used(self) -> int:
        """Used."""
        return int(self.size * self.data_percent / 100)
    
    @property
    def free(self) -> int:
        """Free."""
        return self.size - self.used


@dataclass
class BlockDevice:
    """Block device information for shared storage."""
    path: str
    wwid: Optional[str] = None
    wwn: Optional[str] = None
    serial: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    size: int = 0
    type: str = ""
    hctl: Optional[str] = None
