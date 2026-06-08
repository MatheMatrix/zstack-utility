# Copyright (c) ZStack.io, Inc.

"""
QEMU-related exceptions.

Provides exception classes for QEMU Guest Agent and QEMU operations.
"""

from typing import Optional


# Error codes for QGA operations
ERROR_CODE_VM_NOT_RUNNING = 'VM_NOT_RUNNING'
ERROR_CODE_VM_CONFIG_IPV6_NOT_SUPPORT = 'VM_CONFIG_IPV6_NOT_SUPPORT'
ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_IP = 'VM_CONFIG_NOT_EFFECTIVE_NET_IP'
ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_GW = 'VM_CONFIG_NOT_EFFECTIVE_NET_GW'
ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_MTU = 'VM_CONFIG_NOT_EFFECTIVE_NET_MTU'
ERROR_CODE_VM_CONFIG_NOT_EFFECTIVE_DNS = 'VM_CONFIG_NOT_EFFECTIVE_NET_DNS'
ERROR_CODE_VM_CONFIG_PERSISTENCE_FAILED = 'VM_CONFIG_PERSISTENCE_FAILED'
ERROR_CODE_VM_CONFIG_INTERNAL = 'VM_CONFIG_INTERNAL'
ERROR_CODE_QGA_NOT_RUNNING = 'QGA_NOT_RUNNING'
ERROR_CODE_QGA_OS_NOT_SUPPORT = 'QGA_OS_NOT_SUPPORT'
ERROR_CODE_QGA_COMMAND_IS_DISABLED = 'QGA_COMMAND_IS_DISABLED'
ERROR_CODE_QGA_VERSION_TOO_LOWER = 'QGA_VERSION_TOO_LOWER'
ERROR_CODE_QGA_COMMAND_ERROR = 'QGA_COMMAND_EXEC_ERROR'
ERROR_CODE_QGA_RETURN_VALUE_ERROR = 'QGA_RETURN_VALUE_ERROR'


class QemuError(Exception):
    """Base exception for QEMU operations."""
    pass


class QgaException(Exception):
    """Exception class for QEMU Guest Agent operations.
    
    Attributes:
        error_code: A string code identifying the type of error.
        message: Human-readable error message.
    """

    def __init__(self, error_code, msg=None):
        # type: (str, Optional[str]) -> None
        self.error_code = error_code
        super(QgaException, self).__init__('QGA exception' if msg is None else msg)


class QgaNotRunningError(QgaException):
    """Raised when QGA is not running on the VM."""

    def __init__(self, vm_uuid, msg=None):
        # type: (str, Optional[str]) -> None
        self.vm_uuid = vm_uuid
        message = msg or 'QGA is not running on VM {}'.format(vm_uuid)
        super(QgaNotRunningError, self).__init__(ERROR_CODE_QGA_NOT_RUNNING, message)


class QgaCommandError(QgaException):
    """Raised when a QGA command fails to execute."""

    def __init__(self, command, vm_uuid, msg=None):
        # type: (str, str, Optional[str]) -> None
        self.command = command
        self.vm_uuid = vm_uuid
        message = msg or 'QGA command {} failed on VM {}'.format(command, vm_uuid)
        super(QgaCommandError, self).__init__(ERROR_CODE_QGA_COMMAND_ERROR, message)


class QgaCommandDisabledError(QgaException):
    """Raised when a QGA command is disabled."""

    def __init__(self, command, vm_uuid):
        # type: (str, str) -> None
        self.command = command
        self.vm_uuid = vm_uuid
        message = 'QGA command {} is disabled on VM {}'.format(command, vm_uuid)
        super(QgaCommandDisabledError, self).__init__(
            ERROR_CODE_QGA_COMMAND_IS_DISABLED, message
        )


class QgaCommandNotSupportedError(QgaException):
    """Raised when a QGA command is not supported."""

    def __init__(self, command, version, vm_uuid):
        # type: (str, str, str) -> None
        self.command = command
        self.version = version
        self.vm_uuid = vm_uuid
        message = 'QGA command {} not supported, QGA version is {}'.format(
            command, version
        )
        super(QgaCommandNotSupportedError, self).__init__(
            ERROR_CODE_QGA_VERSION_TOO_LOWER, message
        )


class QemuPathNotFoundError(QemuError):
    """Raised when QEMU binary path cannot be found."""
    pass


class QemuVersionError(QemuError):
    """Raised when QEMU version cannot be determined."""
    pass
