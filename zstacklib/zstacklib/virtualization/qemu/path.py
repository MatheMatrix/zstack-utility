# Copyright (c) ZStack.io, Inc.

"""
QEMU binary path detection.

Provides functions to locate QEMU binary and related directories.
"""

import os
from typing import Optional

from .exceptions import QemuPathNotFoundError


# Common QEMU binary paths
QEMU_KVM_PATHS = [
    '/usr/libexec/qemu-kvm',
    '/bin/qemu-kvm',
]

# QEMU binary directory paths
QEMU_BIN_DIRS = [
    '/usr/share/qemu-kvm/',
    '/usr/share/qemu/',
]


def get_host_arch():
    # type: () -> str
    """Get the host architecture.
    
    Returns:
        Architecture string (e.g., 'x86_64', 'aarch64').
    """
    import platform
    return platform.machine()


def get_colo_path():
    # type: () -> str
    """Get the COLO (COarse-grained LOck-stepping) QEMU path.
    
    Returns:
        Path to the COLO QEMU binary.
    """
    return '/var/lib/zstack/colo/qemu-system-x86_64'


def get_qemu_path(arch=None):
    # type: (Optional[str]) -> str
    """Get the path to the QEMU binary.
    
    Searches for QEMU binary in standard locations.
    
    Args:
        arch: Target architecture (defaults to host architecture).
        
    Returns:
        Path to the QEMU binary.
        
    Raises:
        QemuPathNotFoundError: If QEMU binary cannot be found.
    """
    # Check standard qemu-kvm paths
    for path in QEMU_KVM_PATHS:
        if os.path.exists(path):
            return path
    
    # Check architecture-specific path
    if arch is None:
        arch = get_host_arch()
    
    arch_path = '/usr/bin/qemu-system-{}'.format(arch)
    if os.path.exists(arch_path):
        return arch_path
    
    raise QemuPathNotFoundError(
        'Could not find QEMU binary in {} or /usr/bin/qemu-system-{}'.format(
            ', '.join(QEMU_KVM_PATHS), arch
        )
    )


def get_qemu_bin_dir():
    # type: () -> str
    """Get the QEMU binary/data directory.
    
    Returns:
        Path to the QEMU data directory.
        
    Raises:
        QemuPathNotFoundError: If QEMU directory cannot be found.
    """
    for path in QEMU_BIN_DIRS:
        if os.path.exists(path):
            return path
    
    raise QemuPathNotFoundError(
        'Could not find QEMU bin directory in {}'.format(
            ', '.join(QEMU_BIN_DIRS)
        )
    )


def is_qemu_available():
    # type: () -> bool
    """Check if QEMU is available on the system.
    
    Returns:
        True if QEMU binary is found, False otherwise.
    """
    try:
        get_qemu_path()
        return True
    except QemuPathNotFoundError:
        return False
