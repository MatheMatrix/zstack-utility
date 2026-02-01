"""Data models for iSCSI operations.

This module defines data classes for iSCSI objects:

- IscsiPortal: iSCSI portal (IP:port)
- IscsiTarget: iSCSI target (IQN) information
- IscsiLun: iSCSI LUN information
- IscsiSession: Active iSCSI session information
- ChapCredentials: CHAP authentication credentials
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class IscsiPortal:
    """iSCSI portal address.
    
    Attributes:
        ip: Portal IP address
        port: Portal port (default 3260)
    """
    ip: str
    port: int = 3260
    
    def __str__(self) -> str:
        return "{}:{}".format(self.ip, self.port)
    
    @classmethod
    def from_string(cls, portal_str: str) -> "IscsiPortal":
        """Parse portal from string like '192.168.1.1:3260' or '192.168.1.1,1'.
        
        Args:
            portal_str: Portal string in format 'ip:port' or 'ip,tpgt'
            
        Returns:
            IscsiPortal instance
        """
        # Handle format: "192.168.1.1:3260,1" (ip:port,tpgt)
        portal_str = portal_str.strip()
        
        # Remove trailing tpgt if present (e.g., ",1")
        if "," in portal_str:
            portal_str = portal_str.split(",")[0]
        
        if ":" in portal_str:
            parts = portal_str.rsplit(":", 1)
            return cls(ip=parts[0], port=int(parts[1]))
        return cls(ip=portal_str, port=3260)


@dataclass
class ChapCredentials:
    """CHAP authentication credentials.
    
    Attributes:
        username: CHAP username
        password: CHAP password
    """
    username: str
    password: str


@dataclass
class IscsiLun:
    """iSCSI LUN information.
    
    Attributes:
        lun_id: LUN number
        path: Device path (e.g., /dev/disk/by-path/...)
        size: LUN size in bytes
        wwid: World Wide Identifier
        wwn: World Wide Name
        serial: Device serial number
        vendor: Device vendor
        model: Device model
        type: Device type ('disk', 'mpath', etc.)
        hctl: Host:Channel:Target:Lun address
    """
    lun_id: int
    path: str = ""
    size: int = 0
    wwid: Optional[str] = None
    wwn: Optional[str] = None
    serial: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    type: str = "disk"
    hctl: Optional[str] = None


@dataclass
class IscsiTarget:
    """iSCSI target information.
    
    Attributes:
        iqn: iSCSI Qualified Name (target name)
        portal: Portal address
        luns: List of LUNs available on this target
        alias: Target alias (optional)
    """
    iqn: str
    portal: IscsiPortal
    luns: List[IscsiLun] = field(default_factory=list)
    alias: Optional[str] = None
    
    @property
    def portal_str(self) -> str:
        """Get portal as string."""
        return str(self.portal)


@dataclass
class IscsiSession:
    """Active iSCSI session information.
    
    Attributes:
        session_id: Session ID (e.g., "1", "2")
        target_iqn: Target IQN
        portal: Portal address
        state: Session state (e.g., "LOGGED_IN")
        host_number: SCSI host number
        persistent: Whether session is persistent
    """
    session_id: str
    target_iqn: str
    portal: IscsiPortal
    state: str = "LOGGED_IN"
    host_number: Optional[int] = None
    persistent: bool = False
    
    @classmethod
    def from_session_line(cls, line: str) -> Optional["IscsiSession"]:
        """Parse session from iscsiadm -m session output line.
        
        Example line formats:
            tcp: [1] 192.168.1.1:3260,1 iqn.2020-01.com.example:target (non-flash)
            tcp: [2] 10.0.0.1:3260,1 iqn.2020-01.com.example:target2
        
        Args:
            line: Line from iscsiadm -m session output
            
        Returns:
            IscsiSession instance or None if parsing fails
        """
        try:
            parts = line.split()
            if len(parts) < 4:
                return None
            
            # Extract session ID from "[N]"
            session_id = parts[1].strip("[]")
            
            # Extract portal (ip:port,tpgt)
            portal_str = parts[2]
            portal = IscsiPortal.from_string(portal_str)
            
            # Extract target IQN
            target_iqn = parts[3]
            
            return cls(
                session_id=session_id,
                target_iqn=target_iqn,
                portal=portal
            )
        except (IndexError, ValueError):
            return None


@dataclass
class DiscoveryResult:
    """iSCSI discovery result.
    
    Attributes:
        portal: Portal that was discovered
        targets: List of discovered targets
        success: Whether discovery succeeded
        error: Error message if discovery failed
    """
    portal: IscsiPortal
    targets: List[IscsiTarget] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class LoginResult:
    """iSCSI login result.
    
    Attributes:
        target: Target that was logged into
        session: Active session after login
        success: Whether login succeeded
        error: Error message if login failed
        disks: List of disk paths discovered after login
    """
    target: IscsiTarget
    session: Optional[IscsiSession] = None
    success: bool = True
    error: Optional[str] = None
    disks: List[str] = field(default_factory=list)
