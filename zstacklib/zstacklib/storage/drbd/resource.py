# Copyright (c) ZStack.io, Inc.

"""
DRBD resource management.

This module provides the DrbdResource class for managing DRBD resources,
including lifecycle operations (up/down), role management (promote/demote),
and data operations.
"""

import shlex
import time
from typing import Optional, Any

from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import lvm
from zstacklib.utils import log

from .models import DrbdRole, DrbdNetState, DRBD_CONFIG_DIR
from .config import DrbdConfigStruct, get_config_path_from_name, get_config_path_from_disk
from .exceptions import RetryException, DrbdError, DrbdResourceNotFoundError

logger = log.get_logger(__name__)


class DrbdResource:
    """
    DRBD resource manager.
    
    Provides methods for managing a DRBD resource including:
    - Lifecycle: up(), down(), destroy()
    - Role management: promote(), demote()
    - Connection: force_connect(), force_disconnect()
    - State queries: get_role(), get_cstate(), get_dstate()
    - Data operations: initialize(), resize(), dd_out()
    """
    
    def __init__(self, name, up=True):
        # type: (str, bool) -> None
        """
        Initialize a DrbdResource.
        
        Args:
            name: Resource name.
            up: Whether to bring the resource up if not allocated.
        """
        super(DrbdResource, self).__init__()
        self.config = DrbdConfigStruct(name)
        self.name = self.config.name = name
        self.path = self.config.path = "%s/%s.res" % (DRBD_CONFIG_DIR, name)
        
        self.cstate = None  # type: Optional[str]
        self.local_role = None  # type: Optional[str]
        self.remote_role = None  # type: Optional[str]
        self.local_disk_state = None  # type: Optional[str]
        self.remote_disk_state = None  # type: Optional[str]
        self.exists = False
        
        if self.name is None:
            return
        
        try:
            self._init_from_name()
            self.exists = True
        except Exception:
            logger.debug("can not find config of resource %s" % self.name)
            return
        
        if up and not self.minor_allocated():
            self.up()
    
    def _init_from_disk(self, disk_path):
        # type: (str) -> None
        """Initialize resource from disk path."""
        config_path = get_config_path_from_disk(disk_path)
        self._init_from_config_path(config_path)
    
    def _init_from_name(self):
        # type: () -> None
        """Initialize resource from name."""
        if self.name is None:
            return
        self._init_from_config_path(get_config_path_from_name(self.name))
    
    def _init_from_config_path(self, config_path):
        # type: (str) -> None
        """Initialize resource from configuration file path."""
        self.path = self.config.path = config_path
        self.config.read_config()
    
    @bash.in_bash
    def up(self):
        # type: () -> None
        """Bring the DRBD resource up."""
        if not self.minor_allocated() or self.get_cstate() == DrbdNetState.Unconfigured:
            bash.bash_errorout("drbdadm up %s" % self.name)
    
    @bash.in_bash
    @linux.retry(5, 2)
    def down(self):
        # type: () -> None
        """
        Bring the DRBD resource down.
        
        Retries up to 5 times with 2 second intervals.
        """
        r, o, e = bash.bash_roe("drbdadm down %s" % self.name)
        if r == 0:
            return
        if "conflicting use of device-minor" in o + e:
            logger.debug("detect conflicting use of device-minor! %s" % e)
            return
        if 0 == bash.bash_r("cat /proc/drbd | grep '^[[:space:]]*%s: cs:Unconfigured'" % self.config.local_host.minor):
            return
        if 1 == bash.bash_r("cat /proc/drbd | grep '^[[:space:]]*%s: '" % self.config.local_host.minor):
            return
        raise DrbdError(
            "demote resource %s failed: %s, %s, %s" % (self.name, r, o, e),
            resource_name=self.name,
            return_code=r,
            stdout=o,
            stderr=e
        )
    
    @bash.in_bash
    def promote(self, force=False, retry=90, sleep=3, single=False):
        # type: (bool, int, int, bool) -> None
        """
        Promote the resource to Primary role.
        
        Args:
            force: Force promotion even if data is not up-to-date.
            retry: Number of retry attempts.
            sleep: Sleep time between retries in seconds.
            single: Single-node mode (no peer).
        """
        @bash.in_bash
        @linux.retry(times=retry, sleep_time=sleep)
        def do_promote():
            """Do promote."""
            f = " --force" if force else ""
            r, o, e = bash.bash_roe("drbdadm primary %s %s" % (self.name, f))
            if self.get_role() != DrbdRole.Primary:
                raise RetryException(
                    "promote failed, return: %s, %s, %s. resource %s still not in role %s" % (
                        r, o, e, self.name, DrbdRole.Primary
                    ),
                    resource_name=self.name
                )
        
        if not force and not single:
            do_promote()
        else:
            if not single and self.get_dstate() != "UpToDate":
                bash.bash_r("drbdadm fence-peer %s" % self.name)
            bash.bash_errorout("drbdadm primary %s --force" % self.name)
    
    @bash.in_bash
    def demote(self):
        # type: () -> None
        """Demote the resource to Secondary role."""
        @bash.in_bash
        @linux.retry(times=30, sleep_time=2)
        def do_demote():
            """Do demote."""
            bash.bash_errorout("drbdadm secondary %s" % self.name)
        
        do_demote()
    
    @bash.in_bash
    def discard(self):
        # type: () -> None
        """Discard local changes and resync from peer."""
        self.demote()
        self.force_disconnect()
        self.force_connect(discard=True)
    
    @bash.in_bash
    def force_disconnect(self):
        # type: () -> None
        """Force disconnect from peer."""
        bash.bash_r("drbdadm disconnect %s" % self.name)
    
    @bash.in_bash
    def force_connect(self, discard=False):
        # type: (bool) -> None
        """
        Force connect to peer.
        
        Args:
            discard: If True, discard local data on connection.
        """
        if self.get_cstate() not in DrbdNetState.CONNECTING_STATES:
            discard_cmd = "-- --discard-my-data" if discard else ""
            bash.bash_errorout("drbdadm %s connect %s" % (discard_cmd, self.name))
    
    @bash.in_bash
    def get_cstate(self):
        # type: () -> str
        """Get connection state."""
        return bash.bash_o("drbdadm cstate %s" % self.name).strip()
    
    @bash.in_bash
    def get_dstate(self):
        # type: () -> str
        """Get local disk state."""
        return bash.bash_o("drbdadm dstate %s | cut -d '/' -f1" % self.name).strip()
    
    @bash.in_bash
    def get_remote_dstate(self):
        # type: () -> str
        """Get remote disk state."""
        return bash.bash_o("drbdadm dstate %s | cut -d '/' -f2" % self.name).strip()
    
    def is_connected(self):
        # type: () -> bool
        """Check if resource is connected to peer."""
        return self.get_cstate() == DrbdNetState.Connected
    
    @bash.in_bash
    def get_role(self):
        # type: () -> str
        """Get local role (Primary/Secondary)."""
        return bash.bash_o("drbdadm role %s | awk -F '/' '{print $1}'" % self.name).strip()
    
    @bash.in_bash
    def get_remote_role(self):
        # type: () -> str
        """Get remote role (Primary/Secondary)."""
        return bash.bash_o("drbdadm role %s | awk -F '/' '{print $2}'" % self.name).strip()
    
    def get_dev_path(self):
        # type: () -> str
        """Get the DRBD device path."""
        assert self.config.local_host.minor is not None
        return "/dev/drbd%s" % self.config.local_host.minor
    
    def wait_remote_dstate(self, dstate, times=3, sleep_times=1):
        # type: (str, int, int) -> bool
        """
        Wait for remote disk to reach specified state.
        
        Args:
            dstate: Target disk state.
            times: Number of check attempts.
            sleep_times: Sleep time between checks.
            
        Returns:
            True if state reached, False otherwise.
        """
        first_dstate = self.get_remote_dstate()
        if first_dstate == dstate:
            return True
        elif first_dstate == 'DUnknown':
            for i in range(times):
                time.sleep(sleep_times)
                if self.get_remote_dstate() == dstate:
                    return True
        
        return False
    
    @bash.in_bash
    @linux.retry(times=90, sleep_time=3)
    def clear_bits(self):
        # type: () -> None
        """Clear the dirty bitmap for initial sync."""
        bash.bash_errorout("drbdadm new-current-uuid --clear-bitmap %s" % self.name)
    
    @bash.in_bash
    def minor_allocated(self):
        # type: () -> bool
        """Check if device minor number is allocated."""
        r, o, e = bash.bash_roe("drbdadm role %s" % self.name)
        if e is not None and "Device minor not allocated" in o + e:
            logger.debug("Device %s minor not allocated!" % self.name)
            return False
        if e is not None and "not defined in your config" in o + e:
            return False
        return True
    
    @bash.in_bash
    def initialize(self, primary, cmd, backing=None, skip_clear_bits=False):
        # type: (bool, Any, Optional[str], bool) -> None
        """
        Initialize the DRBD resource with metadata.
        
        Args:
            primary: Whether this node should be primary during init.
            cmd: Command object with size and other parameters.
            backing: Optional backing file path.
            skip_clear_bits: Skip clearing dirty bitmap.
        """
        bash.bash_errorout("echo yes | drbdadm create-md %s --force" % shlex.quote(self.name))
        self.up()
        if skip_clear_bits:
            return
        if primary:
            self.promote(single=cmd.single)
            if backing:
                linux.qcow2_create_with_backing_file_and_cmd(backing, self.get_dev_path(), cmd)
            else:
                linux.qcow2_create_with_cmd(self.get_dev_path(), cmd.size, cmd)
            self.demote()
        elif not self.wait_remote_dstate('UpToDate'):
            self.clear_bits()

    @bash.in_bash
    def initialize_with_file(self, primary, src_path, backing=None, backing_fmt=None, skip_clear_bits=False):
        # type: (bool, str, Optional[str], Optional[str], bool) -> None
        """
        Initialize the DRBD resource from a source file.

        Args:
            primary: Whether this node should be primary during init.
            src_path: Source file to copy to DRBD device.
            backing: Optional backing file path.
            backing_fmt: Backing file format.
            skip_clear_bits: Skip clearing dirty bitmap.
        """
        bash.bash_errorout("echo yes | drbdadm create-md %s --force" % shlex.quote(self.name))
        self.up()
        if skip_clear_bits:
            return
        if primary:
            self.promote()
            bash.bash_errorout('dd if=%s of=%s bs=1M oflag=direct' % (shlex.quote(src_path), shlex.quote(self.get_dev_path())))
            if backing:
                linux.qcow2_rebase_no_check(backing, self.get_dev_path(), backing_fmt=backing_fmt)
            self.demote()
        elif not self.wait_remote_dstate('UpToDate'):
            self.clear_bits()
    
    @bash.in_bash
    def is_defined(self):
        # type: () -> bool
        """Check if the resource is defined in DRBD configuration."""
        assert self.name is not None
        assert self.name.strip() != ""
        r, o, e = bash.bash_roe("drbdadm role %s" % self.name)
        if r != 0 and "not defined in your config" in o + e:
            return False
        
        return True
    
    @bash.in_bash
    def destroy(self):
        # type: () -> None
        """Destroy the DRBD resource completely."""
        self.down()
        bash.bash_r("echo yes | drbdadm wipe-md %s" % self.name)
        bash.bash_r("rm %s/%s.res" % (DRBD_CONFIG_DIR, self.name))
    
    @bash.in_bash
    def resize(self):
        # type: () -> None
        """Resize the DRBD device (after backing storage resize)."""
        bash.bash_errorout("drbdadm -- --assume-clean resize %s" % self.name)
    
    @bash.in_bash
    def dd_out(self, dst_path, sparse=True):
        # type: (str, bool) -> None
        """
        Copy data from DRBD device to a file.
        
        Args:
            dst_path: Destination file path.
            sparse: Use sparse copy if True.
        """
        need_promote_first = self.get_role() == DrbdRole.Secondary
        need_promote_first and self.promote()
        try:
            bash.bash_errorout('dd if=%s of=%s bs=1M %s' % (
                shlex.quote(self.get_dev_path()), shlex.quote(dst_path), 'conv=sparse' if sparse else ''
            ))
        finally:
            need_promote_first and self.demote()


