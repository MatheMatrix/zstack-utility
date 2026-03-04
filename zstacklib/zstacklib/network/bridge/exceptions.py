from __future__ import annotations


class BridgeError(Exception):
    """Base exception for bridge-related failures."""
    pass


class BridgeNotFoundError(BridgeError):
    """Raised when a bridge device is not found."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Bridge '{name}' not found")


class BridgeExistsError(BridgeError):
    """Raised when a bridge already exists."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Bridge '{name}' already exists")


class InterfaceOccupiedError(BridgeError):
    """Raised when an interface is already attached to another bridge."""
    def __init__(self, interface: str, bridge: str):
        """Init."""
        self.interface = interface
        self.bridge = bridge
        super().__init__(f"Interface '{interface}' already attached to bridge '{bridge}'")
