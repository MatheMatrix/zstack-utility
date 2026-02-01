# Copyright (c) ZStack.io, Inc.

"""
Utility functions for IP route operations.

Provides helper functions for working with pyroute2, including
connection management, IP version handling, and device lookups.
"""

import re
import socket
from typing import Any, Dict, Optional, Union

from zstacklib.utils import lock

from .exceptions import (
    InvalidIpVersion,
    InvalidScope,
    NoSuchLinkDevice,
    NoSuchNamespace,
)
from .models import IP_VERSION_FAMILY_MAP, _get_scope_name


@lock.lock("subprocess.popen")
def get_iproute(namespace=None):
    # type: (Optional[str]) -> Any
    """
    Get a pyroute2 IPRoute or NetNS instance.
    
    Returns an IPRoute instance for the current namespace, or a NetNS
    instance for a specific network namespace.
    
    Args:
        namespace: Network namespace name (None for default namespace)
    
    Returns:
        pyroute2.IPRoute or pyroute2.NetNS instance (context manager)
    
    Raises:
        NoSuchNamespace: If the specified namespace does not exist
    
    Example:
        >>> with get_iproute() as ipr:
        ...     links = ipr.get_links()
        >>> with get_iproute('my_namespace') as ipr:
        ...     links = ipr.get_links()
    """
    import pyroute2
    
    if namespace is not None:
        # Check if namespace exists before trying to connect
        if is_namespace_exists(namespace):
            return pyroute2.NetNS(namespace)
        raise NoSuchNamespace(namespace)
    else:
        return pyroute2.IPRoute()


def is_namespace_exists(namespace):
    # type: (str) -> bool
    """
    Check if a network namespace exists.
    
    Args:
        namespace: Namespace name to check
    
    Returns:
        True if the namespace exists, False otherwise
    """
    import pyroute2.netns
    
    for name in pyroute2.netns.listnetns():
        if name == namespace:
            return True
    return False


def check_ip_version(ip_version, none_is_supported=True, exception_if_wrong=True):
    # type: (Optional[int], bool, bool) -> Optional[int]
    """
    Validate and convert IP version to socket address family.
    
    Args:
        ip_version: IP version (4 or 6) or None
        none_is_supported: If True, None is a valid value
        exception_if_wrong: If True, raise InvalidIpVersion for invalid values
    
    Returns:
        Socket address family (socket.AF_INET or socket.AF_INET6) or None
    
    Raises:
        InvalidIpVersion: If ip_version is invalid and exception_if_wrong is True
    """
    if ip_version is None:
        if none_is_supported or not exception_if_wrong:
            return None
        else:
            raise InvalidIpVersion(ip_version)
    
    ret = IP_VERSION_FAMILY_MAP.get(ip_version)
    if ret is None and exception_if_wrong:
        raise InvalidIpVersion(ip_version)
    return ret


def get_device_index(ifname_or_index, iproute, exception_if_wrong=True):
    # type: (Union[str, int], Any, bool) -> Optional[int]
    """
    Get device index from interface name or validate existing index.
    
    Args:
        ifname_or_index: Interface name (str) or index (int)
        iproute: IPRoute or NetNS instance
        exception_if_wrong: If True, raise NoSuchLinkDevice on error
    
    Returns:
        Device index (int) or None if not found
    
    Raises:
        NoSuchLinkDevice: If device not found and exception_if_wrong is True
    """
    if isinstance(ifname_or_index, int):
        return ifname_or_index
    elif isinstance(ifname_or_index, str):
        ret = query_index_by_ifname(ifname_or_index, iproute=iproute)
        if ret or not exception_if_wrong:
            return ret
    
    if exception_if_wrong:
        raise NoSuchLinkDevice(ifname_or_index if isinstance(ifname_or_index, str) else None,
                                ifname_or_index if isinstance(ifname_or_index, int) else None)
    return None


def query_index_by_ifname(ifname, namespace=None, iproute=None):
    # type: (str, Optional[str], Any) -> Optional[int]
    """
    Get device index by interface name.
    
    Args:
        ifname: Interface name
        namespace: Network namespace (None for default)
        iproute: Optional existing IPRoute instance
    
    Returns:
        Device index or None if not found
    """
    if iproute is not None:
        return _query_index_by_ifname_internal(ifname, iproute)
    
    with get_iproute(namespace) as ipr:
        return _query_index_by_ifname_internal(ifname, ipr)


