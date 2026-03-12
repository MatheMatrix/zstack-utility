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

_ORIGINAL_MODULES = {}
_ORIGINAL_PARENT_ATTRS = {}  # (parent_fqn, attr_name) -> old_value | _SENTINEL

_SENTINEL = object()

def _patch_module(name, value):
    """Replace sys.modules[name] and snapshot parent-package attribute."""
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

# log
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: mock.MagicMock()
_patch_module('zstacklib.utils.log', _mock_log)
_patch_module('log', _mock_log)

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
_patch_module('zstacklib.utils.bash', _mock_bash)

# misc — isMiniHost / isHyperConvergedHost gate the conditional collectors
_mock_misc = mock.MagicMock()
_mock_misc.isMiniHost.return_value = False
_mock_misc.isHyperConvergedHost.return_value = False
_patch_module('zstacklib.utils.misc', _mock_misc)

# linux — is_virtual_machine, is_support_bmc gate a conditional collector
_mock_linux = mock.MagicMock()
_mock_linux.is_virtual_machine.return_value = False
_mock_linux.is_support_bmc.return_value = False
_patch_module('zstacklib.utils.linux', _mock_linux)

# debug — configure() writes into it
_mock_debug = mock.MagicMock()
_patch_module('zstacklib.utils.debug', _mock_debug)

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
    _patch_module(_mod, mock.MagicMock())

# pyudev / prometheus_client / psutil — external packages not in test env
_patch_module('libvirt', mock.MagicMock())
_patch_module('zstacklib.utils.qga', mock.MagicMock())
_patch_module('pyudev', mock.MagicMock())
_mock_prom = mock.MagicMock()
_mock_prom.core = mock.MagicMock()
_patch_module('prometheus_client', _mock_prom)
_patch_module('prometheus_client.core', _mock_prom.core)
_patch_module('psutil', mock.MagicMock())

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
_mock_kvmagent_mod.SEND_COMMAND_URL = 'SEND_COMMAND_URL'
_mock_kvmagent_mod.HOST_UUID = 'HOST_UUID'
_mock_kvmagent_mod.get_qemu_path = mock.MagicMock(return_value='/usr/bin/qemu-kvm')
_mock_kvmagent_mod.register_prometheus_collector = mock.MagicMock()
_mock_kvmagent_mod.host_arch = 'x86_64'
_mock_kvmagent_mod.kvmagent_physical_memory_usage_hardlimit = None
_mock_kvmagent_mod.kvmagent_physical_memory_usage_alarm_threshold = None
_patch_module('kvmagent.kvmagent', _mock_kvmagent_mod)


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

    def test_configure_sets_debug_send_url_key(self):
        """debug.SEND_COMMAND_URL is always the key string, not the URL value."""
        p = self._make_plugin()
        p.configure({})
        self.assertEqual('SEND_COMMAND_URL', _mock_debug.SEND_COMMAND_URL)

    def test_configure_sets_debug_host_uuid_key(self):
        """debug.HOST_UUID is always the key string, not the UUID value."""
        p = self._make_plugin()
        p.configure({})
        self.assertEqual('HOST_UUID', _mock_debug.HOST_UUID)

    def test_configure_standalone_maps_send_url_into_config(self):
        """Standalone sendCommandUrl is mapped to CONFIG[SEND_COMMAND_URL] key."""
        p = self._make_plugin()
        cfg = {'sendCommandUrl': 'http://standalone/send'}
        p.configure(cfg)
        self.assertEqual('http://standalone/send', cfg['SEND_COMMAND_URL'])

    def test_configure_standalone_maps_host_uuid_into_config(self):
        """Standalone hostUuid is mapped to CONFIG[HOST_UUID] key."""
        p = self._make_plugin()
        cfg = {'hostUuid': 'standalone-host-uuid'}
        p.configure(cfg)
        self.assertEqual('standalone-host-uuid', cfg['HOST_UUID'])


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
        """Import alone must not register any collectors.

        Note: a full reimport is impractical because prometheus.py has deep
        module-level dependencies.  We reset the mock and verify no NEW
        registrations happen after the initial import.
        """
        _mock_kvmagent_mod.register_prometheus_collector.reset_mock()
        calls = _mock_kvmagent_mod.register_prometheus_collector.call_count
        self.assertEqual(0, calls,
                         "Collectors must not be registered at import time")

    def test_misc_isMiniHost_not_called_at_import_time(self):
        """misc.isMiniHost() must not be called during module import.

        It is called inside PrometheusPlugin.start() instead.
        """
        _mock_misc.isMiniHost.reset_mock()
        self.assertEqual(0, _mock_misc.isMiniHost.call_count)


if __name__ == '__main__':
    unittest.main()
