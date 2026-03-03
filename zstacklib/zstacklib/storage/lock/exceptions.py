from __future__ import annotations


class LockError(Exception):
    """Lockerror."""
    pass


class LockAcquireError(LockError):
    """Lockacquireerror."""
    def __init__(self, resource: str, message: str):
        """Init."""
        self.resource = resource
        super().__init__(f"Failed to acquire lock for '{resource}': {message}")


class LockReleaseError(LockError):
    """Lockreleaseerror."""
    def __init__(self, resource: str, message: str):
        """Init."""
        self.resource = resource
        super().__init__(f"Failed to release lock for '{resource}': {message}")


class LockNotHeldError(LockError):
    """Locknothelderror."""
    def __init__(self, resource: str):
        """Init."""
        self.resource = resource
        super().__init__(f"Lock for '{resource}' is not held")
