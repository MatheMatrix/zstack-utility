"""Physical Volume (PV) operations for LVM.

This module provides functions for managing LVM physical volumes including:
- Listing PVs in a volume group
- Getting PV information by UUID or path
- Checking PV status and validity
- Managing PV allocation strategies
"""


import os
import random
from typing import Optional, List, Dict, Callable

from zstacklib.utils import bash, linux, log
from zstacklib.storage.lvm.models import PhysicalVolume, BlockDevice, PvNotFoundError

logger = log.get_logger(__name__)


def list_pvs(vg_uuid: str, timeout: int = 10) -> Optional[List[str]]:
    """List all physical volume paths in a volume group.
    
    Args:
        vg_uuid: Volume group UUID/name
        timeout: Command timeout in seconds
        
    Returns:
        List of PV paths, or None if query failed
    """
    r, o = bash.bash_ro(
        f"timeout -s SIGKILL {timeout} pvs --noheading --nolocking -t -Svg_name={vg_uuid} -oname"
    )
    if r != 0:
        return None
    
    paths = [s.strip() for s in o.splitlines()]
    return [p for p in paths if p]


def get_pv_name_by_uuid(pv_uuid: str, timeout: int = 10) -> str:
    """Get physical volume path by its UUID.
    
    Args:
        pv_uuid: Physical volume UUID
        timeout: Command timeout in seconds
        
    Returns:
        PV device path, or empty string if not found
    """
    return bash.bash_o(
        f"timeout -s SIGKILL {timeout} pvs --noheading --nolocking -t -oname -Spv_uuid={pv_uuid}"
    ).strip()


def get_pv_uuid_by_path(pv_path: str, timeout: int = 10) -> str:
    """Get physical volume UUID by its path.
    
    Args:
        pv_path: Physical volume device path
        timeout: Command timeout in seconds
        
    Returns:
        PV UUID, or empty string if not found
    """
    return bash.bash_o(
        f"timeout -s SIGKILL {timeout} pvs --noheading --nolocking -t -ouuid {pv_path}"
    ).strip()


@bash.in_bash
@linux.retry(times=5, sleep_time=2)
def add_pv(vg_uuid: str, disk_path: str, metadata_size: str) -> None:
    """Add a physical volume to an existing volume group.
    
    Args:
        vg_uuid: Volume group UUID/name
        disk_path: Device path to add
        metadata_size: Metadata area size (e.g., "16M")
        
    Raises:
        Exception: If the disk was not added successfully
    """
    bash.bash_errorout(f"vgextend --metadatasize {metadata_size} {vg_uuid} {disk_path}")
    if bash.bash_r(f"pvs --nolocking -t --readonly {disk_path} | grep {vg_uuid}"):
        raise Exception(f"disk {disk_path} not added to vg {vg_uuid} after vgextend")


def check_pv_status(vg_uuid: str, timeout: int = 10) -> tuple[bool, str]:
    """Check physical volume status in a volume group.
    
    Validates that all PVs in the VG are healthy and accessible.
    Also checks VG attributes for proper configuration.
    
    Args:
        vg_uuid: Volume group UUID/name
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (is_healthy, error_message)
    """
    r, o, e = bash.bash_roe(
        f"timeout -s SIGKILL {timeout} pvs --noheading --nolocking -t -Svg_name={vg_uuid} -oname,missing"
    )
    if len(o) == 0 or r != 0:
        s = f"can not find shared block in shared block group {vg_uuid}, detail: [return_code: {r}, stdout: {o}, stderr: {e}]"
        logger.warn(s)
        return False, s
        
    for pvs_out in o.splitlines():
        if "unknown" in pvs_out:
            s = f"disk in shared block group {vg_uuid} missing"
            logger.warn(f"{s}, details: {o}")
            return False, s
        if "missing" in pvs_out:
            pv_name = pvs_out.strip().split(" ")[0]
            s = f"disk {pv_name} in shared block group {vg_uuid} exists but state is missing"
            logger.warn(f"{s}, details: {o}")
            return False, s

    return _validate_vg_attributes(vg_uuid, timeout)


def _validate_vg_attributes(vg_uuid: str, timeout: int) -> tuple[bool, str]:
    vg_timeout = max(10, timeout)
    health = bash.bash_o(
        f'timeout -s SIGKILL {vg_timeout} vgs -oattr --nolocking -t --noheadings --shared {vg_uuid}'
    ).strip()
    
    if health == "":
        logger.warn("can not get proper attr of vg, return false")
        return False, f"primary storage {vg_uuid} attr get error, expect 'wz--ns' got '{health}'"

    if health[0] != "w":
        return False, f"primary storage {vg_uuid} permission error, expect 'w', got '{health}'"

    if health[1] != "z":
        return False, f"primary storage {vg_uuid} resizeable error, expect 'z', got '{health}'"

    if len(health) > 3 and health[3] != "-":
        return False, f"primary storage {vg_uuid} partial error, expect '-', got '{health}'"

    if len(health) > 5 and health[5] != "s":
        return False, f"primary storage {vg_uuid} shared mode error, expect 's', got '{health}'"

    return True, ""


