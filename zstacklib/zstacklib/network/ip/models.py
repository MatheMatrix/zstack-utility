# Copyright (c) ZStack.io, Inc.

"""
Data models for IP address, link, and route information.

These classes wrap pyroute2 response data into structured objects
with typed attributes for easier use.
"""

import socket
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pyroute2


# IP version to socket family mapping
IP_VERSION_FAMILY_MAP = {4: socket.AF_INET, 6: socket.AF_INET6}


def _get_scope_name(scope, exception_if_wrong=False):
    # type: (object, bool) -> Optional[object]
    """
    Get the scope name from number or number from name.
    
    Scope mapping:
        0   -> 'universe' (equals to 'global')
        200 -> 'site'
        253 -> 'link'
        254 -> 'host'
        255 -> 'nowhere'
    
    Args:
        scope: Scope as int or string ('universe', 'site', 'link', 'host', 'nowhere')
        exception_if_wrong: If True, raise InvalidScope for invalid values
    
    Returns:
        Scope name (str) if input is int, or scope number (int) if input is str.
        Returns None if scope is invalid and exception_if_wrong is False.
    
    Raises:
        InvalidScope: If scope is invalid and exception_if_wrong is True
    """
    try:
        import pyroute2.netlink.rtnl
        ret = pyroute2.netlink.rtnl.rt_scope.get(scope)
        if ret is None and exception_if_wrong:
            from .exceptions import InvalidScope
            raise InvalidScope(scope)
        return ret
    except ImportError:
        # Fallback mapping when pyroute2 is not available
        _SCOPE_MAP = {
            0: 'universe', 'universe': 0, 'global': 0,
            200: 'site', 'site': 200,
            253: 'link', 'link': 253,
            254: 'host', 'host': 254,
            255: 'nowhere', 'nowhere': 255
        }
        ret = _SCOPE_MAP.get(scope)
        if ret is None and exception_if_wrong:
            from .exceptions import InvalidScope
            raise InvalidScope(scope)
        return ret


class IpAddr(object):
    """
    Represents an IP address assigned to a network interface.
    
    Wraps pyroute2 address query response data with typed attributes.
    
    Attributes:
        index: Interface index
        family: Socket address family (AF_INET or AF_INET6)
        ip_version: IP version (4 or 6)
        prefixlen: Prefix length (CIDR notation)
        address: IP address string
        label: Address label
        ifname: Interface name (alias for label)
        scope: Address scope name
        chunk: Raw pyroute2 response data
    """
    
    def __init__(self, chunk, iproute):
        # type: (Dict[str, Any], Any) -> None
        """
        Initialize IpAddr from pyroute2 response chunk.
        
        Args:
            chunk: Raw response dictionary from pyroute2
            iproute: IPRoute or NetNS instance for additional queries
        """
        self.index = chunk['index']  # type: int
        self.family = chunk['family']  # type: int
        self.ip_version = 4 if chunk['family'] == socket.AF_INET else 6  # type: int
        self.prefixlen = chunk['prefixlen']  # type: int
        self.address = None  # type: Optional[str]
        self.label = ''  # type: str
        self.ifname = ''  # type: str
        self.chunk = chunk  # type: Dict[str, Any]
        
        for attr in chunk['attrs']:
            if attr[0] == 'IFA_ADDRESS':
                self.address = attr[1]
            elif attr[0] == 'IFA_LABEL':
                self.label = attr[1]
                self.ifname = attr[1]
        
        self.scope = _get_scope_name(chunk['scope'])
        
        if not self.ifname:
            try:
                link = iproute.get_links(self.index)[0]
                self.ifname = link.get_attr('IFA_LABEL') or link.get_attr('IFLA_IFNAME')
            except Exception:
                pass
    
    def __repr__(self):
        """Repr."""
        # type: () -> str
        return "IpAddr(%s/%s on %s)" % (self.address, self.prefixlen, self.ifname)


