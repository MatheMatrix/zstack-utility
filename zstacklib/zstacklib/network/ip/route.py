# Copyright (c) ZStack.io, Inc.

"""
IP routing operations.

Provides functions for querying, adding, and deleting IP routes.
"""

from typing import Any, Dict, List, Optional, Union

from .models import IpRoute
from .utils import (
    check_ip_version,
    get_iproute,
    query_index_by_ifname,
)
from .models import _get_scope_name


def _make_pyroute2_route_args(namespace, ip_version, ip, ifname, via, table,
                               metric, scope, protocol):
    # type: (Optional[str], Optional[int], Optional[str], Optional[str], Optional[str], Optional[Union[str, int]], Optional[int], Optional[Union[str, int]], Optional[str]) -> Dict[str, Any]
    """
    Build arguments dictionary for pyroute2 route commands.
    
    This is adapted from openstack/neutron.
    
    Args:
        namespace: Network namespace name
        ip_version: IP version (4, 6, or None)
        ip: Source IP or CIDR address
        ifname: Input interface name
        via: Gateway IP address
        table: Routing table number or name
        metric: Route metric (priority)
        scope: Route scope
        protocol: Protocol name
    
    Returns:
        Dictionary of kwargs for pyroute2 route commands
    """
    args = {'family': check_ip_version(ip_version)}  # type: Dict[str, Any]
    
    if not scope:
        scope = 'universe' if via else 'link'
    scope_val = _get_scope_name(scope)
    if scope_val is not None:
        args['scope'] = scope_val
    
    if ip:
        args['dst'] = ip
    if ifname:
        args['oif'] = query_index_by_ifname(ifname, namespace)
    if via:
        args['gateway'] = via
    if table:
        args['table'] = int(table)
    if metric:
        args['priority'] = int(metric)
    if protocol:
        args['proto'] = protocol
    
    return args


def get_routes_by_ip(dst_ip, ip_version=None, namespace=None):
    # type: (str, Optional[int], Optional[str]) -> List[IpRoute]
    """
    Get routes matching a destination IP.
    
    Args:
        dst_ip: Destination IP address
        ip_version: IP version (4 or 6, or None)
        namespace: Network namespace (None for default)
    
    Returns:
        List of IpRoute objects matching the destination
    """
    return get_routes(ip_version=ip_version, namespace=namespace, dst=dst_ip)


def get_routes(ifname=None, ip_version=None, table=None, namespace=None, **kwargs):
    # type: (Optional[str], Optional[int], Optional[Union[str, int]], Optional[str], **Any) -> List[IpRoute]
    """
    Get IP routes matching criteria.
    
    Equivalent to: ip route get [dst] [...]
    
    Args:
        ifname: Output interface name
        ip_version: IP version (4 or 6, or None for all)
        table: Routing table number
        namespace: Network namespace (None for default)
        **kwargs: Additional filter criteria (e.g., dst, src)
    
    Returns:
        List of IpRoute objects
    
    Note:
        This uses pyroute2's 'get' operation which requires a destination.
    """
    kwargs.update(_make_pyroute2_route_args(
        namespace, ip_version, None, ifname, None, table, None, None, None))
    
    with get_iproute(namespace) as ipr:
        return [IpRoute(chunk) for chunk in ipr.route('get', **kwargs)]


def show_routes(ifname=None, ip_version=4, table=None, namespace=None, **kwargs):
    # type: (Optional[str], int, Optional[Union[str, int]], Optional[str], **Any) -> List[IpRoute]
    """
    List IP routes.
    
    Equivalent to: ip route show [...]
    
    Args:
        ifname: Filter by output interface name
        ip_version: IP version (default 4)
        table: Routing table number
        namespace: Network namespace (None for default)
        **kwargs: Additional filter criteria
    
    Returns:
        List of IpRoute objects
    """
    kwargs.update(_make_pyroute2_route_args(
        namespace, ip_version, None, ifname, None, table, None, None, None))
    
    with get_iproute(namespace) as ipr:
        return [IpRoute(chunk) for chunk in ipr.route('show', **kwargs)]


def add_route(ip, ip_version, ifname=None, via=None,
              table=None, metric=None, scope=None, namespace=None, **kwargs):
    # type: (str, int, Optional[str], Optional[str], Optional[Union[str, int]], Optional[int], Optional[Union[str, int]], Optional[str], **Any) -> None
    """
    Add or replace an IP route.
    
    Equivalent to: ip route replace {ip} [via {gateway}] [dev {ifname}] [...]
    
    Args:
        ip: Destination IP or CIDR (e.g., '192.168.1.0/24')
        ip_version: IP version (4 or 6)
        ifname: Output interface name
        via: Gateway IP address
        table: Routing table number
        metric: Route metric (priority)
        scope: Route scope
        namespace: Network namespace (None for default)
        **kwargs: Additional route options
    
    Example:
        >>> add_route('192.168.1.0/24', 4, ifname='eth0')
        >>> add_route('0.0.0.0/0', 4, via='10.0.0.1')
        >>> add_route('10.0.0.0/8', 4, via='192.168.1.1', metric=100)
    """
    kwargs.update(_make_pyroute2_route_args(
        namespace, ip_version, ip, ifname, via, table, metric, scope, 'static'))
    
    with get_iproute(namespace) as ipr:
        ipr.route('replace', **kwargs)


def delete_route(ip, ip_version, ifname=None, via=None,
                 table=None, scope=None, namespace=None, **kwargs):
    # type: (str, int, Optional[str], Optional[str], Optional[Union[str, int]], Optional[Union[str, int]], Optional[str], **Any) -> None
    """
    Delete an IP route.
    
    Equivalent to: ip route delete {ip} [via {gateway}] [dev {ifname}] [...]
    
    Args:
        ip: Destination IP or CIDR
        ip_version: IP version (4 or 6)
        ifname: Output interface name
        via: Gateway IP address
        table: Routing table number
        scope: Route scope
        namespace: Network namespace (None for default)
        **kwargs: Additional route options
    
    Example:
        >>> delete_route('192.168.1.0/24', 4)
        >>> delete_route('0.0.0.0/0', 4, via='10.0.0.1')
    """
    kwargs.update(_make_pyroute2_route_args(
        namespace, ip_version, ip, ifname, via, table, None, scope, None))
    
    with get_iproute(namespace) as ipr:
        ipr.route('delete', **kwargs)
