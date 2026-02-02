from __future__ import annotations


class BridgeError(Exception):
    pass


class BridgeNotFoundError(BridgeError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Bridge '{name}' not found")


class BridgeExistsError(BridgeError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Bridge '{name}' already exists")


class InterfaceOccupiedError(BridgeError):
    def __init__(self, interface: str, bridge: str):
        self.interface = interface
        self.bridge = bridge
        super().__init__(f"Interface '{interface}' already attached to bridge '{bridge}'")
