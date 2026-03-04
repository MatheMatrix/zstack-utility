# Copyright (c) ZStack.io, Inc.

"""
IP address operations.

Provides functions for querying, adding, deleting, and flushing
IP addresses on network interfaces.
"""

from typing import Any, Dict, List, Optional, Union

from .decorators import log_iproute_call, no_error_do
from .exceptions import NoSuchLinkDevice
from .models import IpAddr, _get_scope_name
from .utils import (
    check_index_and_ifname,
    check_ip_version,
    get_device_index,
    get_iproute,
)


def query_addresses(namespace=None, **kwargs):
    # type: (Optional[str], **Any) -> List[IpAddr]
    """
    Query IP addresses with optional filtering.
    
    Args:
        namespace: Network namespace (None for default)
        **kwargs: Filter conditions:
            - ifname: Device name
            - scope: Address scope ('host', 'universe', 'link', etc.)
            - ip: IP address to match
            - ip_version: 4 or 6, or None for all
            - index: Device index
    
    Returns:
        List of IpAddr objects matching the criteria
    
    Example:
        >>> addresses = query_addresses()  # All addresses
        >>> addresses = query_addresses(ifname='eth0')  # Addresses on eth0
        >>> addresses = query_addresses(ip_version=4)  # IPv4 only
    """
    with get_iproute(namespace) as ipr:
        if kwargs:
            # Convert ifname to index (pyroute2 doesn't support ifname directly)
            if 'ifname' in kwargs:
                device_index = check_index_and_ifname(
                    kwargs['ifname'], kwargs.get('index'), ipr, False
                )
                if device_index == 0:
                    return []
                kwargs['index'] = device_index
                del kwargs['ifname']
            
            # Convert scope string to int
            if 'scope' in kwargs and isinstance(kwargs['scope'], str):
                kwargs['scope'] = _get_scope_name(kwargs['scope'], True)
            
            # Rename 'ip' to 'address' for pyroute2
            if 'ip' in kwargs and isinstance(kwargs['ip'], str):
                kwargs['address'] = kwargs['ip']
                del kwargs['ip']
            
            # Convert ip_version to family
            if 'ip_version' in kwargs:
                kwargs['family'] = check_ip_version(kwargs['ip_version'])
                del kwargs['ip_version']
        
        return [IpAddr(chunk, ipr) for chunk in ipr.get_addr(**kwargs)]


def is_addresses_exists(namespace=None, **kwargs):
    # type: (Optional[str], **Any) -> bool
    """
    Check if any addresses exist matching the criteria.
    
    Args:
        namespace: Network namespace (None for default)
        **kwargs: Filter conditions (see query_addresses)
    
    Returns:
        True if any matching addresses exist
    """
    return len(query_addresses(namespace, **kwargs)) > 0


def query_addresses_by_ifname(ifname, namespace=None):
    # type: (str, Optional[str]) -> List[IpAddr]
    """
    Query IP addresses for a specific interface.
    
    Args:
        ifname: Interface name
        namespace: Network namespace (None for default)
    
    Returns:
        List of IpAddr objects for the interface
    """
    return query_addresses(namespace, ifname=ifname)


def query_addresses_by_scope(scope, namespace=None):
    # type: (Union[str, int], Optional[str]) -> List[IpAddr]
    """
    Query IP addresses by scope.
    
    Args:
        scope: Scope as string ('host', 'universe', 'link') or int
        namespace: Network namespace (None for default)
    
    Returns:
        List of IpAddr objects with the specified scope
    """
    return query_addresses(namespace, scope=scope)


def query_addresses_by_ip(ip, ip_version=None, namespace=None):
    # type: (str, Optional[int], Optional[str]) -> List[IpAddr]
    """
    Query addresses matching a specific IP.
    
    Args:
        ip: IP address to match
        ip_version: 4 or 6, or None to auto-detect
        namespace: Network namespace (None for default)
    
    Returns:
        List of IpAddr objects with the specified IP
    """
    return query_addresses(namespace, address=ip, ip_version=ip_version)


