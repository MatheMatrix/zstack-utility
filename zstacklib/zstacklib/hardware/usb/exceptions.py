from __future__ import annotations


class UsbError(Exception):
    pass


class UsbNotFoundError(UsbError):
    def __init__(self, device_id: str):
        self.device_id = device_id
        super().__init__(f"USB device '{device_id}' not found")


class UsbOperationError(UsbError):
    def __init__(self, device_id: str, operation: str, message: str):
        self.device_id = device_id
        self.operation = operation
        super().__init__(f"Failed to {operation} USB device '{device_id}': {message}")
