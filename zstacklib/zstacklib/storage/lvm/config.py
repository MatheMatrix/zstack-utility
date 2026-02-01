"""LVM configuration management."""


import os
import time
from typing import List, Optional, Set

from zstacklib.utils import bash, shell, linux, log

logger = log.get_logger(__name__)

LVM_CONFIG_PATH = "/etc/lvm"
LVM_CONFIG_FILE = '/etc/lvm/lvm.conf'
LVM_CONFIG_BACKUP_PATH = "/etc/lvm/zstack-backup"
LVM_CONFIG_ARCHIVE_PATH = "/etc/lvm/archive"


def check_lvm_config_is_default() -> bool:
    """Check if LVM config matches default settings."""
    cmd = shell.ShellCmd("lvmconfig --type diff")
    cmd(is_exception=True)
    return cmd.stdout == ""


def clean_duplicate_configs() -> None:
    """Remove duplicate config backup files."""
    cmd = shell.ShellCmd(
        f"md5sum {LVM_CONFIG_BACKUP_PATH}/* | awk 'p[$1]++ {{ printf \"rm %s\\n\",$2;}}' | bash"
    )
    cmd(is_exception=False)


def backup_lvm_config() -> None:
    """Backup current LVM config files."""
    if not os.path.exists(LVM_CONFIG_PATH):
        logger.warn(f"can not find lvm config path: {LVM_CONFIG_PATH}, backup failed")
        return

    if not os.path.exists(LVM_CONFIG_BACKUP_PATH):
        os.makedirs(LVM_CONFIG_BACKUP_PATH)

    clean_duplicate_configs()
    current_time = time.time()
    cmd = shell.ShellCmd(
        f"cp {LVM_CONFIG_PATH}/lvm.conf {LVM_CONFIG_BACKUP_PATH}/lvm-{current_time}.conf; "
        f"cp {LVM_CONFIG_PATH}/lvmlocal.conf {LVM_CONFIG_BACKUP_PATH}/lvmlocal-{current_time}.conf"
    )
    cmd(is_exception=False)
    logger.debug("backup lvm config file success")


def reset_lvm_conf_default() -> None:
    """Reset LVM config to default values."""
    if not os.path.exists(LVM_CONFIG_PATH):
        raise Exception(f"can not find lvm config path: {LVM_CONFIG_PATH}, reset lvm config failed")

    cmd = shell.ShellCmd(
        f"lvmconfig --type default > {LVM_CONFIG_PATH}/lvm.conf; "
        f"lvmconfig --type default > {LVM_CONFIG_PATH}/lvmlocal.conf"
    )
    cmd(is_exception=False)


def config_lvm_by_sed(keyword: str, entry: str, files: List[str]) -> None:
    """Configure LVM using sed replacement."""
    if not os.path.exists(LVM_CONFIG_PATH):
        raise Exception(f"can not find lvm config path: {LVM_CONFIG_PATH}, config lvm failed")

    for f in files:
        cmd = shell.ShellCmd(
            f"sed -i 's/.*\\b{keyword}\\b.*/{entry}/g' {LVM_CONFIG_PATH}/{f}"
        )
        cmd(is_exception=False)
    logger.debug(bash.bash_o("lvmconfig --type diff"))


@bash.in_bash
def config_lvm_filter(
    files: List[str],
    no_drbd: bool = False,
    preserve_disks: Optional[Set[str]] = None
) -> None:
    """Configure LVM device filter.
    
    Args:
        files: Config files to modify
        no_drbd: Whether to exclude DRBD devices
        preserve_disks: Set of disk paths to preserve
    """
    if not os.path.exists(LVM_CONFIG_PATH):
        raise Exception(f"can not find lvm config path: {LVM_CONFIG_PATH}, config lvm failed")

    if preserve_disks is not None and len(preserve_disks) != 0:
        filter_str = 'filter=['
        for disk in preserve_disks:
            escaped_disk = disk.replace("/", "\\/")
            filter_str += f'"a|^{escaped_disk}$|", '
        filter_str += '"r\\/.*\\/"]'

        for f in files:
            bash.bash_r(f"sed -i 's/.*\\b%s.*/{filter_str}/g' {LVM_CONFIG_PATH}/{f}" % "filter")
            bash.bash_r(f"sed -i 's/.*\\b%s.*/global_{filter_str}/g' {LVM_CONFIG_PATH}/{f}" % "global_filter")
        linux.sync_file(LVM_CONFIG_FILE)
        return

    filter_str = 'filter=["r|\\/dev\\/cdrom|"'
    vgs = bash.bash_o("vgs --nolocking -t -oname --noheading").splitlines()
    for vg in vgs:
        filter_str += f', "r\\/dev\\/mapper\\/{vg.strip()}.*\\/"'
    if no_drbd:
        filter_str += ', "r\\/dev\\/drbd.*\\/"'

    filter_str += ']'

    for f in files:
        bash.bash_r(f"sed -i 's/.*\\bfilter.*/{filter_str}/g' {LVM_CONFIG_PATH}/{f}")
    linux.sync_file(LVM_CONFIG_FILE)


def config_lvm_conf(node: str, value: str) -> None:
    """Set a node value in lvm.conf using lvmconfig."""
    cmd = shell.ShellCmd(f"lvmconfig --mergedconfig --config {node}={value} -f /etc/lvm/lvm.conf")
    cmd(is_exception=True)


def config_lvmlocal_conf(node: str, value: str) -> None:
    """Set a node value in lvmlocal.conf using lvmconfig."""
    cmd = shell.ShellCmd(f"lvmconfig --mergedconfig --config {node}={value} -f /etc/lvm/lvmlocal.conf")
    cmd(is_exception=True)


@bash.in_bash
def clean_lvm_archive_files(vg_uuid: str) -> None:
    """Clean old archive files for a volume group."""
    if not os.path.exists(LVM_CONFIG_ARCHIVE_PATH):
        logger.warn(f"can not find lvm archive path {LVM_CONFIG_ARCHIVE_PATH}")
        return
    archive_files = len([f for f in os.listdir(LVM_CONFIG_ARCHIVE_PATH) if vg_uuid in f])
    if archive_files > 10:
        bash.bash_r(
            f"ls -rt {LVM_CONFIG_ARCHIVE_PATH} | grep {vg_uuid} | head -n {archive_files-10} | "
            f"xargs -i rm -rf {LVM_CONFIG_ARCHIVE_PATH}/{{}}"
        )
