# Copyright (c) ZStack.io, Inc.

"""
Ceph data models and structures.

This module defines data classes for Ceph pool and OSD capacity management.
"""

from typing import Dict, List, Optional, Any


class CephOsdCapacity:
    """
    Ceph OSD capacity information.
    
    Represents the capacity metrics for a single OSD.
    """
    
    def __init__(self, size, available_capacity, used_capacity):
        # type: (int, int, int) -> None
        """
        Initialize OSD capacity.
        
        Args:
            size: Total OSD size in bytes.
            available_capacity: Available capacity in bytes.
            used_capacity: Used capacity in bytes.
        """
        self.size = size
        self.availableCapacity = available_capacity
        self.usedCapacity = used_capacity


class CephPoolCapacity:
    """
    Ceph pool capacity and configuration information.
    
    Represents detailed capacity information for a Ceph pool including
    replication settings, CRUSH rules, and OSD associations.
    """
    
    def __init__(self, pool_name, replicated_size, crush_rule_set, security_policy, disk_utilization):
        # type: (str, int, Optional[int], str, float) -> None
        """
        Initialize pool capacity.
        
        Args:
            pool_name: Name of the pool.
            replicated_size: Number of replicas.
            crush_rule_set: CRUSH rule set ID.
            security_policy: Security policy ("Copy" or "ErasureCode").
            disk_utilization: Effective disk utilization ratio.
        """
        self.pool_name = pool_name
        self.replicated_size = replicated_size
        self.disk_utilization = disk_utilization
        self.security_policy = security_policy
        self.crush_rule_set = crush_rule_set
        self.available_capacity = 0  # type: int
        self.used_capacity = 0  # type: int
        self.crush_rule_item_names = []  # type: List[str]
        self.crush_item_osds = []  # type: List[str]
        self.crush_item_osds_total_size = 0  # type: int
        self.pool_total_size = 0  # type: int
        self.related_osd_capacity = {}  # type: Dict[str, CephOsdCapacity]
    
    def get_related_osds(self):
        # type: () -> str
        """Get comma-separated list of related OSD names."""
        return ",".join(self.crush_item_osds)


# Constants
CEPH_CONF_ROOT = "/var/lib/zstack/ceph"
CEPH_KEYRING_CONFIG_NAME = 'client.zstack.keyring'
CEPH_CONF_FILENAME = "ceph.conf"

# NBD constants
QEMU_NBD_SOCKET_DIR = "/var/lock/"
QEMU_NBD_SOCKET_PREFIX = "qemu-nbd-nbd"
NBD_DEV_PREFIX = "/dev/nbd"

# Manufacturer constants
MANUFACTURER_XSKY = "xsky"
MANUFACTURER_SANDSTONE = "sandstone"
MANUFACTURER_OPENSOURCE = "open-source"
