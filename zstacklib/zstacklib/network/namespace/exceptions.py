from __future__ import annotations


class NamespaceError(Exception):
    pass


class NamespaceNotFoundError(NamespaceError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Network namespace '{name}' not found")


class NamespaceExistsError(NamespaceError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Network namespace '{name}' already exists")


class NamespaceExecError(NamespaceError):
    def __init__(self, namespace: str, command: str, message: str):
        self.namespace = namespace
        self.command = command
        super().__init__(f"Failed to execute '{command}' in namespace '{namespace}': {message}")
