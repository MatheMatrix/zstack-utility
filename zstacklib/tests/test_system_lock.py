"""Tests for system.lock module."""

import threading
import time
import tempfile
import os
from pathlib import Path

import pytest

from zstacklib.system.lock import (
    NamedLock,
    lock,
    get_lock,
    FileLock,
    Flock,
    Lockf,
    file_lock,
)


class TestNamedLock:
    def test_basic_lock(self):
        with NamedLock("test1"):
            pass

    def test_same_name_returns_same_lock(self):
        lock1 = get_lock("shared")
        lock2 = get_lock("shared")
        assert lock1 is lock2

    def test_different_names_return_different_locks(self):
        lock1 = get_lock("name_a")
        lock2 = get_lock("name_b")
        assert lock1 is not lock2

    def test_lock_decorator(self):
        counter = {"value": 0}

        @lock("counter_lock")
        def increment():
            counter["value"] += 1

        increment()
        increment()
        assert counter["value"] == 2

    def test_concurrent_access(self):
        results = []
        
        @lock("concurrent_test")
        def append_with_delay(value):
            results.append(f"start_{value}")
            time.sleep(0.01)
            results.append(f"end_{value}")

        threads = [
            threading.Thread(target=append_with_delay, args=(i,))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(3):
            start_idx = results.index(f"start_{i}")
            end_idx = results.index(f"end_{i}")
            assert end_idx == start_idx + 1


class TestFileLock:
    def test_basic_file_lock(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        with FileLock(str(lock_path)):
            assert lock_path.exists()

    def test_file_lock_with_lockf(self, tmp_path):
        lock_path = tmp_path / "lockf.lock"
        with FileLock(str(lock_path), Lockf()):
            assert lock_path.exists()

    def test_file_lock_with_flock(self, tmp_path):
        lock_path = tmp_path / "flock.lock"
        with FileLock(str(lock_path), Flock()):
            assert lock_path.exists()

    def test_file_lock_creates_parent_dirs(self, tmp_path):
        lock_path = tmp_path / "nested" / "dir" / "test.lock"
        with FileLock(str(lock_path)):
            assert lock_path.exists()
