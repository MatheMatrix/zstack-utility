from __future__ import annotations


class ShellError(Exception):
    """Base exception for shell operations."""

    def __init__(self, message: str, command: str | None = None, return_code: int | None = None):
        super().__init__(message)
        self.command = command
        self.return_code = return_code


class CommandTimeoutError(ShellError):
    """Command execution timed out."""

    def __init__(self, command: str, timeout: float):
        super().__init__(f"Command timed out after {timeout}s: {command}", command=command)
        self.timeout = timeout


class CommandNotFoundError(ShellError):
    """Command executable not found."""

    def __init__(self, command: str):
        super().__init__(f"Command not found: {command}", command=command, return_code=127)
