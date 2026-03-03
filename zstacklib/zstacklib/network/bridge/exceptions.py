from __future__ import annotations


class BridgeError(Exception):
    """Bridgeerror."""
    pass


class BridgeNotFoundError(BridgeError):
    """Bridgenotfounderror."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Bridge '{name}' not found")


class BridgeExistsError(BridgeError):
    """Bridgeexistserror."""
    def __init__(self, name: str):
        """Init."""
        self.name = name
        super().__init__(f"Bridge '{name}' already exists")


class InterfaceOccupiedError(BridgeError):
    """Interfaceoccupiederror."""
    def __init__(self, interface: str, bridge: str):
        """Init."""
        self.interface = interface
        self.bridge = bridge
        super().__init__(f"Interface '{interface}' already attached to bridge '{bridge}'")
