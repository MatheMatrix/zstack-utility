# Copyright (c) ZStack.io, Inc.

"""
Ceph storage exception classes.

This module defines the exception hierarchy for Ceph operations.
"""

from typing import Optional


class CephError(Exception):
    """Base exception for all Ceph errors."""
    
    def __init__(self, message, pool_name=None, return_code=None):
        """Init."""
        # type: (str, Optional[str], Optional[int]) -> None
        super(CephError, self).__init__(message)
        self.pool_name = pool_name
        self.return_code = return_code


class CephConnectionError(CephError):
    """Exception raised when connection to Ceph cluster fails."""
    pass


class CephConfigError(CephError):
    """Exception raised for configuration errors."""
    pass


class CephPoolNotFoundError(CephError):
    """Exception raised when a pool is not found."""
    pass


class CephNbdError(CephError):
    """Exception raised for NBD-related errors."""
    pass


class CephMountError(CephError):
    """Exception raised when mount operation fails."""
    pass
