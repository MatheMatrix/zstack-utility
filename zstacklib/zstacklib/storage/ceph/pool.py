# Copyright (c) ZStack.io, Inc.

"""
Ceph pool capacity management.

This module provides functions for querying Ceph pool capacity
and OSD information.
"""

from typing import List, Optional, Set

import zstacklib.utils.jsonobject as jsonobject
from zstacklib.utils import shell

from .models import CephPoolCapacity, CephOsdCapacity, MANUFACTURER_OPENSOURCE
from .utils import get_ceph_manufacturer


def get_pools_capacity():
    # type: () -> List[CephPoolCapacity]
    """
    Get capacity information for all Ceph pools.
    
    Queries the Ceph cluster for pool information including:
    - Pool type (replicated or erasure coded)
    - CRUSH rules and OSD associations
    - Capacity metrics (total, available, used)
    
    Returns:
        List of CephPoolCapacity objects with detailed capacity info.
    """
    result = []  # type: List[CephPoolCapacity]
    
    o = shell.call('ceph osd dump -f json')
    df = jsonobject.loads(o)
    if not df.pools:
        return result
    
    for pool in df.pools:
        crush_rule = pool.crush_ruleset if pool.crush_ruleset is not None else pool.crush_rule
        
        if pool.type == 1:
            # Replicated pool
            pool_capacity = CephPoolCapacity(
                pool.pool_name, pool.size, crush_rule, "Copy", 1.0 / pool.size
            )
        elif pool.type == 3:
            # Erasure coded pool
            prof = shell.call('ceph osd erasure-code-profile get %s -f json' % pool.erasure_code_profile)
            jprof = jsonobject.loads(prof)
            if not jprof.k or not jprof.m:
                raise Exception('unexpected erasure-code-profile for pool: %s' % pool.pool_name)
            k = int(jprof.k)
            m = int(jprof.m)
            utilization = float(k) / (k + m)
            pool_capacity = CephPoolCapacity(
                pool.pool_name, pool.size, crush_rule, "ErasureCode", utilization
            )
        else:
            raise Exception("unexpected pool type: %s:%d" % (pool.pool_name, pool.type))
        
        result.append(pool_capacity)
    
    # Fill crush_rule_item_name
    _fill_crush_rule_names(result)
    
    # Fill crush_item_osds
    _fill_crush_osds(result)
    
    # Fill capacity metrics
    _fill_capacity_metrics(result)
    
    return result


def _fill_crush_rule_names(pools):
    # type: (List[CephPoolCapacity]) -> None
    """Fill CRUSH rule item names for each pool."""
    o = shell.call('ceph osd crush rule dump -f json')
    crush_rules = jsonobject.loads(o)
    if not crush_rules:
        return
    
    for pool_capacity in pools:
        if pool_capacity.crush_rule_set is None:
            continue
        
        for crush_rule in crush_rules:
            if crush_rule.rule_id == pool_capacity.crush_rule_set:
                # Set crush rule name
                for step in crush_rule.steps:
                    if step.op == "take":
                        pool_capacity.crush_rule_item_names.append(step.item_name)


def _fill_crush_osds(pools):
    # type: (List[CephPoolCapacity]) -> None
    """Fill CRUSH item OSDs for each pool."""
    o = shell.call('ceph osd tree -f json')
    # In the open source Ceph 10 version, the value returned by executing
    # 'ceph osd tree -f json' might have '-nan', causing json parsing to fail.
    o = o.replace("-nan", "\"\"")
    tree = jsonobject.loads(o)
    if not tree.nodes:
        return
    
    def find_node_by_id(node_id):
        for node in tree.nodes:
            if node.id == node_id:
                return node
        return None
    
    def find_all_childs(node):
        childs = []
        if not node.children:
            return childs
        
        for child_id in node.children:
            child = find_node_by_id(child_id)
            if not child:
                continue
            childs.append(child)
            if child.children:
                grandson_childs = find_all_childs(child)
                childs.extend(grandson_childs)
        return childs
    
    for pool_capacity in pools:
        if not pool_capacity.crush_rule_item_names:
            continue
        
        osd_nodes = set()  # type: Set[str]
        for node in tree.nodes:
            if node.name not in pool_capacity.crush_rule_item_names:
                continue
            if not node.children:
                continue
            
            nodes = find_all_childs(node)
            for n in nodes:
                if n.type != "osd":
                    continue
                osd_nodes.add(n.name)
        pool_capacity.crush_item_osds = sorted(osd_nodes)


def _fill_capacity_metrics(pools):
    # type: (List[CephPoolCapacity]) -> None
    """Fill capacity metrics for each pool based on OSD data."""
    o = shell.call('ceph osd df -f json')
    # In the open source Ceph 10 version, the value returned by executing
    # 'ceph osd df -f json' might have '-nan', causing json parsing to fail.
    o = o.replace("-nan", "\"\"")
    manufacturer = get_ceph_manufacturer()
    osds = jsonobject.loads(o)
    if not osds.nodes:
        return
    
    for pool_capacity in pools:
        if not pool_capacity.crush_item_osds:
            continue
        
        for osd_name in pool_capacity.crush_item_osds:
            for osd in osds.nodes:
                if osd.name != osd_name:
                    continue
                pool_capacity.crush_item_osds_total_size += osd.kb * 1024
                pool_capacity.available_capacity += osd.kb_avail * 1024
                pool_capacity.used_capacity += osd.kb_used * 1024
                if manufacturer == MANUFACTURER_OPENSOURCE:
                    pool_capacity.related_osd_capacity[osd_name] = CephOsdCapacity(
                        osd.kb * 1024, osd.kb_avail * 1024, osd.kb_used * 1024
                    )
        
        if not pool_capacity.disk_utilization:
            continue
        
        if pool_capacity.crush_item_osds_total_size:
            pool_capacity.pool_total_size = int(
                pool_capacity.crush_item_osds_total_size * pool_capacity.disk_utilization
            )
        if pool_capacity.available_capacity:
            pool_capacity.available_capacity = int(
                pool_capacity.available_capacity * pool_capacity.disk_utilization
            )
        if pool_capacity.used_capacity:
            pool_capacity.used_capacity = int(
                pool_capacity.used_capacity * pool_capacity.disk_utilization
            )