_pv_allocate_strategy: Dict[str, str] = {}


def update_pv_allocate_strategy(vg_uuid: str, strategy: str) -> None:
    """Update the PV allocation strategy for a volume group.
    
    Args:
        vg_uuid: Volume group UUID/name
        strategy: Allocation strategy ('none', 'minLvCounts', 'maxFreeSize')
    """
    global _pv_allocate_strategy
    _pv_allocate_strategy[vg_uuid] = strategy


def get_allocated_pvs(vg_name: str) -> List[str]:
    """Get PVs sorted according to the configured allocation strategy.
    
    Args:
        vg_name: Volume group name
        
    Returns:
        List of PV paths in allocation order, or empty list if no strategy
    """
    global _pv_allocate_strategy
    strategy = _pv_allocate_strategy.get(vg_name, "none")

    if strategy == "none":
        return []
    elif strategy == "minLvCounts":
        return get_volume_lv_sorted_pvs(vg_name)
    elif strategy == "maxFreeSize":
        return get_free_sorted_pvs(vg_name)
    else:
        return []


@bash.in_bash
def get_volume_lv_sorted_pvs(vg_name: str, image_tag: str = "zs::sharedblock::image") -> List[str]:
    """Get PVs sorted by number of volume LVs on each (ascending).
    
    Distributes new volumes across PVs to balance load.
    
    Args:
        vg_name: Volume group name
        image_tag: Tag to exclude from counting
        
    Returns:
        List of PV paths sorted by LV count
    """
    cmd = f'''pvs --segments --noheadings --nolocking -t \
-S 'vg_name={vg_name},seg_type!=free,lv_tags!={image_tag},lv_tags!=""' \
-o pv_name,lv_name -O pv_name,lv_name | uniq | awk '{{count[$1]++;}} END {{for(pv in count) {{print pv" "count[pv]}}}}'
'''
    r, o = bash.bash_ro(cmd)
    all_pvs = list_pvs(vg_name) or []
    lv_counts = dict(zip(all_pvs, [0] * len(all_pvs)))
    
    for l in o.strip().splitlines():
        parts = l.split()
        if len(parts) >= 2:
            pv_name, lv_count = parts[0], parts[1]
            lv_counts[pv_name] = int(lv_count)

    return sorted(lv_counts.keys(), key=lambda lv: lv_counts[lv] + random.random())


@bash.in_bash
def get_free_sorted_pvs(vg_name: str) -> List[str]:
    """Get PVs sorted by free space (descending).
    
    Args:
        vg_name: Volume group name
        
    Returns:
        List of PV paths sorted by free space
    """
    r, o = bash.bash_ro(
        f"pvs --nolocking -t --noheadings -S 'vg_name={vg_name}' -o pv_name -O-pv_free --rows"
    )
    if r == 0:
        return o.strip().split()
    return []


@bash.in_bash
def get_lv_location(lv_path: str) -> List[str]:
    """Get the PVs where an LV's extents are located.
    
    Args:
        lv_path: Logical volume path
        
    Returns:
        List of PV paths containing the LV's data
    """
    r, o = bash.bash_ro(
        f'''lvs --nolocking -t --noheadings -o devices {lv_path} | awk -F '(' '!pv[$1]++{{printf " "$1}}' '''
    )
    if r == 0:
        return o.strip().split()
    return []


def get_lv_affinity_sorted_pvs(lv_path: str, update_strategy: bool = False) -> Optional[List[str]]:
    """Get PVs sorted with affinity to an existing LV's location.
    
    Prioritizes PVs where the LV already has extents, useful for extending.
    
    Args:
        lv_path: Logical volume path
        update_strategy: Whether to update allocation strategy first
        
    Returns:
        List of PV paths with affinity-based ordering, or None if no strategy configured
    """
    vg_name = lv_path.split(os.sep)[-2]
    lv_name = lv_path.split(os.sep)[-1]
    
    total_pvs = get_allocated_pvs(vg_name)
    if not total_pvs:
        return None

    locations = get_lv_location(os.path.join("/dev", vg_name, lv_name))
    rest_pvs = [p for p in total_pvs if p not in locations]
    return locations + rest_pvs
