from __future__ import annotations


class LibvirtError(Exception):
    pass


class LibvirtConnectionError(LibvirtError):
    def __init__(self, uri: str, message: str = ""):
        self.uri = uri
        super().__init__(f"Failed to connect to libvirt at '{uri}': {message}" if message else f"Failed to connect to libvirt at '{uri}'")


class LibvirtNotAvailableError(LibvirtError):
    def __init__(self):
        super().__init__("libvirt is not installed or not available")


class DomainNotFoundError(LibvirtError):
    def __init__(self, domain: str):
        self.domain = domain
        super().__init__(f"Domain '{domain}' not found")


class DomainOperationError(LibvirtError):
    def __init__(self, domain: str, operation: str, message: str):
        self.domain = domain
        self.operation = operation
        super().__init__(f"Failed to {operation} domain '{domain}': {message}")
