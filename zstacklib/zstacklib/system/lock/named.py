"""Named in-memory locks for thread synchronization."""

from __future__ import annotations

import functools
import threading
import weakref
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

_internal_lock = threading.RLock()
_locks: weakref.WeakValueDictionary[str, threading.RLock] = weakref.WeakValueDictionary()


def get_lock(name: str) -> threading.RLock:
    with _internal_lock:
        lock = _locks.get(name)
        if lock is None:
            lock = threading.RLock()
            _locks[name] = lock
        return lock


class NamedLock:
    def __init__(self, name: str):
        self.name = name
        self._lock: threading.RLock | None = None

    def __enter__(self) -> NamedLock:
        self._lock = get_lock(self.name)
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._lock:
            self._lock.release()


def lock(name: str = 'defaultLock') -> Callable[[Callable[P, T]], Callable[P, T]]:
    def wrap(f: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(f)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            with NamedLock(name):
                return f(*args, **kwargs)
        return inner
    return wrap
