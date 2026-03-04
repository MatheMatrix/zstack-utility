# Copyright (c) ZStack.io, Inc.

"""
DRBD configuration management.

This module handles reading and writing DRBD resource configuration files.
"""

import os
import shlex
from typing import Dict, Any, Optional

from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import log

from .models import (
    DrbdStruct, DrbdHostStruct, DrbdNetStruct,
    DRBD_CONFIG_DIR, DEFAULT_SPLIT_BRAIN_HANDLER,
    DEFAULT_FENCE_PEER_HANDLER, DEFAULT_FENCING
)
from .exceptions import DrbdConfigError, DrbdMinorConflictError

try:
    from jinja2 import Template
except ImportError:
    Template = None  # type: ignore

logger = log.get_logger(__name__)


# DRBD resource configuration template
DRBD_RESOURCE_TEMPLATE = """
resource {{ name }} {
  handlers {
    split-brain {{ split_brain }};
    fence-peer {{ fence_peer }};
  }

  net {
    csums-alg {{ net_csums_alg }};
    after-sb-0pri {{ net_after_sb_0pri }};
    after-sb-1pri {{ net_after_sb_1pri }};
    after-sb-2pri {{ net_after_sb_2pri }};
    protocol C;

    sndbuf-size {{ net_sndbuf_size }};
    rcvbuf-size {{ net_sndbuf_size }};
    allow-two-primaries yes;
    verify-alg {{ net_verify_alg }};
    max-buffers 16000;
    max-epoch-size 20000;
    max-buffers 51200;
  }

  disk {
    fencing {{ fencing }};
    resync-rate 100M;
    c-min-rate 102400;
    c-max-rate 204800;
  }

  on {{ local_host_hostname }} {  # local
    device    {{ local_host_device }} minor {{ local_host_minor }};
    disk      {{ local_host_disk }};
    address   {{ local_host_address }};
    meta-disk internal;
  }
  on {{ remote_host_hostname }} {  # remote
    device    {{ remote_host_device }} minor {{ remote_host_minor }};
    disk      {{ remote_host_disk }};
    address   {{ remote_host_address }};
    meta-disk internal;
  }
}
"""


