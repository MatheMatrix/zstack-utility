# Copyright (c) ZStack.io, Inc.

from __future__ import annotations


class NfsError(Exception):
    """Nfserror."""
    pass


class InvalidNfsUrlError(NfsError):
    """Invalidnfsurlerror."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Invalid NFS URL [{url}]'
        super().__init__(message)


class MountError(NfsError):
    """Mounterror."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Failed to mount NFS URL [{url}]'
        super().__init__(message)


class InvalidMountDomainError(NfsError):
    """Invalidmountdomainerror."""

    def __init__(self, url: str, msg: str | None = None):
        """Init."""
        self.url = url
        message = msg or f'Invalid mount domain [{url}]'
        super().__init__(message)


class InvalidMountPathError(NfsError):
    """Invalidmountpatherror."""

    def __init__(self, path: str, msg: str | None = None):
        """Init."""
        self.path = path
        message = msg or f'Invalid local mount path [{path}]'
        super().__init__(message)
