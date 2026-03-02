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
        addr = mon.addr.split(':')[0]
        cmd = ''
        if route_protocol is None:
            cmd = 'ip route | grep -w %s > /dev/null' % addr
        elif route_protocol == "kernel":
            cmd = 'ip route | grep -w "proto kernel" | grep -w %s > /dev/null' % addr
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
    return path.replace('ceph://', '')
