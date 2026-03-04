"""System lock module for thread and file locking utilities.

This module provides clean interfaces for synchronization:
- NamedLock: Named in-memory locks for thread synchronization
- FileLock: File-based locks for process synchronization
- Decorators: @lock() and @file_lock() for automatic locking
"""

from zstacklib.system.lock.named import (
    NamedLock,
    lock,
    get_lock,
)

from zstacklib.system.lock.file import (
    FileLock,
    Locker,
    Flock,
    Lockf,
    file_lock,
)

__all__ = [
    # Named locks
    'NamedLock',
    'lock',
    'get_lock',
    # File locks
    'FileLock',
    'Locker',
    'Flock',
    'Lockf',
    'file_lock',
]
