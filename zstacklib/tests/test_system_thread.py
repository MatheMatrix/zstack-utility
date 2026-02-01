"""Tests for system.thread module."""

import threading
import time

import pytest

from zstacklib.system.thread import (
    AsyncThread,
    run_in_thread,
    PeriodicTimer,
    AtomicInteger,
)


class TestRunInThread:
    def test_basic_thread_execution(self):
        result = {"value": None}
        
        def set_value():
            result["value"] = 42
        
        thread = run_in_thread(set_value)
        thread.join()
        assert result["value"] == 42

    def test_thread_with_args(self):
        result = {"value": None}
        
        def set_value(x, y):
            result["value"] = x + y
        
        thread = run_in_thread(set_value, args=(10, 20))
        thread.join()
        assert result["value"] == 30

    def test_thread_with_kwargs(self):
        result = {"value": None}
        
        def set_value(x, y=0):
            result["value"] = x + y
        
        thread = run_in_thread(set_value, args=(5,), kwargs={"y": 3})
        thread.join()
        assert result["value"] == 8

    def test_exception_does_not_crash(self):
        def raise_error():
            raise ValueError("test error")
        
        thread = run_in_thread(raise_error)
        thread.join()


class TestAsyncThread:
    def test_decorator(self):
        result = {"called": False}
        
        @AsyncThread
        def async_func():
            result["called"] = True
        
        thread = async_func()
        thread.join()
        assert result["called"] is True


class TestAtomicInteger:
    def test_initial_value(self):
        ai = AtomicInteger(10)
        assert ai.get() == 10

    def test_default_value(self):
        ai = AtomicInteger()
        assert ai.get() == 0

    def test_increment(self):
        ai = AtomicInteger(5)
        result = ai.inc()
        assert result == 6
        assert ai.get() == 6

    def test_decrement(self):
        ai = AtomicInteger(5)
        result = ai.dec()
        assert result == 4
        assert ai.get() == 4

    def test_set(self):
        ai = AtomicInteger(0)
        ai.set(100)
        assert ai.get() == 100

    def test_concurrent_increment(self):
        ai = AtomicInteger(0)
        num_threads = 10
        increments_per_thread = 100

        def increment_many():
            for _ in range(increments_per_thread):
                ai.inc()

        threads = [threading.Thread(target=increment_many) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ai.get() == num_threads * increments_per_thread


class TestPeriodicTimer:
    def test_periodic_execution(self):
        counter = AtomicInteger(0)
        
        def callback():
            if counter.inc() >= 3:
                return False
            return True
        
        timer = PeriodicTimer(0.05, callback)
        timer.start()
        time.sleep(0.3)
        
        assert counter.get() >= 3

    def test_cancel(self):
        counter = AtomicInteger(0)
        
        def callback():
            counter.inc()
            return True
        
        timer = PeriodicTimer(0.05, callback)
        timer.start()
        time.sleep(0.1)
        timer.cancel()
        
        count_at_cancel = counter.get()
        time.sleep(0.1)
        
        assert counter.get() <= count_at_cancel + 1
