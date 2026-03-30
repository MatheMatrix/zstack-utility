# Copyright (c) ZStack.io, Inc.

"""
QEMU version detection utilities.

Provides functions to query QEMU version from various sources.
"""

import logging
from typing import Optional, Tuple

from zstacklib.utils import bash

from .path import get_qemu_path
from .exceptions import QemuVersionError


logger = logging.getLogger(__name__)


def get_qemu_version():
    # type: () -> str
    """Get the QEMU version from virsh.
    
    Returns:
        QEMU version string.
        
    Raises:
        QemuVersionError: If version cannot be determined.
    """
    from zstacklib.utils import shell
    try:
        return shell.call("virsh version | awk '/hypervisor.*QEMU/{print $4}'").strip()
    except Exception as e:
        raise QemuVersionError('Failed to get QEMU version: {}'.format(e))


def get_version_from_exe(path, raise_error=False):
    # type: (str, bool) -> str
    """Get QEMU version from an executable file.
    
    Args:
        path: Path to the QEMU executable.
        raise_error: If True, raise exception on failure.
        
    Returns:
        Version string, or empty string on failure.
        
    Raises:
        QemuVersionError: If raise_error is True and version cannot be determined.
    """
    r, o, e = bash.bash_roe("{} --version".format(path))
    if r == 0:
        return _parse_version_output(o.strip())
    
    if raise_error:
        raise QemuVersionError('Cannot get version from {}: {}'.format(path, e))
    else:
        logger.debug('Cannot get version from %s: %s', path, e)
    
    return ''


def get_running_vm_version(vm_uuid):
    # type: (str) -> str
    """Get the QEMU version of a running VM.
    
    Tries multiple methods:
    1. From /proc/<pid>/exe of the VM process
    2. From QMP query-version command
    3. Falls back to system QEMU version
    
    Args:
        vm_uuid: UUID of the virtual machine.
        
    Returns:
        QEMU version string.
    """
    from zstacklib.utils import jsonobject
    
    # Try to get from VM process
    pid = _get_vm_pid(vm_uuid)
    if pid:
        exe_path = '/proc/{}/exe'.format(pid)
        version = get_version_from_exe(exe_path)
        if version:
            return version
    
    # Try QMP query
    r, o, e = bash.bash_roe(
        '''virsh qemu-monitor-command {} '{{"execute":"query-version"}}\''''.format(vm_uuid)
    )
    if r == 0:
        try:
            ret = jsonobject.loads(o.strip())
            if ret["return"].package:
                return _parse_version_output(ret["return"].package)
            else:
                qv = ret["return"].qemu
                return '{}.{}.{}'.format(qv.major, qv.minor, qv.micro)
        except Exception:
            pass
    
    logger.debug('Cannot get VM [uuid:%s] version from QMP: %s', vm_uuid, e)
    
    # Fall back to system QEMU version
    return get_version_from_exe(get_qemu_path())


def _get_vm_pid(vm_uuid):
    # type: (str) -> Optional[int]
    """Get the process ID of a running VM.
    
    Args:
        vm_uuid: UUID of the virtual machine.
        
    Returns:
        Process ID or None if not found.
    """
    try:
        from zstacklib.utils.linux import get_vm_pid
        return get_vm_pid(vm_uuid)
    except ImportError:
        # Fallback implementation
        r, o, _ = bash.bash_roe(
            "ps aux | grep qemu | grep {} | grep -v grep | awk '{{print $2}}'".format(vm_uuid)
        )
        if r == 0 and o.strip():
            try:
                return int(o.strip().split()[0])
            except (ValueError, IndexError):
                pass
    return None


def _parse_version_output(version_output):
    # type: (str) -> str
    """Parse QEMU version from command output.
    
    Handles various version output formats:
    - "QEMU emulator version 2.12.0 (qemu-kvm-ev-2.12.0-33.el7)"
    - "qemu-kvm-ev-2.12.0-33.el7"
    
    Args:
        version_output: Raw version output string.
        
    Returns:
        Parsed version string (e.g., "2.12.0-33").
    """
    lines = version_output.splitlines()
    ver_line = lines[0].strip() if lines else ''
    
    # Find the line starting with "qemu" (case insensitive)
    for line in lines:
        if line.lower().startswith('qemu'):
            ver_line = line.strip()
            break
    
    # Extract version from parentheses if present
    if '(' in ver_line:
        full_ver = ver_line.split('(', 1)[1].split(')', 1)[0]
    else:
        full_ver = ver_line
    
    # Extract version numbers
    parts = full_ver.split('-')
    version_parts = [s for s in parts if s and s[0].isdigit()]
    return '-'.join(version_parts)


def compare_versions(v1, v2):
    # type: (str, str) -> int
    """Compare two version strings.
    
    Args:
        v1: First version string.
        v2: Second version string.
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
    """
    from zstacklib.utils.version import NumericVersion

    lv1 = NumericVersion(v1)
    lv2 = NumericVersion(v2)
    
    if lv1 < lv2:
        return -1
    elif lv1 > lv2:
        return 1
    return 0
