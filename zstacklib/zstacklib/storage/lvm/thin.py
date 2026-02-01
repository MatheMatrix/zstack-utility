"""Thin provisioning operations for LVM."""


from typing import List

from zstacklib.utils import bash, log
from zstacklib.storage.lvm.models import ThinPool

logger = log.get_logger(__name__)


def is_thin_lv(path: str) -> bool:
    """Check if an LV is a thin-provisioned volume."""
    return bash.bash_r(f"lvs --nolocking -t --noheadings -olayout {path} | grep 'thin,sparse'") == 0


def get_thin_lv_size(path: str) -> str:
    """Get the used size of a thin LV in bytes."""
    pool = ThinPoolInfo(path)
    return str(int(pool.total - pool.free))


class ThinPoolInfo:
    """Information about a thin pool."""
    
    def __init__(self, path: str):
        o = bash.bash_o(
            f"lvs --nolocking -t {path} --separator ' ' -oname,data_percent,lv_size,pool_lv --noheading --unit B"
        ).strip()
        self.name = o.split(" ")[0].strip()
        self.total = float(o.split(" ")[2].strip("B"))
        self.thin_lvs = [
            l.strip() for l in 
            bash.bash_o(f"lvs -Spool_lv={self.name} --noheadings --nolocking -t -oname").strip().splitlines()
        ]
        if len(self.thin_lvs) == 0 and not is_thin_lv(path):
            self.free = self.total
        else:
            try:
                self.free = self.total * (100 - float(o.split(" ")[1].strip("B"))) / 100
            except Exception:
                self.free = self.total


def get_thin_pools_from_vg(vg_name: str) -> List[ThinPool]:
    """Get all thin pools in a volume group."""
    names = bash.bash_o(
        f"lvs --nolocking -t {vg_name} -Slayout=pool -oname --noheading"
    ).strip().splitlines()
    if len(names) == 0:
        return []
    
    pools = []
    for n in names:
        n = n.strip()
        if not n:
            continue
        info = ThinPoolInfo(f"/dev/{vg_name}/{n}")
        pools.append(ThinPool(
            name=info.name,
            vg_name=vg_name,
            size=int(info.total),
            data_percent=(info.total - info.free) / info.total * 100 if info.total > 0 else 0,
            metadata_percent=0
        ))
    return pools


def get_thin_pool_from_vg(vg_name: str) -> str:
    """Get the thin pool with most free space from a VG."""
    pools = get_thin_pools_from_vg(vg_name)
    if not pools:
        return ""
    
    most_free_pool = max(pools, key=lambda p: p.size * (100 - p.data_percent) / 100)
    return most_free_pool.name


@bash.in_bash
def create_thin_lv_from_absolute_path(
    path: str,
    size: int,
    tag: str,
    lock: bool = False
) -> None:
    """Create a thin-provisioned LV."""
    from zstacklib.storage.lvm.lv import lv_exists, calc_lv_reserved_size, round_to, dd_zero
    from zstacklib.storage.lvm.lock import OperateLv
    
    if lv_exists(path):
        return

    vg_name = path.split("/")[2]
    lv_name = path.split("/")[3]

    thin_pool = get_thin_pool_from_vg(vg_name)
    assert thin_pool != ""

    final_size = round_to(calc_lv_reserved_size(size), 512)
    r, o, e = bash.bash_roe(
        f"lvcreate --wipesignatures y --addtag {tag} -n {lv_name} -V {final_size}b --thinpool {thin_pool} {vg_name}"
    )
    if not lv_exists(path):
        raise Exception(f"can not find lv {path} after create, lvcreate return : {r}, {o}, {e}")

    if lock:
        with OperateLv(path, shared=False):
            dd_zero(path)
    else:
        from zstacklib.storage.lvm.lv import active_lv
        active_lv(path)
        dd_zero(path)
