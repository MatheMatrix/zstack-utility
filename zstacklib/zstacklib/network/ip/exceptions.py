# Copyright (c) ZStack.io, Inc.

"""
Network IP module exceptions.

This module defines all exceptions for the network.ip package,
providing structured error handling for IP, route, and namespace operations.
"""

from typing import Optional


class NoSuchNamespace(RuntimeError):
    """Raised when a network namespace does not exist."""
    
    def __init__(self, namespace):
        """Init."""
        # type: (str) -> None
        super(NoSuchNamespace, self).__init__(
            "Network namespace: %(namespace)s could not be found." % {'namespace': namespace}
        )
        self.namespace = namespace


class NamespaceAlreadyExists(RuntimeError):
    """Raised when trying to create a namespace that already exists."""
    
    def __init__(self, namespace):
        """Init."""
        # type: (str) -> None
        super(NamespaceAlreadyExists, self).__init__(
            "Network namespace: %(namespace)s already exists." % {'namespace': namespace}
        )
        self.namespace = namespace


class InvalidScope(RuntimeError):
    """Raised when an invalid scope value is provided."""
    
    def __init__(self, scope):
        """Init."""
        # type: (object) -> None
        super(InvalidScope, self).__init__(
            "Scope: %(scope)s is invalid." % {'scope': scope}
        )
        self.scope = scope


class InvalidIpVersion(RuntimeError):
    """Raised when an invalid IP version is provided (must be 4 or 6)."""
    
    def __init__(self, ip_version):
        """Init."""
        # type: (object) -> None
        super(InvalidIpVersion, self).__init__(
            "IP version: %(ip_version)s is invalid. Must be 4 or 6." % {'ip_version': ip_version}
        )
        self.ip_version = ip_version


class NoSuchLinkDevice(RuntimeError):
    """Raised when a network link device does not exist."""
    
    def __init__(self, ifname=None, index=None, cause=None):
        """Init."""
        # type: (Optional[str], Optional[int], Optional[str]) -> None
        message = "Link device(s):"
        if ifname is not None:
            message += " ifname=%s" % ifname
        if index is not None:
            message += " index=%s" % index
        message += " could not be found."
        if cause:
            message += " Because: %s" % cause
        
        super(NoSuchLinkDevice, self).__init__(message)
        self.ifname = ifname
        self.index = index
        self.cause = cause


class InvalidIpAddress(ValueError):
    """Raised when an invalid IP address format is provided."""
    
    def __init__(self, ip, reason=None):
        """Init."""
        # type: (str, Optional[str]) -> None
        message = "Invalid IP address: %s" % ip
        if reason:
            message += ". Reason: %s" % reason
        super(InvalidIpAddress, self).__init__(message)
        self.ip = ip
        self.reason = reason


class IpRouteError(RuntimeError):
    """Base exception for IP route operations."""
    
    def __init__(self, message, operation=None):
        """Init."""
        # type: (str, Optional[str]) -> None
        if operation:
            message = "[%s] %s" % (operation, message)
        super(IpRouteError, self).__init__(message)
        self.operation = operation
