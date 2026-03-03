from __future__ import annotations


class NamespaceError(Exception):
    """Namespaceerror."""
    pass


class NamespaceNotFoundError(NamespaceError):
    """Namespacenotfounderror."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Network namespace '{name}' not found")


class NamespaceExistsError(NamespaceError):
    """Namespaceexistserror."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Network namespace '{name}' already exists")


class NamespaceExecError(NamespaceError):
    """Namespaceexecerror."""
    def __init__(self, namespace: str, command: str, message: str):
        """Init."""
        self.namespace = namespace
        self.command = command
        super().__init__(f"Failed to execute '{command}' in namespace '{namespace}': {message}")
