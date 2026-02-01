"""iSCSI exception classes.

This module defines exception hierarchy for iSCSI operations:

- IscsiError: Base exception for all iSCSI errors
  - DiscoveryError: Target discovery failed
  - LoginError: Session login failed
  - LogoutError: Session logout failed
  - SessionNotFoundError: Session does not exist
  - TargetNotFoundError: Target not found
  - ChapAuthError: CHAP authentication configuration failed
  - TimeoutError: Operation timed out
"""

from typing import Optional


class IscsiError(Exception):
    """Base exception for iSCSI operations."""
    
    def __init__(self, message: str, portal: Optional[str] = None, 
                 target: Optional[str] = None, return_code: Optional[int] = None):
        self.message = message
        self.portal = portal
        self.target = target
        self.return_code = return_code
        super(IscsiError, self).__init__(self._format_message())
    
    def _format_message(self) -> str:
        parts = [self.message]
        if self.portal:
            parts.append("portal={}".format(self.portal))
        if self.target:
            parts.append("target={}".format(self.target))
        if self.return_code is not None:
            parts.append("rc={}".format(self.return_code))
        return " ".join(parts)


class DiscoveryError(IscsiError):
    """iSCSI target discovery failed."""
    
    def __init__(self, portal: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(DiscoveryError, self).__init__(
            message=message or "Failed to discover iSCSI targets",
            portal=portal,
            return_code=return_code
        )


class LoginError(IscsiError):
    """iSCSI session login failed."""
    
    def __init__(self, portal: str, target: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(LoginError, self).__init__(
            message=message or "Failed to login to iSCSI target",
            portal=portal,
            target=target,
            return_code=return_code
        )


class LogoutError(IscsiError):
    """iSCSI session logout failed."""
    
    def __init__(self, portal: str, target: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(LogoutError, self).__init__(
            message=message or "Failed to logout from iSCSI target",
            portal=portal,
            target=target,
            return_code=return_code
        )


class SessionNotFoundError(IscsiError):
    """iSCSI session does not exist."""
    
    def __init__(self, portal: str, target: str, message: Optional[str] = None):
        super(SessionNotFoundError, self).__init__(
            message=message or "iSCSI session not found",
            portal=portal,
            target=target
        )


class TargetNotFoundError(IscsiError):
    """iSCSI target not found after discovery."""
    
    def __init__(self, portal: str, target: Optional[str] = None,
                 message: Optional[str] = None):
        super(TargetNotFoundError, self).__init__(
            message=message or "iSCSI target not found",
            portal=portal,
            target=target
        )


class ChapAuthError(IscsiError):
    """CHAP authentication configuration failed."""
    
    def __init__(self, portal: str, target: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(ChapAuthError, self).__init__(
            message=message or "Failed to configure CHAP authentication",
            portal=portal,
            target=target,
            return_code=return_code
        )


class TimeoutError(IscsiError):
    """iSCSI operation timed out."""
    
    def __init__(self, operation: str, timeout: int, portal: Optional[str] = None,
                 target: Optional[str] = None):
        super(TimeoutError, self).__init__(
            message="iSCSI {} timed out after {}s".format(operation, timeout),
            portal=portal,
            target=target
        )
        self.operation = operation
        self.timeout = timeout


class RescanError(IscsiError):
    """iSCSI session rescan failed."""
    
    def __init__(self, session_id: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(RescanError, self).__init__(
            message=message or "Failed to rescan iSCSI session",
            return_code=return_code
        )
        self.session_id = session_id


class NodeDeleteError(IscsiError):
    """iSCSI node deletion failed."""
    
    def __init__(self, portal: str, target: str, message: Optional[str] = None,
                 return_code: Optional[int] = None):
        super(NodeDeleteError, self).__init__(
            message=message or "Failed to delete iSCSI node",
            portal=portal,
            target=target,
            return_code=return_code
        )
