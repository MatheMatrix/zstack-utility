"""Multipath device handling for LVM."""


import os
import re as _re
from typing import List, Optional

from zstacklib.utils import bash, linux, log

logger = log.get_logger(__name__)


def _validate_dev_name(dev_name):
    # type: (str) -> None
    if not _re.match(r'^[A-Za-z0-9._-]+$', dev_name):
        raise ValueError('invalid device name: %s' % dev_name)


@bash.in_bash
def is_multipath_running() -> bool:
    """Check if multipath daemon is running."""
    r = bash.bash_r("multipath -t > /dev/null")
    if r != 0:
        return False
    r = bash.bash_r("pgrep multipathd")
    return r == 0


@bash.in_bash
def is_slave_of_multipath(dev_path: str) -> bool:
    """Check if a device is a slave of a multipath device."""
    if not is_multipath_running():
        return False
    r = bash.bash_r(f"multipath -c {dev_path}")
    return r == 0


def is_slave_of_multipath_list(
    dev_path: str,
    slave_multipath: List[str],
    is_multipath_running_sign: bool
) -> bool:
    """Check if device is in the slave multipath list."""
    if not is_multipath_running_sign:
        return False
    return dev_path.split("/")[-1] in slave_multipath


def is_multipath(dev_name: str) -> bool:
    """Check if a device is a multipath device."""
    if not is_multipath_running():
        return False
    r = bash.bash_r(f"multipath /dev/{dev_name} -l | grep policy")
    if r == 0:
        return True

    slaves = linux.listdir(f"/sys/class/block/{dev_name}/slaves/")
    if slaves is not None and len(slaves) > 0:
        if len(slaves) == 1 and slaves[0] == "":
            return False
        return True
    return False


def get_multipath_dmname(dev_name: str) -> Optional[str]:
    """Get multipath device-mapper name for a device.

    Returns:
        dm-* name if multipath, None otherwise
    """
    _validate_dev_name(dev_name)
    slaves = linux.listdir(f"/sys/class/block/{dev_name}/slaves/")
    if slaves is not None and len(slaves) > 0 and slaves[0].strip() != "":
        return dev_name

    r = bash.bash_r(f"multipath /dev/{dev_name} -l | grep policy")
    if r != 0:
        return None
    return bash.bash_o(
        f"multipath -l /dev/{dev_name} | head -n1 | grep -Eo 'dm-[[:digits:]]+'"
    ).strip()


def get_multipath_name(dev_name: str) -> str:
    """Get multipath device name."""
    _validate_dev_name(dev_name)
    return bash.bash_o(f"multipath /dev/{dev_name} -l -v1").strip()


@bash.in_bash
@linux.retry(times=3, sleep_time=1)
def enable_multipath() -> None:
    """Enable and start multipath daemon."""
    from zstacklib.storage.lvm.lock import RetryException
    
    bash.bash_roe("modprobe dm-multipath")
    bash.bash_roe("modprobe dm-round-robin")
    bash.bash_roe("mpathconf --enable --with_multipathd y")
    bash.bash_roe("systemctl enable multipathd")

    if not is_multipath_running():
        raise RetryException("multipath still not running")


@bash.in_bash
@linux.retry(times=3, sleep_time=1)
def disable_multipath() -> None:
    """Disable and stop multipath daemon."""
    from zstacklib.storage.lvm.lock import RetryException
    
    bash.bash_roe("systemctl disable multipathd")
    bash.bash_roe("systemctl stop multipathd")

    if is_multipath_running():
        raise RetryException("multipath is still running")


def get_disk_holders(disk_names: List[str]) -> List[str]:
    """Get all holder devices for given disks recursively."""
    holders = []
    for disk_name in disk_names:
        h = linux.listdir(f"/sys/class/block/{disk_name}/holders/")
        if len(h) == 0:
            continue
        holders.extend(h)
        holders.extend(get_disk_holders(h))
    holders.reverse()
    return holders


def unpriv_sgio() -> None:
    """Enable unprivileged SCSI generic I/O for all block devices."""
    for devname in os.listdir("/sys/block/"):
        if "loop" in devname:
            continue
        linux.write_file(f"/sys/block/{devname}/queue/unpriv_sgio", "1")
