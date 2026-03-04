# Copyright (c) ZStack.io, Inc.

"""
QEMU/KVM virtualization module.

Provides utilities for:
- QEMU binary path and version detection
- qemu-img disk image operations
- QEMU Guest Agent (QGA) communication

Example usage:

    # Get QEMU path and version
    from zstacklib.virtualization.qemu import get_qemu_path, get_qemu_version
    
    qemu_path = get_qemu_path()
    version = get_qemu_version()
    
    # Work with disk images
    from zstacklib.virtualization.qemu import check_image, get_image_info
    
    result = check_image('/var/lib/libvirt/images/vm.qcow2')
    if result.has_errors():
        print('Image has {} errors'.format(result.check_errors))
    
    info = get_image_info('/path/to/image.qcow2')
    
    # Communicate with VM via QGA
    from zstacklib.virtualization.qemu import VmQga
    
    import libvirt
    conn = libvirt.open('qemu:///system')
    domain = conn.lookupByName('my-vm')
    
    qga = VmQga(domain)
    if qga.is_running():
        # Execute command in guest
        exitcode, output = qga.guest_exec_bash('uname -a')
        print(output.decode())
        
        # Read file from guest
        count, data = qga.guest_file_read('/etc/os-release')
        print(data.decode())
"""

# Exceptions
from .exceptions import (
    QemuError,
    QemuPathNotFoundError,
    QemuVersionError,
    QgaException,
    QgaNotRunningError,
    QgaCommandError,
    QgaCommandDisabledError,
    QgaCommandNotSupportedError,
    # Error codes
    ERROR_CODE_VM_NOT_RUNNING,
    ERROR_CODE_VM_CONFIG_IPV6_NOT_SUPPORT,
    ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_IP,
    ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_GW,
    ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_MTU,
    ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_DNS,
    ERROR_CODE_VM_CONFIG_PERSISTENCE_FAILED,
    ERROR_CODE_VM_CONFIG_INTERNAL,
    ERROR_CODE_QGA_NOT_RUNNING,
    ERROR_CODE_QGA_OS_NOT_SUPPORT,
    ERROR_CODE_QGA_COMMAND_IS_DISABLED,
    ERROR_CODE_QGA_VERSION_TOO_LOWER,
    ERROR_CODE_QGA_COMMAND_ERROR,
    ERROR_CODE_QGA_RETURN_VALUE_ERROR,
)

# Models and constants
from .models import (
    # QGA constants
    QGA_CHANNEL_STATE_CONNECTED,
    QGA_CHANNEL_STATE_DISCONNECTED,
    QGA_STATE_RUNNING,
    QGA_STATE_NOT_RUNNING,
    QGA_EXEC_WAIT_INTERVAL,
    QGA_EXEC_WAIT_RETRY,
    ZS_TOOLS_WAIT_RETRY,
    ZS_TOOLS_PATH_WIN,
    # OS type constants
    VM_OS_LINUX_KYLIN,
    VM_OS_LINUX_UOS,
    VM_OS_LINUX_UBUNTU,
    VM_OS_LINUX_CENTOS,
    VM_OS_LINUX_OPEN_SUSE,
    VM_OS_LINUX_SUSE_S,
    VM_OS_LINUX_SUSE_D,
    VM_OS_LINUX_ORACLE,
    VM_OS_LINUX_REDHAT,
    VM_OS_WINDOWS,
    LINUX_OS_LIST,
    # Data classes
    QemuImgCheckResult,
    QgaInfo,
)

# Path utilities
from .path import (
    get_host_arch,
    get_colo_path,
    get_qemu_path,
    get_qemu_bin_dir,
    is_qemu_available,
)

# Version utilities
from .version import (
    get_qemu_version,
    get_version_from_exe,
    get_running_vm_version,
    compare_versions,
)

# qemu-img operations
from .img import (
    get_qemu_img_version,
    build_subcmd,
    check_image,
    get_image_info,
    create_image,
    convert_image,
    resize_image,
    snapshot_image,
    rebase_image,
    commit_image,
)

# Guest Agent
from .guest_agent import (
    get_qga_channel_state,
    is_qga_connected,
    VmQga,
)


__all__ = [
    # Exceptions
    'QemuError',
    'QemuPathNotFoundError',
    'QemuVersionError',
    'QgaException',
    'QgaNotRunningError',
    'QgaCommandError',
    'QgaCommandDisabledError',
    'QgaCommandNotSupportedError',
    # Error codes
    'ERROR_CODE_VM_NOT_RUNNING',
    'ERROR_CODE_VM_CONFIG_IPV6_NOT_SUPPORT',
    'ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_IP',
    'ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_GW',
    'ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_MTU',
    'ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_DNS',
    'ERROR_CODE_VM_CONFIG_PERSISTENCE_FAILED',
    'ERROR_CODE_VM_CONFIG_INTERNAL',
    'ERROR_CODE_QGA_NOT_RUNNING',
    'ERROR_CODE_QGA_OS_NOT_SUPPORT',
    'ERROR_CODE_QGA_COMMAND_IS_DISABLED',
    'ERROR_CODE_QGA_VERSION_TOO_LOWER',
    'ERROR_CODE_QGA_COMMAND_ERROR',
    'ERROR_CODE_QGA_RETURN_VALUE_ERROR',
    # QGA constants
    'QGA_CHANNEL_STATE_CONNECTED',
    'QGA_CHANNEL_STATE_DISCONNECTED',
    'QGA_STATE_RUNNING',
    'QGA_STATE_NOT_RUNNING',
    'QGA_EXEC_WAIT_INTERVAL',
    'QGA_EXEC_WAIT_RETRY',
    'ZS_TOOLS_WAIT_RETRY',
    'ZS_TOOLS_PATH_WIN',
    # OS type constants
    'VM_OS_LINUX_KYLIN',
    'VM_OS_LINUX_UOS',
    'VM_OS_LINUX_UBUNTU',
    'VM_OS_LINUX_CENTOS',
    'VM_OS_LINUX_OPEN_SUSE',
    'VM_OS_LINUX_SUSE_S',
    'VM_OS_LINUX_SUSE_D',
    'VM_OS_LINUX_ORACLE',
    'VM_OS_LINUX_REDHAT',
    'VM_OS_WINDOWS',
    'LINUX_OS_LIST',
    # Data classes
    'QemuImgCheckResult',
    'QgaInfo',
    # Path utilities
    'get_host_arch',
    'get_colo_path',
    'get_qemu_path',
    'get_qemu_bin_dir',
    'is_qemu_available',
    # Version utilities
    'get_qemu_version',
    'get_version_from_exe',
    'get_running_vm_version',
    'compare_versions',
    # qemu-img operations
    'get_qemu_img_version',
    'build_subcmd',
    'check_image',
    'get_image_info',
    'create_image',
    'convert_image',
    'resize_image',
    'snapshot_image',
    'rebase_image',
    'commit_image',
    # Guest Agent
    'get_qga_channel_state',
    'is_qga_connected',
    'VmQga',
]
