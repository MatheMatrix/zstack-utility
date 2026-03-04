"""Multipath exception classes.

This module defines exception hierarchy for multipath operations:

- MultipathError: Base exception for all multipath errors
  - MultipathNotRunningError: multipathd daemon not running
  - MultipathConfigError: Configuration file error
  - DeviceNotFoundError: Multipath device not found
"""

from typing import Optional


class MultipathError(Exception):
    """Base exception for multipath operations."""
    
    def __init__(self, message: str, device: Optional[str] = None,
                 return_code: Optional[int] = None):
        """Init."""
        self.message = message
        self.device = device
        self.return_code = return_code
        super(MultipathError, self).__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format message."""
        parts = [self.message]
        if self.device:
            parts.append("device={}".format(self.device))
        if self.return_code is not None:
            parts.append("rc={}".format(self.return_code))
        return " ".join(parts)


class MultipathNotRunningError(MultipathError):
    """multipathd daemon is not running."""
    
    def __init__(self, message: Optional[str] = None):
        """Init."""
        super(MultipathNotRunningError, self).__init__(
            message=message or "multipathd is not running"
        )


class MultipathConfigError(MultipathError):
    """Multipath configuration file error."""
    
    def __init__(self, path: str, message: Optional[str] = None):
        """Init."""
        super(MultipathConfigError, self).__init__(
            message=message or "Invalid multipath configuration: {}".format(path)
        )
        self.path = path


class DeviceNotFoundError(MultipathError):
    """Multipath device not found."""
    
    def __init__(self, device: str, message: Optional[str] = None):
        """Init."""
        super(DeviceNotFoundError, self).__init__(
            message=message or "Multipath device not found",
            device=device
        )


class ServiceError(MultipathError):
    """Multipath service operation failed."""
    
    def __init__(self, operation: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        """Init."""
        super(ServiceError, self).__init__(
            message=message or "Multipath service {} failed".format(operation),
            return_code=return_code
        )
        self.operation = operation
