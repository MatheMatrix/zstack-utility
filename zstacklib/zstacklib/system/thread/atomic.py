from __future__ import annotations

import threading


class AtomicInteger:
    def __init__(self, value: int = 0):
        self._value = value
        self._lock = threading.Lock()

    def inc(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    def dec(self) -> int:
        with self._lock:
            self._value -= 1
            return self._value

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, value: int) -> None:
        with self._lock:
            self._value = value
