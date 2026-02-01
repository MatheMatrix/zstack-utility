"""Volume Group (VG) operations for LVM.

This module provides functions for managing LVM volume groups including:
- Getting VG size and free space
- Adding/removing VG tags
- Checking VG existence and status
- Removing device mappings
"""


from typing import Optional, Dict, Tuple, List

from zstacklib.utils import bash, shell, log
from zstacklib.storage.lvm.models import VolumeGroup, VgNotFoundError

logger = log.get_logger(__name__)


def get_vg_uuid(path: str) -> str:
    """Extract VG UUID from an LV path.
    
    Args:
        path: LV path in format /dev/VG_UUID/LV_NAME
        
    Returns:
        VG UUID portion of the path
        
    Raises:
        Exception: If path format is invalid
    """
    if not path or len(path.split("/")) != 4:
        raise Exception(f"invalid lv path[{path}]")
    return path.split("/")[2]


@bash.in_bash
def get_vg_lvm_uuid(vg_uuid: str) -> str:
    """Get the internal LVM UUID for a volume group.
    
    Args:
        vg_uuid: Volume group name/UUID
        
    Returns:
        LVM internal UUID
    """
    return bash.bash_o(f"vgs --nolocking -t --noheading -ouuid {vg_uuid}").strip()


@bash.in_bash
def vg_exists(vg_uuid: str) -> bool:
    """Check if a volume group exists.
    
    Args:
        vg_uuid: Volume group name/UUID
        
    Returns:
        True if VG exists, False otherwise
    """
    cmd = shell.ShellCmd(f"vgs --nolocking -t {vg_uuid}")
    cmd(is_exception=False)
    return cmd.return_code == 0


def get_vg_size(vg_uuid: str, raise_exception: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """Get the total and free size of a volume group.
    
    For thin-provisioned VGs, includes free space in thin pools.
    
    Args:
        vg_uuid: Volume group name/UUID
        raise_exception: Whether to raise on error
        
    Returns:
        Tuple of (total_size, free_size) in bytes as strings, or (None, None) on error
    """
    from zstacklib.storage.lvm.thin import get_thin_pools_from_vg
    
    r, o, _ = bash.bash_roe(
        f"vgs --nolocking -t {vg_uuid} --noheadings --separator : --units b -o vg_size,vg_free,vg_lock_type",
        errorout=raise_exception
    )
    if r != 0:
        return None, None
        
    parts = o.strip().split(':')
    vg_size = parts[0].strip("B")
    vg_free = parts[1].strip("B")
    
    if "sanlock" in o:
        return vg_size, vg_free

    pools = get_thin_pools_from_vg(vg_uuid)
    if len(pools) == 0:
        return vg_size, vg_free
        
    vg_free_val = float(vg_free)
    for pool in pools:
        vg_free_val += pool.free
    return vg_size, str(int(vg_free_val))


def get_all_vg_size() -> Dict[str, Tuple[int, int]]:
    """Get size information for all volume groups.
    
    Returns:
        Dict mapping VG name to (total_size, free_size) tuple
    """
    from zstacklib.storage.lvm.thin import get_thin_pools_from_vg
    
    d: Dict[str, Tuple[int, int]] = {}

    o = bash.bash_o(
        "vgs --nolocking -t --noheadings --separator : --units b -o name,vg_size,vg_free,vg_lock_type"
    )
    if not o:
        return d

    for line in o.splitlines():
        xs = line.strip().split(':')
        vg_name = xs[0]
        vg_size = int(xs[1].strip("B"))
        vg_free = int(xs[2].strip("B"))

        if "sanlock" in line:
            d[vg_name] = (vg_size, vg_free)
            continue

        pools = get_thin_pools_from_vg(vg_name)
        if len(pools) == 0:
            d[vg_name] = (vg_size, vg_free)
            continue

        for pool in pools:
            vg_free += int(pool.free)
        d[vg_name] = (vg_size, vg_free)

    return d


def add_vg_tag(vg_uuid: str, tag: str) -> None:
    """Add a tag to a volume group.
    
    Args:
        vg_uuid: Volume group name/UUID
        tag: Tag to add
        
    Raises:
        Exception: If command fails
    """
    cmd = shell.ShellCmd(f"vgchange --addtag {tag} {vg_uuid}")
    cmd(is_exception=True)


def clean_vg_exists_host_tags(vg_uuid: str, host_uuid: str, tag: str) -> None:
    """Remove host-specific tags from a volume group.
    
    Args:
        vg_uuid: Volume group name/UUID
        host_uuid: Host identifier to match
        tag: Tag pattern to match
    """
    cmd = shell.ShellCmd(
        f"vgs {vg_uuid} -otags --nolocking -t --noheading | tr ',' '\\n' | grep {tag} | grep {host_uuid}"
    )
    cmd(is_exception=False)
    exists_tags = [x.strip() for x in cmd.stdout.splitlines()]
    if len(exists_tags) == 0:
        return
    t = " --deltag " + " --deltag ".join(exists_tags)
    cmd = shell.ShellCmd(f"vgchange {t} {vg_uuid}")
    cmd(is_exception=False)


@bash.in_bash
def remove_device_map_for_vg(vg_uuid: str) -> None:
    """Remove all device mapper entries for a volume group.
    
    Args:
        vg_uuid: Volume group name/UUID
    """
    o = bash.bash_o(f"dmsetup ls | awk '/{vg_uuid}/{{print $1}}'").strip().splitlines()
    if len(o) == 0:
        return
    for dm in o:
        bash.bash_roe(f"dmsetup remove {dm.strip()}")


def lvm_vgck(vg_uuid: str, timeout: int) -> Tuple[bool, str]:
    """Run vgck to check volume group consistency.
    
    Args:
        vg_uuid: Volume group name/UUID
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (success, error_message)
    """
    from zstacklib.storage.lvm.lock import check_stuck_vglk, fix_global_lock
    
    actual_timeout = max(360, timeout)
    health, o, e = bash.bash_roe(f'timeout -s SIGKILL {actual_timeout} vgck {vg_uuid} 2>&1')
    check_stuck_vglk()

    if health != 0:
        s = f"vgck {vg_uuid} failed, detail: [return_code: {health}, stdout: {o}, stderr: {e}]"
        logger.warn(s)
        return False, s

    if o is not None and o != "":
        for es in o.strip().splitlines():
            if es.strip() == "":
                continue
            if any(skip in es for skip in ["WARNING", "Retrying", "have changed sizes", 
                                            "held by other host", "without a lock"]):
                continue
            if "Duplicate sanlock global lock" in es:
                fix_global_lock()
                continue
            s = f"vgck {vg_uuid} failed, details: [return_code: {health}, stdout: {o}, stderr: {e}]"
            logger.warn(s)
            return False, s
    return True, ""


def lvm_check_operation(vg_uuid: str) -> bool:
    """Test LVM operations by creating and deleting a test volume.
    
    Args:
        vg_uuid: Volume group name/UUID
        
    Returns:
        True if operations succeed, False otherwise
    """
    import random
    from zstacklib.storage.lvm.lv import create_lv_from_absolute_path, delete_lv
    
    test_lv = f"/dev/{vg_uuid}/zscheckvolume{random.randint(100000, 999999)}"
    try:
        create_lv_from_absolute_path(test_lv, 1024 * 1024 * 4)
        delete_lv(test_lv, True)
    except Exception as e:
        if "already exists" in str(e):
            return True
        return False
    finally:
        delete_lv(test_lv, False)
    return True
