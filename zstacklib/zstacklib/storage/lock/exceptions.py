from __future__ import annotations


class LockError(Exception):
    pass


class LockAcquireError(LockError):
    def __init__(self, resource: str, message: str):
        self.resource = resource
        super().__init__(f"Failed to acquire lock for '{resource}': {message}")


class LockReleaseError(LockError):
    def __init__(self, resource: str, message: str):
        self.resource = resource
        super().__init__(f"Failed to release lock for '{resource}': {message}")


class LockNotHeldError(LockError):
    def __init__(self, resource: str):
        self.resource = resource
        super().__init__(f"Lock for '{resource}' is not held")
