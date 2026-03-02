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

_mock_log = _types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: mock.MagicMock()
sys.modules['zstacklib.utils.log'] = _mock_log
sys.modules['log'] = _mock_log
sys.modules['zstacklib.utils.linux'] = mock.MagicMock()
sys.modules.pop('zstacklib.utils.daemon', None)  # clear conftest stub

from zstacklib.utils.daemon import ZStackDaemon  # noqa: E402


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
            self.stop()  # stop after first tick by default

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
        # Override stop so ticks can accumulate
        svc.stop = lambda: None

        class _MultiSvc(ZStackDaemon):
            def run(self):
                for _ in range(3):
                    if not self.is_healthy():
                        break
                    self.ticks = getattr(self, 'ticks', 0) + 1

        ms = _MultiSvc('test')
        ms.start()
        self.assertEqual(3, ms.ticks)


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
        original = signal.getsignal(signal.SIGHUP)
        svc = _CountingService()
        svc.start()
        self.assertEqual(original, signal.getsignal(signal.SIGHUP))


if __name__ == '__main__':
    unittest.main()
