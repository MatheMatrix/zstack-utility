# Copyright (c) ZStack.io, Inc.

"""
DRBD utility functions.

This module provides utility functions for DRBD installation and
resource enumeration.
"""

import platform
from typing import List

from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import log

from .models import DrbdNetState, DRBD_CONFIG_DIR
from .resource import DrbdResource
from .exceptions import DrbdInstallError

logger = log.get_logger(__name__)


@bash.in_bash
def list_local_up_drbd(vg_uuid=None):
    # type: (str) -> List[DrbdResource]
    """
    List all locally configured DRBD resources that are up.
    
    Args:
        vg_uuid: Optional volume group UUID filter (currently unused).
        
    Returns:
        List of DrbdResource objects for active resources.
    
    Note:
        Uses drbd-overview command which may not be available on all systems.
    """
    # TODO(weiw): drbd-overview maybe not exists
    if bash.bash_r("drbd-overview | grep -v %s" % DrbdNetState.Unconfigured) == 1:
        return []
    
    names = bash.bash_o(
        "drbd-overview | grep -v %s | awk -F ':' '{print $2}' | awk '{print $1}'" % DrbdNetState.Unconfigured
    ).strip().splitlines()
    
    return [DrbdResource(name) for name in names if name]


@bash.in_bash
def install_drbd():
    # type: () -> None
    """
    Ensure DRBD kernel module and utilities are installed.
    
    Checks for DRBD module and utilities, installing them if necessary.
    
    Raises:
        DrbdInstallError: If DRBD cannot be installed.
    """
    mod_installed = bash.bash_r("lsmod | grep drbd") == 0
    mod_exists = bash.bash_r("modinfo drbd") == 0
    utils_installed = bash.bash_r("rpm -ql drbd-utils || rpm -ql drbd84-utils") == 0
    basearch = platform.machine()
    releasever = bash.bash_o("awk '{print $3}' /etc/zstack-release").strip()
    utils_exists, o = bash.bash_ro(
        "ls /opt/zstack-dvd/{}/{}/Packages/drbd-utils*".format(basearch, releasever)
    )
    
    if mod_installed and utils_installed:
        return
    
    if not mod_installed:
        if mod_exists:
            bash.bash_errorout("modprobe drbd")
        else:
            raise DrbdInstallError("DRBD kernel module not installed and not available")
    
    if not utils_installed:
        if utils_exists == 0:
            bash.bash_errorout("rpm -ivh %s" % o.strip())
        else:
            raise DrbdInstallError("DRBD utilities not installed and not available")


@bash.in_bash
def up_all_resources():
    # type: () -> None
    """
    Bring up all DRBD resources and demote unused ones.
    
    Scans /etc/drbd.d/ for resource configurations and brings them up.
    Demotes any resources that are not currently in use.
    """
    all_names = bash.bash_o(
        "ls %s/ | grep -v global_common.conf" % DRBD_CONFIG_DIR
    ).strip().splitlines()
    
    for name in all_names:
        try:
            resource_name = name.split(".")[0]
            if not resource_name:
                continue
            r = DrbdResource(resource_name)
            if r.config.local_host.minor is not None:
                device_path = r.config.local_host.get_drbd_device()
                if linux.linux_lsof(device_path).strip() == "":
                    r.demote()
        except Exception as e:
            logger.warn("up resource %s failed: %s" % (name, str(e)))


@bash.in_bash
def is_drbd_available():
    # type: () -> bool
    """
    Check if DRBD is available on this system.
    
    Returns:
        True if DRBD module and utilities are available.
    """
    mod_available = bash.bash_r("modinfo drbd") == 0
    utils_available = bash.bash_r("which drbdadm") == 0
    return mod_available and utils_available


@bash.in_bash
def get_drbd_version():
    # type: () -> str
    """
    Get the DRBD kernel module version.
    
    Returns:
        Version string or empty string if not available.
    """
    r, o, e = bash.bash_roe("cat /proc/drbd | head -n1 | awk '{print $2}'")
    if r == 0:
        return o.strip()
    return ""