class DrbdConfigStruct(DrbdStruct):
    """
    DRBD resource configuration structure.
    
    Manages the complete configuration for a DRBD resource including
    local and remote hosts, network settings, and handlers.
    """
    
    def __init__(self, name):
        """Init."""
        # type: (str) -> None
        super(DrbdConfigStruct, self).__init__()
        self.path = None  # type: Optional[str]
        self.name = name
        self.local_host = DrbdHostStruct(name)
        self.remote_host = DrbdHostStruct(name)
        self.net = DrbdNetStruct()
        
        # handlers
        self.split_brain = DEFAULT_SPLIT_BRAIN_HANDLER
        self.fence_peer = DEFAULT_FENCE_PEER_HANDLER
        
        # disk
        self.fencing = DEFAULT_FENCING
    
    def read_config(self):
        # type: () -> None
        """
        Read and parse the DRBD resource configuration file.
        
        Raises:
            DrbdConfigError: If path is not set or file cannot be read.
        """
        if not self.path:
            raise DrbdConfigError("Configuration path not set")
        
        try:
            with open(self.path, "r") as f:
                content = f.readlines()
        except IOError as e:
            raise DrbdConfigError("Cannot read config file: %s" % str(e))
        
        on_local = on_remote = False
        for line in content:
            line = line.strip()
            if line.startswith("resource ") and line.endswith(" {"):
                parsed_name = line.split(" ")[1]
                if self.name != parsed_name:
                    raise DrbdConfigError(
                        "Resource name mismatch: expected %s, got %s" % (self.name, parsed_name)
                    )
            elif line.strip().endswith(";"):
                line = line.strip(";")
                key = line.split(" ", 1)[0].replace("-", "_")
                try:
                    value = line.split(" ", 1)[1].strip()
                except IndexError:
                    continue
                
                if key in self.__dict__.keys():
                    self.__dict__[key] = value
                elif key in self.net.__dict__.keys():
                    self.net.__dict__[key] = value
                elif on_local and key in self.local_host.__dict__.keys():
                    if key == "device":
                        self.local_host.device = value.split(" ")[0]
                        self.local_host.minor = value.split(" ")[2]
                        continue
                    self.local_host.__dict__[key] = value
                elif on_remote and key in self.remote_host.__dict__.keys():
                    if key == "device":
                        self.remote_host.device = value.split(" ")[0]
                        self.remote_host.minor = value.split(" ")[2]
                        continue
                    self.remote_host.__dict__[key] = value
            elif line.startswith("on ") and line.endswith("# local"):
                on_local = True
                self.local_host.hostname = line.split(" ")[1]
            elif line.startswith("on ") and line.endswith("# remote"):
                on_remote = True
                self.remote_host.hostname = line.split(" ")[1]
            elif (on_local is True or on_remote is True) and "}" in line:
                on_local = on_remote = False
    
    def write_config(self):
        # type: () -> None
        """
        Write the DRBD resource configuration to file.
        
        Raises:
            DrbdConfigError: If name is not set or template not available.
            DrbdMinorConflictError: If the minor number is already in use.
        """
        if not self.name:
            raise DrbdConfigError("Resource name is required")
        
        if Template is None:
            raise DrbdConfigError("jinja2 is required for config generation")
        
        config = Template(DRBD_RESOURCE_TEMPLATE)
        ctx = self.make_ctx()
        rendered = config.render(ctx).strip()
        
        logger.debug("write drbd config: \n%s" % rendered)
        
        dirname = os.path.dirname(self.path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        
        # Check for minor conflict
        # TODO(weiw): this assumes minor will always be same on local and remote
        r, o = bash.bash_ro("grep ' minor %s;' /etc/drbd.d/*" % shlex.quote(str(self.local_host.minor)))
        if r == 0:
            raise DrbdMinorConflictError(
                "minor %s has already been defined: %s" % (self.local_host.minor, o),
                resource_name=self.name
            )
        
        with open(self.path, "w") as f:
            f.write(rendered)
            f.flush()
            os.fsync(f.fileno())
    
    def make_ctx(self):
        # type: () -> Dict[str, Any]
        """
        Build the context dictionary for template rendering.
        
        Returns:
            Dictionary with all configuration values.
        """
        ctx = {}  # type: Dict[str, Any]
        for k, v in self.__dict__.items():
            if isinstance(v, str):
                ctx[k] = v
            elif isinstance(v, DrbdStruct):
                for m, n in v.__dict__.items():
                    ctx["%s_%s" % (k, m)] = n
        ctx["local_host_hostname"] = linux.get_hostname()
        return ctx


@bash.in_bash
def get_config_path_from_disk(disk_path, raise_exception=True):
    # type: (str, bool) -> str
    """
    Find the DRBD resource config file that uses the given disk.
    
    Args:
        disk_path: Path to the backing disk.
        raise_exception: Whether to raise on failure.
        
    Returns:
        Path to the configuration file.
    """
    return bash.bash_o(
        "grep -E 'disk.*%s' /etc/drbd.d/ -r | head -n1 | awk '{print $1}' | cut -d ':' -f1" % shlex.quote(disk_path),
        raise_exception
    ).strip()


@bash.in_bash
def get_config_path_from_name(name):
    # type: (str) -> str
    """
    Find the DRBD resource config file by resource name.
    
    Args:
        name: DRBD resource name.
        
    Returns:
        Path to the configuration file.
        
    Raises:
        DrbdConfigError: If resource cannot be found.
    """
    if bash.bash_r("drbdadm dump %s" % shlex.quote(name)) == 0:
        return bash.bash_o("drbdadm dump %s | grep 'defined at' | awk '{print $4}'" % shlex.quote(name)).split(":")[0]
    
    default_path = "%s/%s.res" % (DRBD_CONFIG_DIR, name)
    if os.path.exists(default_path):
        return default_path
    
    raise DrbdConfigError("Cannot find drbd resource: %s" % name, resource_name=name)


@bash.in_bash
def get_name_from_config_path(config_path):
    # type: (str) -> str
    """
    Extract the resource name from a config file path.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        Resource name.
    """
    if bash.bash_r("head -n 1 %s" % shlex.quote(config_path)) == 0:
        return bash.bash_o("head -n 1 %s | awk '{print $2}'" % shlex.quote(config_path)).strip()
    else:
        return config_path.split("/")[-1].split(".")[0]
