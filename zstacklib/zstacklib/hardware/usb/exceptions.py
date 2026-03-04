from __future__ import annotations


class UsbError(Exception):
    """Base exception for USB-related errors."""
    pass


class UsbNotFoundError(UsbError):
    """Raised when a USB device is not found."""
    def __init__(self, device_id: str):
        """Init."""
        self.device_id = device_id
        super().__init__(f"USB device '{device_id}' not found")


class UsbOperationError(UsbError):
    """Raised when a USB device operation fails."""
    def __init__(self, device_id: str, operation: str, message: str):
        """Init."""
        self.device_id = device_id
        self.operation = operation
        super().__init__(f"Failed to {operation} USB device '{device_id}': {message}")