def _query_index_by_ifname_internal(ifname, iproute):
    # type: (str, Any) -> Optional[int]
    """Internal helper to query device index by name."""
    rets = iproute.link_lookup(ifname=ifname)
    return rets[0] if rets else None


def is_device_ifname_exists(ifname, namespace=None):
    # type: (str, Optional[str]) -> bool
    """
    Check if a device with the given interface name exists.
    
    Args:
        ifname: Interface name
        namespace: Network namespace (None for default)
    
    Returns:
        True if device exists, False otherwise
    """
    return query_index_by_ifname(ifname, namespace) is not None


def is_device_index_exists(index, namespace=None):
    # type: (int, Optional[str]) -> bool
    """
    Check if a device with the given index exists.
    
    Args:
        index: Device index
        namespace: Network namespace (None for default)
    
    Returns:
        True if device exists, False otherwise
    """
    with get_iproute(namespace) as ipr:
        return _is_device_index_exists_internal(index, ipr)


def _is_device_index_exists_internal(index, iproute):
    # type: (int, Any) -> bool
    """Internal helper to check if device index exists."""
    rets = iproute.link_lookup(index=index)
    return len(rets) == 1


def check_index_and_ifname(ifname, index, iproute, exception_if_wrong=False):
    # type: (Optional[str], Optional[int], Any, bool) -> int
    """
    Validate and resolve device index from ifname and/or index.
    
    Args:
        ifname: Interface name (optional)
        index: Device index (optional)
        iproute: IPRoute or NetNS instance
        exception_if_wrong: If True, raise NoSuchLinkDevice on error
    
    Returns:
        Valid device index (int), or 0 if invalid
    
    Raises:
        NoSuchLinkDevice: If device not found and exception_if_wrong is True
    """
    if ifname:
        ret = _query_index_by_ifname_internal(ifname, iproute)
        if ret is None and exception_if_wrong:
            raise NoSuchLinkDevice(ifname)
        if index is None:
            return ret if ret else 0
        elif ret != index:
            if exception_if_wrong:
                raise NoSuchLinkDevice(ifname, index, 'ifname and index do not match')
            else:
                return 0
        else:
            return ret
    else:
        if index is None or not _is_device_index_exists_internal(index, iproute):
            if exception_if_wrong:
                if index is None:
                    raise NoSuchLinkDevice(None, None, 'ifname and index cannot both be None')
                else:
                    raise NoSuchLinkDevice(None, index)
            return 0
        return index


def get_prefix_len_by_netmask(netmask):
    # type: (str) -> int
    """
    Convert netmask to prefix length.
    
    Args:
        netmask: Netmask in dotted-decimal notation (e.g., '255.255.255.0')
    
    Returns:
        Prefix length (e.g., 24 for '255.255.255.0')
    """
    packed = socket.inet_aton(netmask)
    # Convert bytes to integer for Python 3 compatibility
    ip_int = 0
    for b in packed:
        if isinstance(b, int):
            ip_int = (ip_int << 8) | b
        else:
            ip_int = (ip_int << 8) | ord(b)
    
    i = 1
    prefix = 0
    while not ip_int & i:
        i = i << 1
        prefix += 1
    return 32 - prefix


def is_ipv4(ip_address):
    # type: (str) -> bool
    """
    Check if an IP address is a valid IPv4 address.
    
    Args:
        ip_address: IP address string
    
    Returns:
        True if valid IPv4, False otherwise
    """
    pattern = re.compile(r'^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)')
    return bool(pattern.match(ip_address))


def is_ipv6(ip_address):
    # type: (str) -> bool
    """
    Check if an IP address is a valid IPv6 address.
    
    Args:
        ip_address: IP address string
    
    Returns:
        True if valid IPv6, False otherwise
    """
    try:
        socket.inet_pton(socket.AF_INET6, ip_address)
        return True
    except socket.error:
        return False


# Re-export for backward compatibility
get_scope_name = _get_scope_name
