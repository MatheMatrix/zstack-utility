# Copyright (c) ZStack.io, Inc.

from __future__ import annotations


class NfsError(Exception):
    """Base class for NFS-related errors."""
    pass


class InvalidNfsUrlError(NfsError):
    """Raised when an NFS URL is invalid."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Invalid NFS URL [{url}]'
        super().__init__(message)


class MountError(NfsError):
    """Raised when mounting an NFS URL fails."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Failed to mount NFS URL [{url}]'
        super().__init__(message)


class InvalidMountDomainError(NfsError):
    """Raised when the mount domain is invalid."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Invalid mount domain [{url}]'
        super().__init__(message)


class InvalidMountPathError(NfsError):
    """Raised when the local mount path is invalid."""

    def __init__(self, path: str, msg: str | None = None):
        """Init."""
        self.path = path
        message = msg or f'Invalid local mount path [{path}]'
        super().__init__(message)
