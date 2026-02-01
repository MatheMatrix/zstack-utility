# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch exceptions.
"""

from __future__ import annotations


class OvsError(Exception):
    """Base exception for OVS operations."""
    pass


class OvsBridgeError(OvsError):
    """Raised when bridge operations fail."""

    def __init__(self, bridge: str, msg: str | None = None):
        self.bridge = bridge
        message = msg or f'Bridge operation failed for [{bridge}]'
        super().__init__(message)


class OvsPortError(OvsError):
    """Raised when port operations fail."""

    def __init__(self, port: str, bridge: str | None = None, msg: str | None = None):
        self.port = port
        self.bridge = bridge
        if bridge:
            message = msg or f'Port operation failed for [{port}] on bridge [{bridge}]'
        else:
            message = msg or f'Port operation failed for [{port}]'
        super().__init__(message)


class OvsDaemonError(OvsError):
    """Raised when OVS daemon operations fail."""

    def __init__(self, daemon: str, msg: str | None = None):
        self.daemon = daemon
        message = msg or f'Daemon operation failed for [{daemon}]'
        super().__init__(message)


class OvsDpdkError(OvsError):
    """Raised when DPDK-related operations fail."""

    def __init__(self, msg: str | None = None):
        message = msg or 'DPDK operation failed'
        super().__init__(message)


class OvsBondError(OvsError):
    """Raised when bond operations fail."""

    def __init__(self, bond_name: str, msg: str | None = None):
        self.bond_name = bond_name
        message = msg or f'Bond operation failed for [{bond_name}]'
        super().__init__(message)


class OvsConfigError(OvsError):
    """Raised when OVS configuration fails."""

    def __init__(self, key: str, value: str | None = None, msg: str | None = None):
        self.key = key
        self.value = value
        if value:
            message = msg or f'Configuration failed for [{key}={value}]'
        else:
            message = msg or f'Configuration failed for [{key}]'
        super().__init__(message)
