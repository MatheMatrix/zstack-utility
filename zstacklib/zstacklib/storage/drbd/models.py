# Copyright (c) ZStack.io, Inc.

"""
DRBD data models and enumerations.

This module defines dataclasses and enumerations for DRBD state management.
"""

from typing import Optional


class DrbdRole:
    """DRBD node role constants."""
    Primary = "Primary"
    Secondary = "Secondary"


class DrbdNetState:
    """DRBD network connection state constants."""
    WFConnection = "WFConnection"
    Unconfigured = "Unconfigured"
    StandAlone = "StandAlone"
    Disconnecting = "Disconnecting"
    Unconnected = "Unconnected"
    Timeout = "Timeout"
    BrokenPipe = "BrokenPipe"
    NetworkFailure = "NetworkFailure"
    ProtocolError = "ProtocolError"
    Connecting = "Connecting"
    TearDown = "TearDown"
    Connected = "Connected"
    Unknown = "Unknown"
    
    # States that indicate active connection attempt
    CONNECTING_STATES = ('Connecting', 'Connected', 'WFConnection')
    
    # States that indicate disconnected
    DISCONNECTED_STATES = ('StandAlone', 'Disconnecting', 'Unconnected', 
                            'Timeout', 'BrokenPipe', 'NetworkFailure', 
                            'ProtocolError', 'TearDown')


class DrbdDiskState:
    """DRBD disk state constants."""
    UpToDate = "UpToDate"
    Inconsistent = "Inconsistent"
    Diskless = "Diskless"
    Attaching = "Attaching"
    Failed = "Failed"
    Negotiating = "Negotiating"
    DUnknown = "DUnknown"
    Outdated = "Outdated"


class DrbdStruct:
    """Base class for DRBD configuration structures."""
    pass


class DrbdHostStruct(DrbdStruct):
    """
    DRBD host configuration structure.
    
    Represents the configuration for one side of a DRBD resource.
    """
    
    def __init__(self, name):
        # type: (str) -> None
        super(DrbdHostStruct, self).__init__()
        self.hostname = None  # type: Optional[str]
        self.address = None   # type: Optional[str]
        self.disk = None      # type: Optional[str]
        self.device = "/dev/drbd_%s" % name
        self.minor = None     # type: Optional[str]
        self.meta_disk = "internal"
    
    def get_drbd_device(self):
        # type: () -> str
        """Get the DRBD device path based on minor number."""
        return "/dev/drbd%s" % self.minor


class DrbdNetStruct(DrbdStruct):
    """
    DRBD network configuration structure.
    
    Contains network-related settings for DRBD replication.
    """
    
    def __init__(self):
        # type: () -> None
        super(DrbdNetStruct, self).__init__()
        self.csums_alg = 'crc32'
        self.after_sb_0pri = 'discard-zero-changes'
        self.after_sb_1pri = 'call-pri-lost-after-sb'
        self.after_sb_2pri = 'call-pri-lost-after-sb'
        self.sndbuf_size = '2m'
        self.allow_two_primaries = 'yes'
        self.verify_alg = 'crc32'


# Default DRBD configuration values
DRBD_CONFIG_DIR = "/etc/drbd.d"
DRBD_GLOBAL_COMMON = "/etc/drbd.d/global_common.conf"

# Default handler scripts
DEFAULT_SPLIT_BRAIN_HANDLER = '"/usr/lib/drbd/notify-split-brain.sh root"'
DEFAULT_FENCE_PEER_HANDLER = '"python /usr/lib/drbd/mini_fencer.py $DRBD_RESOURCE"'

# Default disk settings
DEFAULT_FENCING = 'resource-and-stonith'
DEFAULT_RESYNC_RATE = '100M'
DEFAULT_C_MIN_RATE = 102400
DEFAULT_C_MAX_RATE = 204800
