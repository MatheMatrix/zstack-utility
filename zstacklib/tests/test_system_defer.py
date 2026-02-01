"""Tests for system.defer module."""

import pytest

from zstacklib.system.defer import defer, protect


class TestDefer:
    def test_basic_defer(self):
        order = []
        
        @protect
        def func():
            defer(lambda: order.append("deferred"))
            order.append("main")
        
        func()
        assert order == ["main", "deferred"]

    def test_multiple_defers_lifo(self):
        order = []
        
        @protect
        def func():
            defer(lambda: order.append("first"))
            defer(lambda: order.append("second"))
            defer(lambda: order.append("third"))
            order.append("main")
        
        func()
        assert order == ["main", "third", "second", "first"]

    def test_defer_runs_on_exception(self):
        order = []
        
        @protect
        def func():
            defer(lambda: order.append("cleanup"))
            order.append("before")
            raise ValueError("test")
        
        with pytest.raises(ValueError):
            func()
        
        assert order == ["before", "cleanup"]

    def test_defer_without_protect_raises(self):
        with pytest.raises(RuntimeError):
            defer(lambda: None)

    def test_defer_with_return_value(self):
        @protect
        def func():
            defer(lambda: None)
            return 42
        
        assert func() == 42

    def test_nested_protect(self):
        order = []
        
        @protect
        def outer():
            defer(lambda: order.append("outer_defer"))
            order.append("outer_start")
            inner()
            order.append("outer_end")
        
        @protect
        def inner():
            defer(lambda: order.append("inner_defer"))
            order.append("inner")
        
        outer()
        assert order == [
            "outer_start",
            "inner",
            "inner_defer",
            "outer_end",
            "outer_defer"
        ]

    def test_defer_exception_handling(self):
        order = []
        
        @protect
        def func():
            defer(lambda: order.append("ok"))
            defer(lambda: (_ for _ in ()).throw(ValueError("ignored")))
            defer(lambda: order.append("also_ok"))
            order.append("main")
        
        func()
        assert "main" in order
        assert "ok" in order
        assert "also_ok" in order
