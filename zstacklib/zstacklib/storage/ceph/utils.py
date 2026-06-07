# Copyright (c) ZStack.io, Inc.

"""
Ceph utility functions.

This module provides utility functions for Ceph cluster detection
and FSID retrieval.
"""

import os
from typing import Optional

from zstacklib.utils.bash import bash_r

from .models import MANUFACTURER_XSKY, MANUFACTURER_SANDSTONE, MANUFACTURER_OPENSOURCE

CEPH_MON_PROTOCOL_PREFIX = 'v'
CEPH_MON_PROTOCOL_SEPARATOR = ':'
CEPH_MON_ADDR_SUFFIX_SEPARATOR = '/'
CEPH_MON_IPV6_BRACKET_PREFIX = '['
CEPH_MON_IPV6_BRACKET_SUFFIX = ']'
ROUTE_PROTOCOL_KERNEL = 'kernel'
ROUTE_MATCH_CMD_FORMAT = "ip route | grep -w '%s' > /dev/null"
ROUTE_KERNEL_MATCH_CMD_FORMAT = 'ip route | grep -w "proto kernel" | grep -w \'%s\' > /dev/null'


def get_fsid(conffile='/etc/ceph/ceph.conf'):
    # type: (str) -> str
    """
    Get the Ceph cluster FSID.
    
    Args:
        conffile: Path to ceph.conf file.
        
    Returns:
        Cluster FSID string.
        
    Note:
        Requires the rados Python library.
    """
    import rados
    with rados.Rados(conffile=conffile) as cluster:
        return cluster.get_fsid()


def is_xsky():
    # type: () -> bool
    """Check if this is an XSKY Ceph installation."""
    return os.path.exists("/usr/bin/xms-cli")


def is_sandstone():
    # type: () -> bool
    """Check if this is a Sandstone Ceph installation."""
    return os.path.exists("/opt/sandstone/bin/sds") or os.path.exists("/var/lib/ceph/bin/ceph")


def get_ceph_manufacturer():
    # type: () -> str
    """
    Detect the Ceph manufacturer/distribution.
    
    Returns:
        One of: "xsky", "sandstone", "open-source"
    """
    if is_xsky():
        return MANUFACTURER_XSKY
    elif is_sandstone():
        return MANUFACTURER_SANDSTONE
    else:
        return MANUFACTURER_OPENSOURCE


def strip_mon_addr_protocol(addr):
    # type: (str) -> str
    protocol, separator, rest = addr.partition(CEPH_MON_PROTOCOL_SEPARATOR)
    if separator and protocol.startswith(CEPH_MON_PROTOCOL_PREFIX) and protocol[1:].isdigit():
        return rest
    return addr


def extract_mon_host(addr):
    # type: (Optional[str]) -> Optional[str]
    if not addr:
        return None

    addr = strip_mon_addr_protocol(addr.strip())
    if addr.startswith(CEPH_MON_IPV6_BRACKET_PREFIX):
        end = addr.find(CEPH_MON_IPV6_BRACKET_SUFFIX)
        if end > 0:
            return addr[1:end]
        return addr[1:]

    has_addr_suffix = CEPH_MON_ADDR_SUFFIX_SEPARATOR in addr
    addr_without_suffix = addr.split(CEPH_MON_ADDR_SUFFIX_SEPARATOR, 1)[0]
    if CEPH_MON_PROTOCOL_SEPARATOR not in addr_without_suffix:
        return addr_without_suffix

    host, separator, port = addr_without_suffix.rpartition(CEPH_MON_PROTOCOL_SEPARATOR)
    if addr_without_suffix.count(CEPH_MON_PROTOCOL_SEPARATOR) == 1:
        return host
    if has_addr_suffix and separator and port.isdigit():
        return host
    return addr_without_suffix


def get_mon_addr(monmap, route_protocol=None):
    # type: (str, Optional[str]) -> Optional[str]
    """
    Find a monitor address that is routable from this host.
    
    Args:
        monmap: JSON string containing monitor map.
        route_protocol: Optional route protocol filter ("kernel" or None).
        
    Returns:
        Routable monitor address or None.
    """
    import zstacklib.utils.jsonobject as jsonobject
    
    for mon in jsonobject.loads(monmap).mons:
        addr = extract_mon_host(mon.addr)
        if addr is None:
            continue

        cmd = ''
        if route_protocol is None:
            cmd = ROUTE_MATCH_CMD_FORMAT % addr
        elif route_protocol == ROUTE_PROTOCOL_KERNEL:
            cmd = ROUTE_KERNEL_MATCH_CMD_FORMAT % addr
        if cmd == '':
            return None
        if bash_r(cmd) == 0:
            return addr
    return None


def normalize_install_path(path):
    # type: (str) -> str
    """
    Normalize a Ceph install path by removing the ceph:// prefix.
    
    Args:
        path: Install path (may have ceph:// prefix).
        
    Returns:
        Normalized path without prefix.
    """
    prefix = 'ceph://'
    return path[len(prefix):] if path.startswith(prefix) else path