class IpLink(object):
    """
    Represents a network link (interface) device.
    
    Wraps pyroute2 link query response data with typed attributes.
    
    Attributes:
        index: Interface index
        ip_version: IP version (typically 4)
        mac: MAC address (link/ether address)
        ifname: Interface name
        mtu: Maximum transmission unit
        qlen: Transmit queue length
        state: Operational state (e.g., 'UP', 'DOWN')
        qdisc: Queuing discipline
        alias: Interface alias
        allmulticast: Whether allmulticast is enabled
        device_type: Device type (e.g., 'vlan', 'bridge', 'veth')
        broadcast: Broadcast address
        group: Interface group
        chunk: Raw pyroute2 response data
    """
    
    def __init__(self, chunk):
        # type: (Any) -> None
        """
        Initialize IpLink from pyroute2 response chunk.
        
        Args:
            chunk: Raw response from pyroute2 get_links()
        """
        self.index = chunk['index']  # type: int
        self.ip_version = 4 if chunk['family'] == socket.AF_INET else 6  # type: int
        self.mac = chunk.get_attr('IFLA_ADDRESS')  # type: Optional[str]
        self.ifname = chunk.get_attr('IFA_LABEL') or chunk.get_attr('IFLA_IFNAME')  # type: Optional[str]
        self.mtu = chunk.get_attr('IFLA_MTU')  # type: Optional[int]
        self.qlen = chunk.get_attr('IFLA_TXQLEN')  # type: Optional[int]
        self.state = chunk.get_attr('IFLA_OPERSTATE')  # type: Optional[str]
        self.qdisc = chunk.get_attr('IFLA_QDISC')  # type: Any
        self.alias = chunk.get_attr('IFLA_IFALIAS')  # type: Any
        self.device_type = chunk.get_nested('IFLA_LINKINFO', 'IFLA_INFO_KIND')  # type: Optional[str]
        self.broadcast = chunk.get_attr('IFLA_BROADCAST')  # type: Optional[str]
        self.group = chunk.get_attr('IFLA_GROUP')  # type: Optional[int]
        self.chunk = chunk  # type: Any
        
        # Check allmulticast flag
        try:
            import pyroute2.netlink.rtnl.ifinfmsg as ifinfmsg
            self.allmulticast = bool(chunk['flags'] & ifinfmsg.IFF_ALLMULTI)
        except (ImportError, AttributeError, KeyError):
            self.allmulticast = False  # type: bool
    
    def __repr__(self):
        """Repr."""
        # type: () -> str
        return "IpLink(%s, index=%s, mac=%s)" % (self.ifname, self.index, self.mac)


class IpRoute(object):
    """
    Represents an IP routing table entry.
    
    Wraps pyroute2 route query response data with typed attributes.
    
    Attributes:
        family: Socket address family
        ip_version: IP version (4 or 6)
        via_ip: Gateway IP address
        src_ip: Source IP address (preferred source)
        src_len: Source prefix length
        dst_ip: Destination IP address
        dst_len: Destination prefix length
        device_index: Output interface index
        table: Routing table number
        scope: Route scope name
        chunk: Raw pyroute2 response data
    """
    
    def __init__(self, chunk):
        # type: (Any) -> None
        """
        Initialize IpRoute from pyroute2 response chunk.
        
        Args:
            chunk: Raw response from pyroute2 route()
        """
        self.family = chunk['family']  # type: int
        self.ip_version = 4 if chunk['family'] == socket.AF_INET else 6  # type: int
        self.via_ip = chunk.get_attr('RTA_GATEWAY')  # type: Optional[str]
        self.src_ip = chunk.get_attr('RTA_PREFSRC')  # type: Optional[str]
        self.src_len = chunk['src_len']  # type: int
        self.dst_ip = chunk.get_attr('RTA_DST')  # type: Optional[str]
        self.dst_len = chunk['dst_len']  # type: int
        self.device_index = chunk.get_attr('RTA_OIF')  # type: Optional[int]
        self.table = chunk['table']  # type: int
        self.scope = _get_scope_name(chunk['scope'])  # type: Any
        self.chunk = chunk  # type: Any
    
    def get_related_addresses(self, namespace=None):
        # type: (Optional[str]) -> List[IpAddr]
        """
        Get IP addresses associated with this route's output interface.
        
        Args:
            namespace: Network namespace name (None for default)
        
        Returns:
            List of IpAddr objects for the interface
        """
        from .addr import query_addresses
        return query_addresses(index=self.device_index, namespace=namespace)
    
    def get_related_link_device(self, namespace=None):
        # type: (Optional[str]) -> IpLink
        """
        Get the link device for this route's output interface.
        
        Args:
            namespace: Network namespace name (None for default)
        
        Returns:
            IpLink object for the interface
        """
        from .link import query_link
        return query_link(self.device_index, namespace)
    
    def __repr__(self):
        """Repr."""
        # type: () -> str
        dst = "%s/%s" % (self.dst_ip or 'default', self.dst_len) if self.dst_ip or self.dst_len else 'default'
        return "IpRoute(%s via %s dev %s)" % (dst, self.via_ip or 'direct', self.device_index)
