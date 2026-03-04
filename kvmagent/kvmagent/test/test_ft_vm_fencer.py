# -*- coding: utf-8 -*-
"""Characterisation tests for FaultToleranceFecnerPlugin lifecycle.

Tests the fencer timestamp state machine (setup / run / cancel) which is
safety-critical: incorrect behaviour can cause split-brain in FT VM setups.

These tests describe CURRENT behaviour, including surprising edge-cases
(e.g. KeyError when host_uuid not registered), so future refactors have
a clear baseline to compare against.
"""
import os
import sys
import json
import types
import threading
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# 1. Add real package roots to sys.path so the kvmagent package structure is
#    discoverable without being installed (setup.py develop / pip -e).
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
_kvmagent_root = os.path.abspath(os.path.join(_here, '..', '..'))       # .../kvmagent/
_repo_root = os.path.abspath(os.path.join(_here, '..', '..', '..'))     # .../zstack-utility-services/
_zstacklib_root = os.path.join(_repo_root, 'zstacklib')                  # .../zstacklib/

for _p in (_kvmagent_root, _zstacklib_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# 2. Mock heavy / Py2-only dependencies BEFORE any project import.
#    Order matters: log → bash → everything else.
# ---------------------------------------------------------------------------

_ORIGINAL_MODULES = {}

def _patch_module(name, value):
    if name not in _ORIGINAL_MODULES:
        _ORIGINAL_MODULES[name] = sys.modules.get(name)
    sys.modules[name] = value

_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda _name: mock.MagicMock()
_patch_module('zstacklib.utils.log', _mock_log)
_patch_module('log', _mock_log)

# bash star-import exposes: bash_roe, bash_ro, bash_r, bash_o, in_bash, json
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log
_mock_bash.bash_roe = mock.MagicMock(return_value=(0, '', ''))
_mock_bash.bash_ro = mock.MagicMock(return_value=(0, ''))
_mock_bash.bash_r = mock.MagicMock(return_value=0)
_mock_bash.bash_o = mock.MagicMock(return_value='')
_mock_bash.in_bash = staticmethod(lambda f: f)   # identity decorator
_mock_bash.json = json                            # ft_vm_fencer uses json.loads
_patch_module('zstacklib.utils.bash', _mock_bash)

for _mod in [
    'zstacklib.utils.shell',
    'zstacklib.utils.linux',
    'zstacklib.utils.lvm',
    'zstacklib.utils.thread',
    'zstacklib.utils.drbd',
    'zstacklib.utils.qemu_img',
    'zstacklib.utils.jsonobject',
    'zstacklib.utils.http',
    'zstacklib.utils.ovn',
]:
    _patch_module(_mod, mock.MagicMock())

# Mock kvmagent.kvmagent (the inner module with KvmAgent, replyerror, etc.)
# We use the REAL kvmagent package structure (from sys.path), but intercept
# kvmagent.kvmagent before it tries to import its own heavy dependencies.
_mock_kvmagent_mod = types.ModuleType('kvmagent.kvmagent')


class _KvmAgent(object):
    """Minimal stub for kvmagent.KvmAgent."""
    def configure(self, config=None):
        pass

    def start(self):
        pass

    def stop(self):
        pass


_mock_kvmagent_mod.KvmAgent = _KvmAgent
_mock_kvmagent_mod.replyerror = staticmethod(lambda f: f)
_mock_kvmagent_mod.get_http_server = mock.MagicMock()
_mock_kvmagent_mod.SEND_COMMAND_URL = 'send_command_url'
_mock_kvmagent_mod.HOST_UUID = 'host_uuid'
_patch_module('kvmagent.kvmagent', _mock_kvmagent_mod)


def tearDownModule():
    for name, old in _ORIGINAL_MODULES.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old

# ---------------------------------------------------------------------------
# 3. Import the module under test
# ---------------------------------------------------------------------------
from kvmagent.plugins.services.ft_vm_fencer import FaultToleranceFecnerPlugin  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFencerLifecycle(unittest.TestCase):
    """Characterisation tests for the fencer timestamp state machine.

    All three public methods (setup_fencer / run_fencer / cancel_fencer)
    only touch self.run_fencer_timestamp and self.fencer_lock — no I/O,
    no shell calls — so they are fully testable without a real host.
    """

    def _make_plugin(self):
        p = FaultToleranceFecnerPlugin()
        p.configure({})
        return p

    # --- setup_fencer ---------------------------------------------------------

    def test_setup_fencer_stores_timestamp(self):
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        self.assertEqual(p.run_fencer_timestamp['host-1'], 1000.0)

    def test_setup_fencer_overwrites_previous_timestamp(self):
        """A second setup call replaces the stored timestamp."""
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        p.setup_fencer('host-1', 2000.0)
        self.assertEqual(p.run_fencer_timestamp['host-1'], 2000.0)

    # --- run_fencer -----------------------------------------------------------

    def test_run_fencer_returns_true_when_timestamps_match(self):
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        self.assertTrue(p.run_fencer('host-1', 1000.0))

    def test_run_fencer_returns_false_when_newer_fencer_exists(self):
        """A newer setup_fencer (higher ts) signals the old thread to stop."""
        p = self._make_plugin()
        p.setup_fencer('host-1', 2000.0)   # newer fencer registered
        self.assertFalse(p.run_fencer('host-1', 1000.0))  # old thread check

    def test_run_fencer_raises_keyerror_when_host_not_registered(self):
        """Characterises current behaviour: no guard on missing host_uuid.

        NOTE: this is a latent defect. run_fencer should return False instead
        of raising KeyError. A future fix must update this assertion.
        """
        p = self._make_plugin()
        with self.assertRaises(KeyError):
            p.run_fencer('unknown-host', 1000.0)

    def test_run_fencer_raises_keyerror_after_cancel(self):
        """After cancel_fencer, the next run_fencer call raises KeyError.

        NOTE: latent race condition — a fencer thread can call run_fencer once
        after cancel and receive an unhandled exception. Document for fix.
        """
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        p.cancel_fencer('host-1')
        with self.assertRaises(KeyError):
            p.run_fencer('host-1', 1000.0)

    # --- cancel_fencer --------------------------------------------------------

    def test_cancel_fencer_removes_entry(self):
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        p.cancel_fencer('host-1')
        self.assertNotIn('host-1', p.run_fencer_timestamp)

    def test_cancel_fencer_noop_for_unknown_host(self):
        """pop(key, None) silently ignores missing keys — no exception."""
        p = self._make_plugin()
        p.cancel_fencer('unknown-host')  # must not raise

    # --- thread safety --------------------------------------------------------

    def test_run_fencer_is_thread_safe_under_concurrent_access(self):
        """Multiple threads calling run_fencer concurrently must not crash."""
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        results = []
        errors = []

        def check():
            try:
                results.append(p.run_fencer('host-1', 1000.0))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual([], errors, "Unexpected exceptions: %s" % errors)
        self.assertTrue(all(results))

    def test_multiple_hosts_are_tracked_independently(self):
        p = self._make_plugin()
        p.setup_fencer('host-1', 1000.0)
        p.setup_fencer('host-2', 2000.0)
        self.assertTrue(p.run_fencer('host-1', 1000.0))
        self.assertTrue(p.run_fencer('host-2', 2000.0))
        p.cancel_fencer('host-1')
        self.assertNotIn('host-1', p.run_fencer_timestamp)
        self.assertIn('host-2', p.run_fencer_timestamp)


if __name__ == '__main__':
    unittest.main()
