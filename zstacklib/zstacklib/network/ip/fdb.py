# Copyright (c) ZStack.io, Inc.

"""
Forwarding Database (FDB) operations for VXLAN.

Provides functions for managing FDB entries on VXLAN devices.
"""

import pyroute2
from typing import List, Optional

from zstacklib.utils import log

from .decorators import log_iproute_call
from .utils import get_iproute, query_index_by_ifname

logger = log.get_logger(__name__)


@log_iproute_call("populate vxlan fdbs")
def batch_populate_vxlan_fdbs(ifnames, lladdr, dsts):
    # type: (List[str], str, List[str]) -> None
    """
    Batch add FDB entries for VXLAN devices.
    
    Adds FDB entries for each (ifname, dst) combination, allowing
    efficient population of VXLAN forwarding databases.
    
    Args:
        ifnames: List of VXLAN interface names
        lladdr: Link-layer (MAC) address for the FDB entry
        dsts: List of destination IP addresses (VTEPs)
    
    Example:
        >>> batch_populate_vxlan_fdbs(['vxlan100', 'vxlan200'],
        ...                           '00:00:00:00:00:00',
        ...                           ['10.0.0.1', '10.0.0.2'])
    """
    with get_iproute(None) as ipr:
        if_name_index_map = {}  # type: dict
        for ifname in ifnames:
            ifindex = query_index_by_ifname(ifname.strip())
            if ifindex is None:
                continue
            if_name_index_map[ifname] = ifindex
        
        ipb = pyroute2.IPBatch()
        for dst in dsts:
            for ifname in ifnames:
                if ifname in if_name_index_map:
                    ipb.fdb('append', ifindex=if_name_index_map[ifname],
                            lladdr=lladdr, dst=dst)
            data = ipb.batch
            ipb.reset()
            ipr.sendto(data, (0, 0))
        ipb.close()


def add_fdb_entry(ifname, lladdr):
    # type: (str, str) -> None
    """
    Add an FDB entry to a network interface.
    
    Args:
        ifname: Interface name
        lladdr: Link-layer (MAC) address
    
    Note:
        Errors are logged but not raised.
    """
    with get_iproute(None) as ipr:
        ifindex = query_index_by_ifname(ifname.strip())
        if ifindex is None:
            logger.debug("Cannot get ifIndex of %s" % ifname)
            return
        
        try:
            ipr.fdb('add', ifindex=ifindex, lladdr=lladdr)
            logger.debug("Added FDB entry: mac=%s interface=%s" % (lladdr, ifname))
        except Exception as e:
            logger.debug("Failed to add FDB entry: mac=%s interface=%s, error=%s" %
                         (lladdr, ifname, e))


def del_fdb_entry(ifname, lladdr):
    # type: (str, str) -> None
    """
    Delete an FDB entry from a network interface.
    
    Args:
        ifname: Interface name
        lladdr: Link-layer (MAC) address
    
    Note:
        Errors are logged but not raised.
    """
    with get_iproute(None) as ipr:
        ifindex = query_index_by_ifname(ifname.strip())
        if ifindex is None:
            logger.debug("Cannot get ifIndex of %s" % ifname)
            return
        
        try:
            ipr.fdb('del', ifindex=ifindex, lladdr=lladdr)
            logger.debug("Deleted FDB entry: mac=%s interface=%s" % (lladdr, ifname))
        except Exception as e:
            logger.debug("Failed to delete FDB entry: mac=%s interface=%s, error=%s" %
                         (lladdr, ifname, e))


# Backward compatibility aliases
delete_fdb_entry = del_fdb_entry