@log_iproute_call("address add")
def add_address(ip, prefixlen, ip_version, ifname_or_index,
                broadcast=None, scope=None, namespace=None):
    # type: (str, int, int, Union[str, int], Optional[str], Optional[Union[str, int]], Optional[str]) -> None
    """
    Add an IP address to an interface.
    
    Equivalent to: ip address add {ip}/{prefixlen} dev {ifname} [broadcast {broadcast}] [scope {scope}]
    
    Args:
        ip: IP address to add
        prefixlen: Prefix length (CIDR notation, e.g., 24 for /24)
        ip_version: IP version (4 or 6)
        ifname_or_index: Interface name or index
        broadcast: Broadcast address (optional)
        scope: Address scope (optional)
        namespace: Network namespace (None for default)
    
    Raises:
        Exception: If ip or prefixlen is None
        NoSuchLinkDevice: If the interface does not exist
    """
    if ip is None or prefixlen is None:
        raise Exception('IP and prefixlen cannot be None')
    
    family = check_ip_version(ip_version, none_is_supported=False)
    
    with get_iproute(namespace) as ipr:
        index = get_device_index(ifname_or_index, ipr)
        if scope:
            scope = _get_scope_name(scope, True)
        ipr.addr('add', index=index, address=ip, prefixlen=prefixlen,
                 broadcast=broadcast, scope=scope, family=family)


@no_error_do
def add_address_no_error(*args, **kwargs):
    # type: (*Any, **Any) -> bool
    """
    Add an IP address, returning False on error instead of raising.
    
    See add_address for arguments.
    
    Returns:
        True on success, False on error
    """
    add_address(*args, **kwargs)
    return True


@log_iproute_call("address delete")
def delete_address(ip, prefixlen, ip_version, ifname_or_index, namespace=None):
    # type: (str, int, int, Union[str, int], Optional[str]) -> None
    """
    Delete an IP address from an interface.
    
    Equivalent to: ip address delete {ip}/{prefixlen} dev {ifname}
    
    Args:
        ip: IP address to delete
        prefixlen: Prefix length
        ip_version: IP version (4 or 6)
        ifname_or_index: Interface name or index
        namespace: Network namespace (None for default)
    
    Raises:
        Exception: If ip or prefixlen is None
        NoSuchLinkDevice: If the interface does not exist
    """
    if ip is None or prefixlen is None:
        raise Exception('IP and prefixlen cannot be None')
    
    family = check_ip_version(ip_version)
    
    with get_iproute(namespace) as ipr:
        index = get_device_index(ifname_or_index, ipr)
        ipr.addr('delete', index=index, address=ip, prefixlen=prefixlen, family=family)


@no_error_do
def delete_address_no_error(*args, **kwargs):
    # type: (*Any, **Any) -> bool
    """
    Delete an IP address, returning False on error instead of raising.
    
    See delete_address for arguments.
    
    Returns:
        True on success, False on error
    """
    delete_address(*args, **kwargs)
    return True


@log_iproute_call("address flush")
def flush_address(ifname_or_index, namespace=None):
    # type: (Union[str, int], Optional[str]) -> None
    """
    Flush all IP addresses from an interface.
    
    Equivalent to: ip address flush dev {ifname}
                   ip netns exec {namespace} ip address flush dev {ifname}
    
    Args:
        ifname_or_index: Interface name or index
        namespace: Network namespace (None for default)
    
    Raises:
        NoSuchLinkDevice: If the interface does not exist
    """
    with get_iproute(namespace) as ipr:
        index = get_device_index(ifname_or_index, ipr)
        ipr.flush_addr(index=index)


@no_error_do
def flush_address_no_error(*args, **kwargs):
    # type: (*Any, **Any) -> bool
    """
    Flush IP addresses, returning False on error instead of raising.
    
    See flush_address for arguments.
    
    Returns:
        True on success, False on error
    """
    flush_address(*args, **kwargs)
    return True
