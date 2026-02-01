"""LVM snapshot operations."""


from typing import Optional

from zstacklib.utils import bash, linux, lock as lock_utils, log

logger = log.get_logger(__name__)


@bash.in_bash
def create_lvm_snapshot(
    absolute_path: str,
    remove_oldest: bool = True,
    snap_name: Optional[str] = None,
    size_percent: float = 0.1,
    drbd_path: Optional[str] = None
) -> str:
    """Create an LVM snapshot of a logical volume.
    
    Args:
        absolute_path: Path to the source LV
        remove_oldest: Whether to remove oldest snapshot if limit reached
        snap_name: Optional specific name for snapshot
        size_percent: Snapshot size as percentage of source
        drbd_path: Optional DRBD path for size calculation
        
    Returns:
        Path to the created snapshot
    """
    from zstacklib.storage.lvm.thin import is_thin_lv
    from zstacklib.storage.lvm.lv import calc_lv_reserved_size
    
    if snap_name is None:
        snap_name = get_new_snapshot_name(absolute_path, remove_oldest)
        
    if is_thin_lv(absolute_path):
        size_command = ""
    else:
        virtual_size = linux.qcow2_virtualsize(drbd_path if drbd_path else absolute_path)
        if virtual_size <= 2147483648:
            snap_size = calc_lv_reserved_size(virtual_size)
            snap_size = int(snap_size / 512 + 1) * 512
        elif int((virtual_size / 512) * size_percent * 512) <= 2147483648:
            snap_size = 2147483648
        else:
            snap_size = int((virtual_size / 512) * size_percent + 1) * 512
        size_command = f" -L {snap_size}B "
        
    bash.bash_errorout(
        f"blockdev --flushbufs {absolute_path}; lvcreate --snapshot -n {snap_name} {absolute_path} {size_command}"
    )
    path = "/".join(absolute_path.split("/")[:-1]) + "/" + snap_name
    if size_command == "":
        bash.bash_r(f"lvchange -ay -K {path}")
    return path


@bash.in_bash
def delete_snapshots(lv_path: str) -> None:
    """Delete all snapshots of a logical volume."""
    from zstacklib.storage.lvm.lv import delete_lv
    
    lv_name = lv_path.split("/")[-1]
    all_snaps = bash.bash_o(
        f"lvs -oname -Sorigin={lv_name} --nolocking -t --noheadings | grep _snap_"
    ).strip().splitlines()
    
    if len(all_snaps) == 0:
        return
    for snap in all_snaps:
        delete_lv(snap.strip())


def get_new_snapshot_name(absolute_path: str, remove_oldest: bool = True) -> str:
    """Generate a new unique snapshot name for an LV."""
    from zstacklib.storage.lvm.lv import delete_lv
    
    @bash.in_bash
    @lock_utils.file_lock(absolute_path)
    def do_get_new_snapshot_name(name: str) -> str:
        all_snaps = bash.bash_o(
            f"lvs -oname -Sorigin={name} --nolocking -t --noheadings | grep _snap_"
        ).strip().splitlines()
        
        if len(all_snaps) == 0:
            return name + "_snap_1"
            
        numbers = list(map(lambda x: int(x.strip().split("_")[-1]), all_snaps))
        if len(all_snaps) >= 3 and remove_oldest:
            oldest = name + "_snap_" + str(min(numbers))
            delete_lv("/".join(absolute_path.split("/")[:-1]) + "/" + oldest)
        elif len(all_snaps) >= 3:
            raise Exception(f"there are {len(all_snaps)} snapshots for lv {absolute_path} exits")
        return name + "_snap_" + str(max(numbers) + 1)
        
    return do_get_new_snapshot_name(absolute_path.split("/")[-1])


@bash.in_bash
def delete_image(path: str, tag: str, deactive: bool = True) -> None:
    """Delete an image LV and its metadata LV."""
    from zstacklib.storage.lvm.lv import get_meta_lv_path
    from zstacklib.storage.lvm.lock import OperateLv
    
    def activate_and_remove(f: str, deactive: bool) -> Optional[str]:
        if deactive:
            from zstacklib.storage.lvm.lv import _active_lv
            _active_lv(f, shared=False)
        backing = linux.qcow2_get_backing_file(f)
        bash.bash_roe(f"lvremove -y -Stags={{{tag}}} {f}")
        return backing

    activate_and_remove(path, deactive)
    activate_and_remove(get_meta_lv_path(path), deactive)
