# Copyright (c) ZStack.io, Inc.

"""
DRBD exception classes.

This module defines the exception hierarchy for DRBD operations.
"""

from typing import Optional


class DrbdError(Exception):
    """Base exception for all DRBD errors."""
    
    def __init__(self, message, resource_name=None, return_code=None, stdout=None, stderr=None):
        """Init."""
        # type: (str, Optional[str], Optional[int], Optional[str], Optional[str]) -> None
        super(DrbdError, self).__init__(message)
        self.resource_name = resource_name
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class RetryException(DrbdError):
    """Exception raised to trigger retry logic."""
    pass


class DrbdResourceNotFoundError(DrbdError):
    """Exception raised when a DRBD resource is not found."""
    pass


class DrbdConfigError(DrbdError):
    """Exception raised for configuration errors."""
    pass


class DrbdPromoteError(DrbdError):
    """Exception raised when promote operation fails."""
    pass


class DrbdDemoteError(DrbdError):
    """Exception raised when demote operation fails."""
    pass


class DrbdConnectionError(DrbdError):
    """Exception raised for connection-related errors."""
    pass


class DrbdMinorConflictError(DrbdError):
    """Exception raised when device minor is already in use."""
    pass


class DrbdInstallError(DrbdError):
    """Exception raised when DRBD installation fails."""
    pass
