from __future__ import annotations


class NamespaceError(Exception):
    """Base exception for namespace-related errors."""
    pass


class NamespaceNotFoundError(NamespaceError):
    """Raised when a network namespace is not found."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Network namespace '{name}' not found")


class NamespaceExistsError(NamespaceError):
    """Raised when a network namespace already exists."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Network namespace '{name}' already exists")


class NamespaceExecError(NamespaceError):
    """Raised when command execution in a namespace fails."""
    def __init__(self, namespace: str, command: str, message: str):
        """Init."""
        self.namespace = namespace
        self.command = command
        super().__init__(f"Failed to execute '{command}' in namespace '{namespace}': {message}")
