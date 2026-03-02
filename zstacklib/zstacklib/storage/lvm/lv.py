"""Logical Volume (LV) operations for LVM.

This module provides functions for managing LVM logical volumes including:
- Creating, deleting, resizing LVs
- Activating/deactivating LVs
- Querying LV properties
- Tag management
"""


import os
import random
from typing import Optional, List

from zstacklib.utils import bash, shell, linux, log
from zstacklib.storage.lvm.models import LogicalVolume, LvNotFoundError

logger = log.get_logger(__name__)

LV_RESERVED_SIZE = 1024 * 1024 * 4


def calc_lv_reserved_size(size: int) -> int:
    """Calculate LV size with reserved space for metadata.
    
    Adds 12M base reservation plus 4M per 4GB for qcow2 potential use.
    
    Args:
        size: Original size in bytes
        
    Returns:
        Size with reservations in bytes
    """
    size = int(size) + 3 * LV_RESERVED_SIZE
    size = int(size) + (size // 1024 // 1024 // 1024 // 4) * LV_RESERVED_SIZE
    return size


def get_original_size(size: int) -> int:
    """Reverse calculation of calc_lv_reserved_size."""
    size = int(size) - (int(size) // 1024 // 1024 // 1024 // 4) * LV_RESERVED_SIZE
    size = int(size) - 3 * LV_RESERVED_SIZE
    return size


def round_to(n: int, r: int) -> int:
    """Round n up to the nearest multiple of r."""
    return (n + r - 1) // r * r


@bash.in_bash
def lv_exists(path: str) -> bool:
    """Check if a logical volume exists."""
    r = bash.bash_r(f"lvs --nolocking -t {path}")
    return r == 0


def lv_uuid(path: str) -> str:
    """Get the UUID of a logical volume."""
    cmd = shell.ShellCmd(f"lvs --nolocking -t --noheadings {path} -ouuid")
    cmd(is_exception=False)
    return cmd.stdout.strip()


def lv_is_active(lv_path: str) -> bool:
    """Check if a logical volume is active."""
    r = bash.bash_r(f"lvs --nolocking -t --noheadings {lv_path} -oactive | grep -w active")
    if r == 0:
        return True
    return os.path.exists(lv_path)


def get_lv_size(path: str) -> str:
    """Get the size of a logical volume in bytes."""
    from zstacklib.storage.lvm.thin import is_thin_lv, get_thin_lv_size
    
    if is_thin_lv(path):
        return get_thin_lv_size(path)
    cmd = shell.ShellCmd(f"lvs --nolocking -t --noheading -osize --units b {path}")
    cmd(is_exception=True, logcmd=False)
    return cmd.stdout.strip().strip("B")


def get_meta_lv_path(path: str) -> str:
    """Get the metadata LV path for a given LV."""
    return path + "_meta"


def dd_zero(path: str) -> None:
    """Write zeros to the first 4M of an LV."""
    cmd = shell.ShellCmd(f"dd if=/dev/zero of={path} bs=1M count=4 oflag=direct")
    cmd(is_exception=False)


@bash.in_bash
@linux.retry(times=15, sleep_time=2)
def create_lv_from_absolute_path(
    path: str,
    size: int,
    tag: str = "zs::sharedblock::volume",
    lock: bool = True,
    exact_size: bool = False,
    pe_ranges: Optional[List[str]] = None
) -> bool:
    """Create a logical volume at the specified path.
    
    Args:
        path: Absolute LV path (/dev/vg_name/lv_name)
        size: Size in bytes
        tag: LVM tag to apply
        lock: Whether to deactivate after creation (for shared storage)
        exact_size: Use exact size without reservations
        pe_ranges: Specific PVs to allocate from
        
    Returns:
        True if created, False if already exists
        
    Raises:
        Exception: If creation fails
    """
    from zstacklib.storage.lvm.pv import get_allocated_pvs
    
    if lv_exists(path):
        return False

    vg_name = path.split("/")[2]
    lv_name = path.split("/")[3]
    pe_range = ' '.join(get_allocated_pvs(vg_name) if pe_ranges is None else pe_ranges)

    image_tag = "zs::sharedblock::image"
    exact_size = exact_size or (tag == image_tag)
    final_size = round_to(size, 512) if exact_size else round_to(calc_lv_reserved_size(size), 512)
    
    r, o, e = bash.bash_roe(
        f"lvcreate -ay --wipesignatures y --addtag {tag} --size {final_size}b --name {lv_name} {vg_name} {pe_range}"
    )

    if not lv_exists(path):
        raise Exception(f"can not find lv {path} after create, lvcreate return: {r}, {o}, {e}")

    dd_zero(path)
    if lock:
        deactive_lv(path)

    return True


@bash.in_bash
@linux.retry(times=10, sleep_time=2)
def _active_lv(path: str, shared: bool = False) -> None:
    flag = "-asy" if shared else "-ay"
    bash.bash_errorout(f"lvchange {flag} {path}")
    if not lv_is_active(path):
        raise Exception(f"active lv {path} with {flag} failed")


@bash.in_bash
@linux.retry(times=3, sleep_time=2)
def _deactive_lv(path: str, raise_exception: bool = True) -> None:
    if not lv_exists(path):
        return
    if not lv_is_active(path):
        return
        
    r = 0
    e = None
    if raise_exception:
        o = bash.bash_errorout(f"lvchange -an {path}")
    else:
        r, o, e = bash.bash_roe(f"lvchange -an {path}")
    if lv_is_active(path):
        from zstacklib.storage.lvm.lock import RetryException
        raise RetryException(f"lv {path} is still active after lvchange -an, returns code: {r}, stdout: {o}, stderr: {e}")


def active_lv(path: str, shared: bool = False) -> None:
    """Activate a logical volume.
    
    Uses lock tracking if available, otherwise direct activation.
    
    Args:
        path: LV path
        shared: Whether to activate in shared mode
    """
    from zstacklib.storage.lvm.lock import LvLockOperator, LvmlockdLockType
    
    op = LvLockOperator.get_lock_cnt_or_else_none(path)
    if op:
        op.force_lock(LvmlockdLockType.SHARE if shared else LvmlockdLockType.EXCLUSIVE)
    else:
        _active_lv(path, shared)


def deactive_lv(path: str, raise_exception: bool = True) -> None:
    """Deactivate a logical volume.
    
    Args:
        path: LV path
        raise_exception: Whether to raise on failure
    """
    from zstacklib.storage.lvm.lock import LvLockOperator
    
    op = LvLockOperator.get_lock_cnt_or_else_none(path)
    if op:
        op.force_unlock(raise_exception)
    else:
        _deactive_lv(path, raise_exception)


@bash.in_bash
def resize_lv(path: str, size: int, force: bool = False) -> None:
    """Resize a logical volume.
    
    Args:
        path: LV path
        size: New size in bytes
        force: Whether to force resize
        
    Raises:
        Exception: If resize fails
    """
    _force = " --force " if force else ""
    r, o, e = bash.bash_roe(f"lvresize {_force} --size {calc_lv_reserved_size(size)}b {path}")
    if r == 0:
        logger.debug(f"successfully resize lv {path} size to {size}")
        return
    elif "matches existing size" in e or "matches existing size" in o:
        logger.debug(f"lv {path} size already matches existing size: {size}, return as successful")
        return
    else:
        raise Exception(f"resize lv {path} to size {size} failed, return code: {r}, stdout: {o}, stderr: {e}")


@bash.in_bash
@linux.retry(times=15, sleep_time=2)
def extend_lv(path: str, extend_size: int) -> None:
    """Extend a logical volume to a new size.
    
    Args:
        path: LV path
        extend_size: Target size in bytes
        
    Raises:
        RetryException: If extend fails (will retry)
    """
    from zstacklib.storage.lvm.lock import RetryException
    
    r, o, e = bash.bash_roe(f"lvextend --size {calc_lv_reserved_size(extend_size)}b {path}")
    if r == 0:
        logger.debug(f"successfully extend lv {path} size to {extend_size}")
        return
    elif "matches existing size" in e or "matches existing size" in o:
        logger.debug(f"lv {path} size already matches existing size: {extend_size}, return as successful")
        return
    else:
        raise RetryException(
            f"extend lv {path} to size {extend_size} failed, return code: {r}, stdout: {o}, stderr: {e}"
        )


@bash.in_bash
def delete_lv(path: str, raise_exception: bool = True, deactive: bool = True) -> Optional[str]:
    """Delete a logical volume.
    
    Args:
        path: LV path
        raise_exception: Whether to raise on failure
        deactive: Whether to deactivate before deletion
        
    Returns:
        Command output or None
    """
    logger.debug(f"deleting lv {path}")
    if deactive:
        _deactive_lv(path, False)
        
    meta_path = get_meta_lv_path(path)
    if lv_exists(meta_path):
        shell.run(f"lvremove -y {meta_path}")
    if not lv_exists(path):
        return None
    if raise_exception:
        o = bash.bash_errorout(f"lvremove -y {path}")
    else:
        o = bash.bash_o(f"lvremove -y {path}")
    return o


@bash.in_bash
def delete_lv_meta(path: str, raise_exception: bool = True) -> Optional[str]:
    """Delete the metadata LV for a given LV."""
    logger.debug(f"deleting lv meta {path}")
    meta_path = get_meta_lv_path(path)
    if not lv_exists(meta_path):
        return None
    if raise_exception:
        o = bash.bash_errorout(f"lvremove -y {meta_path}")
    else:
        o = bash.bash_o(f"lvremove -y {meta_path}")
    return o


@bash.in_bash
def lv_rename(old_abs_path: str, new_abs_path: str, overwrite: bool = False) -> tuple:
    """Rename a logical volume.
    
    Args:
        old_abs_path: Current LV path
        new_abs_path: New LV path
        overwrite: Whether to overwrite existing LV
        
    Returns:
        Tuple of (return_code, stdout, stderr)
        
    Raises:
        Exception: If target exists and overwrite is False
    """
    import time
    
    if not lv_exists(new_abs_path):
        return bash.bash_roe(f"lvrename {old_abs_path} {new_abs_path}")

    if not overwrite:
        raise Exception(f"lv with name {new_abs_path} already exists, can not rename lv {old_abs_path} to it")

    tmp_path = f"{new_abs_path}_{int(time.time())}"
    r, o, e = lv_rename(new_abs_path, tmp_path)
    if r != 0:
        raise Exception(f"rename lv {new_abs_path} to tmp name {tmp_path} failed: stdout: {o}, stderr: {e}")

    r, o, e = lv_rename(old_abs_path, new_abs_path)
    if r != 0:
        bash.bash_errorout(f"lvrename {tmp_path} {new_abs_path}")
        raise Exception(f"rename lv {old_abs_path} to {new_abs_path} failed: stdout: {o}, stderr: {e}")

    delete_lv(tmp_path, False)
    return (0, "", "")


def list_local_active_lvs(vg_uuid: str) -> List[str]:
    """List all locally active LVs in a volume group."""
    cmd = shell.ShellCmd(f"lvs --nolocking -t {vg_uuid} --noheadings -opath -Slv_active=active")
    cmd(is_exception=False)
    result = []
    for i in cmd.stdout.strip().split("\n"):
        if i.strip() != "":
            result.append(i.strip())
    return result


def has_lv_tag(path: str, tag: str) -> bool:
    """Check if an LV has a specific tag."""
    if tag == "":
        logger.debug("check tag is empty, return false")
        return False
    import shlex as _shlex
    tags_raw = shell.call(
        "lvs %s -otags --nolocking -t --noheadings 2>/dev/null" % _shlex.quote(path)
    ).strip()
    return tag in [t.strip() for t in tags_raw.split(',')]


def has_one_lv_tag_sub_string(path: str, tags: Optional[List[str]]) -> bool:
    """Check if an LV has any tag containing one of the given substrings."""
    if not tags or len(tags) == 0:
        logger.debug("check tag is empty, return false")
        return False
    exists_tags = set(shell.call(f"lvs {path} -otags --nolocking -t --noheadings").strip().split(","))
    for tag in tags:
        for exists_tag in exists_tags:
            if tag in exists_tag:
                return True
    return False


def clean_lv_tag(path: str, tag: str) -> None:
    """Remove a tag from an LV if it exists."""
    if has_lv_tag(path, tag):
        shell.run(f'lvchange --deltag {tag} {path}')


def add_lv_tag(path: str, tag: str) -> None:
    """Add a tag to an LV if it doesn't exist."""
    if not has_lv_tag(path, tag):
        shell.run(f'lvchange --addtag {tag} {path}')
