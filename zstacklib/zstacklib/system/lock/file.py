"""File-based locks for process synchronization."""

from __future__ import annotations

import fcntl
import functools
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, TypeVar, ParamSpec

from zstacklib.system.lock.named import NamedLock

P = ParamSpec('P')
T = TypeVar('T')

LOCK_DIR = Path('/var/lib/zstack/lock/')


class Locker(ABC):
    @abstractmethod
    def lock(self, lock_file) -> None:
        raise NotImplementedError

    @abstractmethod
    def unlock(self, lock_file) -> None:
        raise NotImplementedError


class Flock(Locker):
    def lock(self, lock_file) -> None:
        fcntl.flock(lock_file, fcntl.LOCK_EX)

    def unlock(self, lock_file) -> None:
        fcntl.flock(lock_file, fcntl.LOCK_UN)


class Lockf(Locker):
    def lock(self, lock_file) -> None:
        fcntl.lockf(lock_file, fcntl.LOCK_EX)

    def unlock(self, lock_file) -> None:
        fcntl.lockf(lock_file, fcntl.LOCK_UN)


class FileLock:
    def __init__(self, lock_prefix: str, locker: Locker | None = None):
        self._locker = locker or Lockf()
        self._lock_file = None
        self._lock_path = self._prepare_lock_path(lock_prefix)

    def _prepare_lock_path(self, lock_prefix: str) -> Path:
        if os.path.isabs(lock_prefix):
            path = Path(lock_prefix)
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        else:
            LOCK_DIR.mkdir(parents=True, exist_ok=True)
            return LOCK_DIR / f'{lock_prefix}.lock'

    def lock(self) -> None:
        self._lock_file = open(self._lock_path, 'w')
        os.chmod(self._lock_path, 0o600)
        self._locker.lock(self._lock_file)

    def unlock(self) -> None:
        if self._lock_file:
            try:
                self._locker.unlock(self._lock_file)
            finally:
                self._lock_file.close()
                self._lock_file = None

    def __enter__(self) -> FileLock:
        self.lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.unlock()


def file_lock(
    name: str,
    locker: Locker | None = None,
    debug: bool = False
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def wrap(f: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(f)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            with NamedLock(name):
                with FileLock(name, locker or Lockf()):
                    return f(*args, **kwargs)
        return inner
    return wrap
