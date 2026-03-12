# -*- coding: utf-8 -*-
"""Unit tests for ZStackDaemon base class (daemon.py).

Covers the lifecycle contract (start/stop/run), health state, and
the SIGHUP on_reload hook.  All tests run without forking or touching
the file system.
"""
import os
import sys
import signal
import threading
import time
import unittest
from unittest import mock

# Ensure zstacklib is importable when running from the worktree root
_here = os.path.dirname(os.path.abspath(__file__))
_zstacklib_root = os.path.abspath(os.path.join(_here, '..', '..'))
if _zstacklib_root not in sys.path:
    sys.path.insert(0, _zstacklib_root)

# ZStackDaemon only depends on `logger` from the module level of daemon.py.
# Patch it before import so there is no real log file I/O.
#
# conftest.py (in the zstacklib/ parent dir) stubs out zstacklib.utils.daemon
# as a plain MagicMock so GPU tests don't pull in the real daemon.  We must
# pop that stub *before* importing the real module here.
import types as _types

_ORIGINAL_MODULES = {}
_ORIGINAL_PARENT_ATTRS = {}  # (parent_fqn, attr_name) -> old_value | _SENTINEL

_SENTINEL = object()

def _patch_module(name, value):
    if name not in _ORIGINAL_MODULES:
        _ORIGINAL_MODULES[name] = sys.modules.get(name)
    sys.modules[name] = value
    # Sync the attribute on the parent package so that
    # ``from parent import child`` returns *value*, not a stale cache.
    if '.' in name:
        parent_fqn, attr = name.rsplit('.', 1)
        parent = sys.modules.get(parent_fqn)
        if parent is not None:
            key = (parent_fqn, attr)
            if key not in _ORIGINAL_PARENT_ATTRS:
                _ORIGINAL_PARENT_ATTRS[key] = getattr(parent, attr, _SENTINEL)
            setattr(parent, attr, value)

_mock_log = _types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda _name: mock.MagicMock()
_patch_module('zstacklib.utils.log', _mock_log)
_patch_module('log', _mock_log)
_patch_module('zstacklib.utils.linux', mock.MagicMock())
_ORIGINAL_MODULES.setdefault('zstacklib.utils.daemon', sys.modules.get('zstacklib.utils.daemon'))
sys.modules.pop('zstacklib.utils.daemon', None)  # clear conftest stub

from zstacklib.utils.daemon import ZStackDaemon  # noqa: E402


def tearDownModule():
    for name, old in _ORIGINAL_MODULES.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old
    for (parent_fqn, attr), old_val in _ORIGINAL_PARENT_ATTRS.items():
        parent = sys.modules.get(parent_fqn)
        if parent is None:
            continue
        if old_val is _SENTINEL:
            try:
                delattr(parent, attr)
            except AttributeError:
                pass
        else:
            setattr(parent, attr, old_val)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _CountingService(ZStackDaemon):
    """Service that counts run() invocations and stops after max_ticks."""

    def __init__(self, name='test-svc', max_ticks=1):
        super(_CountingService, self).__init__(name)
        self.ticks = 0
        self.max_ticks = max_ticks
        self.reload_calls = 0

    def run(self):
        while self.is_healthy() and self.ticks < self.max_ticks:
            self.ticks += 1
        self.stop()

    def on_reload(self):
        self.reload_calls += 1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestZStackDaemonLifecycle(unittest.TestCase):

    def test_initial_state_is_healthy_and_not_running(self):
        svc = ZStackDaemon('test')
        self.assertTrue(svc.is_healthy())
        self.assertFalse(svc.is_running())

    def test_run_must_be_overridden(self):
        svc = ZStackDaemon('test')
        with self.assertRaises(NotImplementedError):
            svc.run()

    def test_start_calls_run_and_sets_running(self):
        running_during_run = []

        class _Svc(ZStackDaemon):
            def run(self):
                running_during_run.append(self.is_running())
                self.stop()

        svc = _Svc('test')
        svc.start()
        self.assertEqual([True], running_during_run)
        self.assertFalse(svc.is_running())  # cleaned up after run()

    def test_stop_sets_healthy_false_and_running_false(self):
        svc = _CountingService()
        svc._running = True  # simulate running
        svc.stop()
        self.assertFalse(svc.is_healthy())
        self.assertFalse(svc.is_running())

    def test_start_restores_running_to_false_after_completion(self):
        svc = _CountingService(max_ticks=1)
        svc.start()
        self.assertFalse(svc.is_running())

    def test_counting_service_runs_correct_number_of_ticks(self):
        svc = _CountingService(max_ticks=3)
        svc.start()
        self.assertEqual(3, svc.ticks)


class TestZStackDaemonHealth(unittest.TestCase):

    def test_set_healthy_false(self):
        svc = ZStackDaemon('test')
        svc.set_healthy(False)
        self.assertFalse(svc.is_healthy())

    def test_set_healthy_true(self):
        svc = ZStackDaemon('test')
        svc.set_healthy(False)
        svc.set_healthy(True)
        self.assertTrue(svc.is_healthy())

    def test_set_healthy_default_is_true(self):
        svc = ZStackDaemon('test')
        svc.set_healthy(False)
        svc.set_healthy()
        self.assertTrue(svc.is_healthy())


class TestZStackDaemonOnReload(unittest.TestCase):

    def test_on_reload_default_is_noop(self):
        svc = ZStackDaemon('test')
        svc.on_reload()  # must not raise

    def test_on_reload_called_on_sighup(self):
        svc = _CountingService()
        svc._install_signal_handlers()
        try:
            os.kill(os.getpid(), signal.SIGHUP)
            # Give the signal handler a moment to fire
            time.sleep(0.05)
        finally:
            svc._restore_signal_handlers()
        self.assertEqual(1, svc.reload_calls)

    def test_on_reload_exception_does_not_propagate(self):
        class _BadReload(ZStackDaemon):
            def run(self):
                pass

            def on_reload(self):
                raise RuntimeError("intentional failure")

        svc = _BadReload('test')
        svc._install_signal_handlers()
        try:
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.05)
        finally:
            svc._restore_signal_handlers()
        # No exception leaked to the caller

    def test_signal_handlers_restored_after_start(self):
        original_hup = signal.getsignal(signal.SIGHUP)
        original_term = signal.getsignal(signal.SIGTERM)
        svc = _CountingService()
        svc.start()
        self.assertEqual(original_hup, signal.getsignal(signal.SIGHUP))
        self.assertEqual(original_term, signal.getsignal(signal.SIGTERM))

    def test_sigterm_triggers_stop(self):
        class _LongSvc(ZStackDaemon):
            def run(self):
                while self.is_healthy():
                    time.sleep(0.01)

        svc = _LongSvc('test')
        # Install handlers from main thread (signal.signal requires it)
        svc._install_signal_handlers()
        try:
            t = threading.Thread(target=svc.run)
            svc._running = True
            t.start()
            time.sleep(0.05)
            os.kill(os.getpid(), signal.SIGTERM)
            t.join(timeout=2)
            self.assertFalse(svc.is_healthy())
            self.assertFalse(t.is_alive())
        finally:
            svc._restore_signal_handlers()


if __name__ == '__main__':
    unittest.main()
