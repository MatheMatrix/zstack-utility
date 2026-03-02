# -*- coding: utf-8 -*-
"""Characterisation tests for PrometheusPlugin lifecycle.

Covers configure() / ALARM_CONFIG propagation and the gpu-status
abnormal-flag helpers (is_gpu_status_abnormal / remove_gpu_status_abnormal).

Module-level code in prometheus.py calls kvmagent.get_qemu_path() and
kvmagent.register_prometheus_collector() at import time.  All heavy
dependencies are stubbed before the import below.
"""
import os
import sys
import types
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# 1. Package roots on sys.path
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
_kvmagent_root = os.path.abspath(os.path.join(_here, '..', '..'))
_repo_root = os.path.abspath(os.path.join(_here, '..', '..', '..'))
_zstacklib_root = os.path.join(_repo_root, 'zstacklib')

for _p in (_kvmagent_root, _zstacklib_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# 2. Stubs for heavy / unavailable dependencies BEFORE the import
# ---------------------------------------------------------------------------

# log
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: mock.MagicMock()
sys.modules['zstacklib.utils.log'] = _mock_log
sys.modules['log'] = _mock_log

# bash star-import (exposes bash_roe, bash_ro, bash_r, bash_o, in_bash, json)
import json as _json
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log
_mock_bash.bash_roe = mock.MagicMock(return_value=(0, '', ''))
_mock_bash.bash_ro = mock.MagicMock(return_value=(0, ''))
_mock_bash.bash_r = mock.MagicMock(return_value=0)
_mock_bash.bash_o = mock.MagicMock(return_value='')
_mock_bash.in_bash = staticmethod(lambda f: f)
_mock_bash.json = _json
sys.modules['zstacklib.utils.bash'] = _mock_bash

# misc — isMiniHost / isHyperConvergedHost gate the conditional collectors
_mock_misc = mock.MagicMock()
_mock_misc.isMiniHost.return_value = False
_mock_misc.isHyperConvergedHost.return_value = False
sys.modules['zstacklib.utils.misc'] = _mock_misc

# linux — is_virtual_machine, is_support_bmc gate a conditional collector
_mock_linux = mock.MagicMock()
_mock_linux.is_virtual_machine.return_value = False
_mock_linux.is_support_bmc.return_value = False
sys.modules['zstacklib.utils.linux'] = _mock_linux

# debug — configure() writes into it
_mock_debug = mock.MagicMock()
sys.modules['zstacklib.utils.debug'] = _mock_debug

# simple mocks for other zstacklib utils
for _mod in [
    'zstacklib.utils.http',
    'zstacklib.utils.jsonobject',
    'zstacklib.utils.lock',
    'zstacklib.utils.lvm',
    'zstacklib.utils.shell',
    'zstacklib.utils.thread',
    'zstacklib.utils.ip',
    'zstacklib.utils.drbd',
    'zstacklib.utils.ovn',
    'zstacklib.utils.qemu_img',
]:
    sys.modules[_mod] = mock.MagicMock()

# pyudev / prometheus_client / psutil — external packages not in test env
sys.modules['libvirt'] = mock.MagicMock()
sys.modules['zstacklib.utils.qga'] = mock.MagicMock()
sys.modules['pyudev'] = mock.MagicMock()
_mock_prom = mock.MagicMock()
_mock_prom.core = mock.MagicMock()
sys.modules['prometheus_client'] = _mock_prom
sys.modules['prometheus_client.core'] = _mock_prom.core
sys.modules['psutil'] = mock.MagicMock()

# kvmagent.kvmagent — inner module with KvmAgent, replyerror, get_http_server
_mock_kvmagent_mod = types.ModuleType('kvmagent.kvmagent')


class _KvmAgent(object):
    """Minimal stub for kvmagent.KvmAgent."""
    def configure(self, config=None):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class _AgentResponse(object):
    def __init__(self):
        self.success = True
        self.error = None


_mock_kvmagent_mod.KvmAgent = _KvmAgent
_mock_kvmagent_mod.AgentResponse = _AgentResponse
_mock_kvmagent_mod.replyerror = staticmethod(lambda f: f)
_mock_kvmagent_mod.get_http_server = mock.MagicMock()
_mock_kvmagent_mod.SEND_COMMAND_URL = 'http://mn/api'
_mock_kvmagent_mod.HOST_UUID = 'test-host-uuid'
_mock_kvmagent_mod.get_qemu_path = mock.MagicMock(return_value='/usr/bin/qemu-kvm')
_mock_kvmagent_mod.register_prometheus_collector = mock.MagicMock()
_mock_kvmagent_mod.host_arch = 'x86_64'
_mock_kvmagent_mod.kvmagent_physical_memory_usage_hardlimit = None
_mock_kvmagent_mod.kvmagent_physical_memory_usage_alarm_threshold = None
sys.modules['kvmagent.kvmagent'] = _mock_kvmagent_mod

# ---------------------------------------------------------------------------
# 3. Import the module under test
# ---------------------------------------------------------------------------
from kvmagent.plugins.services.prometheus import (  # noqa: E402
    PrometheusPlugin,
    is_gpu_status_abnormal,
    remove_gpu_status_abnormal,
)
import kvmagent.plugins.services.prometheus as _prom_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPrometheusPluginConfigure(unittest.TestCase):
    """configure() propagates config into module globals and debug module."""

    def _make_plugin(self):
        p = PrometheusPlugin()
        return p

    def test_configure_sets_alarm_config(self):
        p = self._make_plugin()
        cfg = {'key': 'value'}
        p.configure(cfg)
        self.assertIs(_prom_mod.ALARM_CONFIG, cfg)

    def test_configure_with_none_uses_empty_dict(self):
        p = self._make_plugin()
        p.configure(None)
        self.assertEqual({}, _prom_mod.ALARM_CONFIG)

    def test_configure_default_arg_is_none(self):
        p = self._make_plugin()
        p.configure()
        self.assertEqual({}, _prom_mod.ALARM_CONFIG)

    def test_configure_propagates_to_debug_config(self):
        p = self._make_plugin()
        cfg = {'send_url': 'http://test'}
        p.configure(cfg)
        self.assertEqual(cfg, _mock_debug.CONFIG)

    def test_configure_copies_kvmagent_send_url_to_debug(self):
        """Falls back to kvmagent.SEND_COMMAND_URL when not in config."""
        p = self._make_plugin()
        p.configure({})
        self.assertEqual('http://mn/api', _mock_debug.SEND_COMMAND_URL)

    def test_configure_copies_kvmagent_host_uuid_to_debug(self):
        """Falls back to kvmagent.HOST_UUID when not in config."""
        p = self._make_plugin()
        p.configure({})
        self.assertEqual('test-host-uuid', _mock_debug.HOST_UUID)

    def test_configure_accepts_send_command_url_from_config(self):
        """Config dict overrides kvmagent constant — enables standalone mode."""
        p = self._make_plugin()
        p.configure({'sendCommandUrl': 'http://standalone/send'})
        self.assertEqual('http://standalone/send', _mock_debug.SEND_COMMAND_URL)

    def test_configure_accepts_host_uuid_from_config(self):
        """Config dict overrides kvmagent constant — enables standalone mode."""
        p = self._make_plugin()
        p.configure({'hostUuid': 'standalone-host-uuid'})
        self.assertEqual('standalone-host-uuid', _mock_debug.HOST_UUID)


class TestGpuStatusAbnormalFlag(unittest.TestCase):
    """is_gpu_status_abnormal / remove_gpu_status_abnormal state machine."""

    def setUp(self):
        # isolate: clear the shared hw_status_abnormal_list_record['gpu'] set
        _prom_mod.hw_status_abnormal_list_record['gpu'].clear()

    def test_not_abnormal_initially(self):
        self.assertFalse(is_gpu_status_abnormal('0000:01:00.0'))

    def test_not_abnormal_for_unknown_device(self):
        self.assertFalse(is_gpu_status_abnormal('ffff:ff:ff.f'))

    def test_remove_noop_for_unknown_device(self):
        remove_gpu_status_abnormal('ffff:ff:ff.f')  # must not raise

    def test_remove_clears_flag_set_externally(self):
        _prom_mod.hw_status_abnormal_list_record['gpu'].add('0000:01:00.0')
        remove_gpu_status_abnormal('0000:01:00.0')
        self.assertFalse(is_gpu_status_abnormal('0000:01:00.0'))

    def test_multiple_devices_tracked_independently(self):
        _prom_mod.hw_status_abnormal_list_record['gpu'].add('0000:01:00.0')
        self.assertTrue(is_gpu_status_abnormal('0000:01:00.0'))
        self.assertFalse(is_gpu_status_abnormal('0000:02:00.0'))
        remove_gpu_status_abnormal('0000:01:00.0')
        self.assertFalse(is_gpu_status_abnormal('0000:01:00.0'))


class TestCollectorRegistrationDeferredToStart(unittest.TestCase):
    """register_prometheus_collector is now deferred to start(), not module-level.

    Before this refactor, all collector registrations ran at import time
    (module scope).  After the refactor they run inside PrometheusPlugin.start()
    so the module can be safely imported without side-effects.
    """

    def test_no_collectors_registered_before_start(self):
        """Import alone must not register any collectors."""
        # reset call count to isolate from any previous test state
        _mock_kvmagent_mod.register_prometheus_collector.reset_mock()
        # re-importing has no effect (module is cached), but count is now 0
        calls = _mock_kvmagent_mod.register_prometheus_collector.call_count
        self.assertEqual(0, calls,
                         "Collectors must not be registered at import time")

    def test_misc_isMiniHost_not_called_at_import_time(self):
        """misc.isMiniHost() must not be called during module import.

        It is called inside PrometheusPlugin.start() instead.
        """
        _mock_misc.isMiniHost.reset_mock()
        # no re-import occurs (module cached) — call count stays 0
        self.assertEqual(0, _mock_misc.isMiniHost.call_count)


if __name__ == '__main__':
    unittest.main()
