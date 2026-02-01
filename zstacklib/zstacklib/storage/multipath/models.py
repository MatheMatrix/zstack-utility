"""Data models for multipath operations.

This module defines data classes for multipath objects:

- MultipathDevice: Multipath device information
- MultipathPath: Individual path in a multipath device
- MultipathConfig: Configuration section model
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class MultipathPath:
    """Individual path in a multipath device.
    
    Attributes:
        device: Device name (e.g., sda, sdb)
        host: SCSI host number
        channel: SCSI channel
        target: SCSI target
        lun: SCSI LUN
        state: Path state (e.g., 'active', 'failed')
        priority: Path priority group
        dm_state: Device-mapper state (e.g., 'active', 'failed')
    """
    device: str
    host: int = 0
    channel: int = 0
    target: int = 0
    lun: int = 0
    state: str = "active"
    priority: int = 1
    dm_state: str = "active"
    
    @property
    def hctl(self) -> str:
        """Get HCTL address string."""
        return "{}:{}:{}:{}".format(self.host, self.channel, self.target, self.lun)


@dataclass
class MultipathDevice:
    """Multipath device information.
    
    Attributes:
        name: Multipath device name (e.g., mpath0)
        wwid: World Wide Identifier
        dm_name: Device mapper name (e.g., dm-0)
        paths: List of paths in this device
        policy: Path selection policy
        vendor: Device vendor
        product: Device product
        size: Device size in bytes
        features: Device features
    """
    name: str
    wwid: str
    dm_name: str = ""
    paths: List[MultipathPath] = field(default_factory=list)
    policy: str = "service-time 0"
    vendor: Optional[str] = None
    product: Optional[str] = None
    size: int = 0
    features: str = ""
    
    @property
    def path(self) -> str:
        """Get device path."""
        return "/dev/mapper/{}".format(self.name)
    
    @property
    def dm_path(self) -> str:
        """Get device-mapper path."""
        if self.dm_name:
            return "/dev/{}".format(self.dm_name)
        return self.path
    
    @property
    def path_count(self) -> int:
        """Get number of paths."""
        return len(self.paths)
    
    @property
    def active_path_count(self) -> int:
        """Get number of active paths."""
        return sum(1 for p in self.paths if p.state == "active")


@dataclass
class BlacklistEntry:
    """Multipath blacklist entry.
    
    Attributes:
        wwid: WWID to blacklist
        devnode: Device node pattern to blacklist
        device: Device vendor/product to blacklist
    """
    wwid: Optional[str] = None
    devnode: Optional[str] = None
    device: Optional[Dict[str, str]] = None


@dataclass 
class DeviceConfig:
    """Multipath device configuration section.
    
    Used for devices section in multipath.conf.
    
    Attributes:
        vendor: Vendor pattern
        product: Product pattern
        features: Device features
        no_path_retry: Behavior when no paths
        path_grouping_policy: Path grouping policy
    """
    vendor: str = ".*"
    product: str = ".*"
    features: str = "0"
    no_path_retry: str = "fail"
    path_grouping_policy: Optional[str] = None
    path_selector: Optional[str] = None
    path_checker: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to configuration dict."""
        result = {
            "vendor": self.vendor,
            "product": self.product,
            "features": self.features,
            "no_path_retry": self.no_path_retry,
        }
        if self.path_grouping_policy:
            result["path_grouping_policy"] = self.path_grouping_policy
        if self.path_selector:
            result["path_selector"] = self.path_selector
        if self.path_checker:
            result["path_checker"] = self.path_checker
        return result


# Default device configuration used by ZStack
DEFAULT_DEVICE_CONFIG = DeviceConfig(
    vendor=".*",
    product=".*",
    features="0",
    no_path_retry="fail"
)