class OperateDrbd:
    """
    Context manager for DRBD operations requiring Primary role.
    
    Automatically promotes the resource on entry and demotes on exit
    (unless shared mode is enabled).
    
    Example:
        with OperateDrbd(resource) as ctx:
            # resource is now Primary
            do_something()
        # resource is demoted back to Secondary
    """
    
    resource = None  # type: Optional[DrbdResource]
    
    @bash.in_bash
    def __init__(self, resource, shared=False, delete_when_exception=False):
        # type: (DrbdResource, bool, bool) -> None
        """
        Initialize the context manager.
        
        Args:
            resource: DrbdResource to operate on.
            shared: If True, don't demote on exit.
            delete_when_exception: If True, destroy resource on exception.
        """
        self.resource = resource
        self.shared = shared
        self.current_role = self.resource.get_role()
        self.delete_when_exception = delete_when_exception
    
    @bash.in_bash
    def __enter__(self):
        # type: () -> OperateDrbd
        """Enter context - promote if necessary."""
        if self.current_role == DrbdRole.Secondary:
            self.resource.promote()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # type: (Any, Any, Any) -> None
        """Exit context - demote or cleanup on exception."""
        if exc_val is not None and self.delete_when_exception is True:
            self.resource.destroy()
            lvm.delete_lv(self.resource.config.local_host.disk, False)
            return
        
        if self.current_role == DrbdRole.Secondary and not self.shared:
            self.resource.demote()
