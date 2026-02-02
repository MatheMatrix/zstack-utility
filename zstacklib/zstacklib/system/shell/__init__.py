from __future__ import annotations

from .exceptions import CommandNotFoundError, CommandTimeoutError, ShellError
from .models import CommandResult, ShellContext

_EXECUTOR_EXPORTS = {"ShellExecutor", "call", "run", "check_run"}


def __getattr__(name: str):
    if name in _EXECUTOR_EXPORTS:
        from . import executor
        return getattr(executor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ShellError",
    "CommandTimeoutError",
    "CommandNotFoundError",
    "CommandResult",
    "ShellContext",
    "ShellExecutor",
    "call",
    "run",
    "check_run",
]
