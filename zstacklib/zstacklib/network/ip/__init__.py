# Copyright (c) ZStack.io, Inc.

"""
Network IP module for ZStack.

This module provides a comprehensive API for IP networking operations,
wrapping pyroute2 to provide a clean, typed interface for:

- IP address management (add, delete, query)
- Network link/interface management (create, delete, configure)
- IP routing (add, delete, query routes)
- Network namespace management
- VXLAN FDB operations
- NIC hardware queries

Example usage:
    >>> from zstacklib.network.ip import query_addresses, add_route
    >>> 
    >>> # Query all IPv4 addresses on eth0
    >>> addrs = query_addresses(ifname='eth0', ip_version=4)
    >>> for addr in addrs:
    ...     print(f"{addr.address}/{addr.prefixlen}")
    >>> 
    >>> # Add a route
    >>> add_route('192.168.1.0/24', 4, via='10.0.0.1')

Dependencies:
    - pyroute2: For netlink operations
    - zstacklib.utils.bash: For shell command execution
    - zstacklib.utils.lock: For thread-safe operations
"""

# Exceptions
from .exceptions import (
    InvalidIpAddress,
    InvalidIpVersion,
    InvalidScope,
    IpRouteError,
    NamespaceAlreadyExists,
    NoSuchLinkDevice,
    NoSuchNamespace,
)

# Data models
from .models import (
    IP_VERSION_FAMILY_MAP,
    IpAddr,
    IpLink,
    IpRoute,
)

# IP address classes
from .address import (
    IpAddress,
    Ipv6Address,
    get_link_local_address,
    netmask_to_cidr,
    remove_zero_from_mac_address,
    removeZeroFromMacAddress,  # backward compat
)

# Utility functions
from .utils import (
    check_index_and_ifname,
    check_ip_version,
    get_device_index,
    get_iproute,
    get_prefix_len_by_netmask,
    get_scope_name,
    is_device_ifname_exists,
    is_device_index_exists,
    is_ipv4,
    is_ipv6,
    is_namespace_exists,
    query_index_by_ifname,
)

# Address operations
from .addr import (
    add_address,
    add_address_no_error,
    delete_address,
    delete_address_no_error,
    flush_address,
    flush_address_no_error,
    is_addresses_exists,
    query_addresses,
    query_addresses_by_ifname,
    query_addresses_by_ip,
    query_addresses_by_scope,
)

# Link operations
from .link import (
    add_link,
    add_link_no_error,
    delete_link,
    delete_link_no_error,
    query_link,
    query_links,
    query_links_use_namespace,
    set_link_attribute,
    set_link_attribute_no_error,
    set_link_down,
    set_link_down_no_error,
    set_link_up,
    set_link_up_no_error,
)

# Route operations
from .route import (
    add_route,
    delete_route,
    get_routes,
    get_routes_by_ip,
    show_routes,
)

# Namespace operations
from .namespace import (
    NETNS_RUN_DIR,
    add_namespace,
    add_namespace_no_error,
    create_namespace,  # backward compat
    delete_namespace,
    delete_namespace_if_exists,
    delete_namespace_no_error,
    list_namespace_pids,
    query_all_namespaces,
    remove_namespace,  # backward compat
)

# FDB operations
from .fdb import (
    add_fdb_entry,
    batch_populate_vxlan_fdbs,
    del_fdb_entry,
    delete_fdb_entry,  # backward compat
)

# NIC utilities
from .nic import (
    get_host_physical_nics,
    get_host_physicl_nics,  # backward compat (typo in original)
    get_namespace_id,
    get_nic_driver_type,
    get_nic_supported_max_speed,
    get_smart_nic_pcis,
    get_smart_nic_representors,
    get_smart_nics_interfaces,
    is_sriov_vf_nic,
    is_sriovVf_nic,  # backward compat
)

# Decorators (for advanced usage)
from .decorators import (
    log_iproute_call,
    no_error_do,
)

__all__ = [
    # Exceptions
    'InvalidIpAddress',
    'InvalidIpVersion',
    'InvalidScope',
    'IpRouteError',
    'NamespaceAlreadyExists',
    'NoSuchLinkDevice',
    'NoSuchNamespace',
    
    # Models
    'IP_VERSION_FAMILY_MAP',
    'IpAddr',
    'IpLink',
    'IpRoute',
    
    # IP Address classes
    'IpAddress',
    'Ipv6Address',
    'get_link_local_address',
    'netmask_to_cidr',
    'remove_zero_from_mac_address',
    'removeZeroFromMacAddress',
    
    # Utility functions
    'check_index_and_ifname',
    'check_ip_version',
    'get_device_index',
    'get_iproute',
    'get_prefix_len_by_netmask',
    'get_scope_name',
    'is_device_ifname_exists',
    'is_device_index_exists',
    'is_ipv4',
    'is_ipv6',
    'is_namespace_exists',
    'query_index_by_ifname',
    
    # Address operations
    'add_address',
    'add_address_no_error',
    'delete_address',
    'delete_address_no_error',
    'flush_address',
    'flush_address_no_error',
    'is_addresses_exists',
    'query_addresses',
    'query_addresses_by_ifname',
    'query_addresses_by_ip',
    'query_addresses_by_scope',
    
    # Link operations
    'add_link',
    'add_link_no_error',
    'delete_link',
    'delete_link_no_error',
    'query_link',
    'query_links',
    'query_links_use_namespace',
    'set_link_attribute',
    'set_link_attribute_no_error',
    'set_link_down',
    'set_link_down_no_error',
    'set_link_up',
    'set_link_up_no_error',
    
    # Route operations
    'add_route',
    'delete_route',
    'get_routes',
    'get_routes_by_ip',
    'show_routes',
    
    # Namespace operations
    'NETNS_RUN_DIR',
    'add_namespace',
    'add_namespace_no_error',
    'create_namespace',
    'delete_namespace',
    'delete_namespace_if_exists',
    'delete_namespace_no_error',
    'list_namespace_pids',
    'query_all_namespaces',
    'remove_namespace',
    
    # FDB operations
    'add_fdb_entry',
    'batch_populate_vxlan_fdbs',
    'del_fdb_entry',
    'delete_fdb_entry',
    
    # NIC utilities
    'get_host_physical_nics',
    'get_host_physicl_nics',
    'get_namespace_id',
    'get_nic_driver_type',
    'get_nic_supported_max_speed',
    'get_smart_nic_pcis',
    'get_smart_nic_representors',
    'get_smart_nics_interfaces',
    'is_sriov_vf_nic',
    'is_sriovVf_nic',
    
    # Decorators
    'log_iproute_call',
    'no_error_do',
]
