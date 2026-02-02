"""Linux kernel operations.

This module provides functions to work with the Linux kernel.
"""
from __future__ import annotations

import os
import platform
import subprocess

from .models import KernelInfo
from .exceptions import KernelError, ModuleLoadError, SysctlError


def get_kernel_version() -> KernelInfo:
    """Get the current kernel version.
    
    Returns:
        KernelInfo object with kernel details.
    """
    release = platform.release()
    version = platform.version()
    
    return KernelInfo(
        version=release,
        release=version
    )


def get_kernel_release() -> str:
    """Get the kernel release string.
    
    Returns:
        Kernel release string (e.g., '5.4.0-150-generic').
    """
    return platform.release()


def is_module_loaded(module: str) -> bool:
    """Check if a kernel module is loaded.
    
    Args:
        module: Module name.
        
    Returns:
        True if module is loaded.
    """
    try:
        with open('/proc/modules', 'r') as f:
            for line in f:
                if line.split()[0] == module:
                    return True
    except (OSError, IOError):
        pass
    return False


def load_module(module: str, params: dict[str, str] | None = None) -> None:
    """Load a kernel module.
    
    Args:
        module: Module name.
        params: Optional module parameters as key-value dict.
        
    Raises:
        ModuleLoadError: If module cannot be loaded.
    """
    if is_module_loaded(module):
        return
    
    cmd = ['modprobe', module]
    if params:
        for key, value in params.items():
            cmd.append(f'{key}={value}')
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ModuleLoadError(module, result.stderr.strip())
    except FileNotFoundError:
        raise ModuleLoadError(module, "modprobe command not found")
    except Exception as e:
        raise ModuleLoadError(module, str(e))


def unload_module(module: str, force: bool = False) -> None:
    """Unload a kernel module.
    
    Args:
        module: Module name.
        force: Force removal even if in use.
        
    Raises:
        ModuleLoadError: If module cannot be unloaded.
    """
    if not is_module_loaded(module):
        return
    
    cmd = ['rmmod']
    if force:
        cmd.append('-f')
    cmd.append(module)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ModuleLoadError(module, f"Failed to unload: {result.stderr.strip()}")
    except FileNotFoundError:
        raise ModuleLoadError(module, "rmmod command not found")
    except Exception as e:
        raise ModuleLoadError(module, str(e))


def get_sysctl(param: str) -> str:
    """Get a sysctl parameter value.
    
    Args:
        param: Sysctl parameter name (e.g., 'net.ipv4.ip_forward').
        
    Returns:
        Parameter value as string.
        
    Raises:
        SysctlError: If parameter cannot be read.
    """
    # Convert dot notation to path
    path = '/proc/sys/' + param.replace('.', '/')
    
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except (OSError, IOError) as e:
        raise SysctlError(param, str(e))


def set_sysctl(param: str, value: str, persist: bool = False) -> None:
    """Set a sysctl parameter value.
    
    Args:
        param: Sysctl parameter name (e.g., 'net.ipv4.ip_forward').
        value: Value to set.
        persist: If True, also write to /etc/sysctl.conf.
        
    Raises:
        SysctlError: If parameter cannot be set.
    """
    # Convert dot notation to path
    path = '/proc/sys/' + param.replace('.', '/')
    
    try:
        with open(path, 'w') as f:
            f.write(value)
    except (OSError, IOError) as e:
        raise SysctlError(param, str(e))
    
    if persist:
        _persist_sysctl(param, value)


def _persist_sysctl(param: str, value: str) -> None:
    """Persist sysctl setting to /etc/sysctl.conf.
    
    Args:
        param: Sysctl parameter name.
        value: Value to set.
    """
    sysctl_conf = '/etc/sysctl.conf'
    sysctl_d_dir = '/etc/sysctl.d'
    zstack_conf = os.path.join(sysctl_d_dir, '99-zstack.conf')
    
    # Prefer writing to sysctl.d if it exists
    if os.path.isdir(sysctl_d_dir):
        target_file = zstack_conf
    else:
        target_file = sysctl_conf
    
    # Read existing content
    lines = []
    param_found = False
    
    if os.path.exists(target_file):
        with open(target_file, 'r') as f:
            for line in f:
                if line.strip().startswith(param):
                    lines.append(f'{param} = {value}\n')
                    param_found = True
                else:
                    lines.append(line)
    
    if not param_found:
        lines.append(f'{param} = {value}\n')
    
    with open(target_file, 'w') as f:
        f.writelines(lines)


def get_hostname() -> str:
    """Get the system hostname.
    
    Returns:
        Hostname string.
    """
    try:
        with open('/etc/hostname', 'r') as f:
            return f.read().strip()
    except (OSError, IOError):
        return platform.node()


def get_fqdn() -> str:
    """Get the fully qualified domain name.
    
    Returns:
        FQDN string.
    """
    import socket
    return socket.getfqdn()
