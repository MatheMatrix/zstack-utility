from __future__ import annotations


class VmError(Exception):
    pass


class VmNotFoundError(VmError):
    def __init__(self, vm_id: str):
        self.vm_id = vm_id
        super().__init__(f"VM '{vm_id}' not found")


class VmStateError(VmError):
    def __init__(self, vm_id: str, current_state: str, expected_state: str):
        self.vm_id = vm_id
        self.current_state = current_state
        self.expected_state = expected_state
        super().__init__(f"VM '{vm_id}' is in state '{current_state}', expected '{expected_state}'")


class VmOperationError(VmError):
    def __init__(self, vm_id: str, operation: str, message: str):
        self.vm_id = vm_id
        self.operation = operation
        super().__init__(f"Failed to {operation} VM '{vm_id}': {message}")


class VmXmlParseError(VmError):
    def __init__(self, message: str):
        super().__init__(f"Failed to parse VM XML: {message}")
