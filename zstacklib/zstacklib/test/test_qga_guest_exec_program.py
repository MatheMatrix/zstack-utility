# -*- coding: utf-8 -*-
"""Unit tests for VmQga.guest_exec_program helpers.

Compatible with Python 2 and Python 3 unittest discovery.
"""
from __future__ import absolute_import

import os
import sys
import types
import unittest
import warnings

try:
    from unittest import mock
except ImportError:  # pragma: no cover
    import mock


qga_mod = None
VmQga = None
_modules_before = None


def _ensure_module(name):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    parent_name, _, child = name.rpartition('.')
    if parent_name:
        parent = _ensure_module(parent_name)
        setattr(parent, child, mod)
    return mod


def _load_module_from_path(name, path):
    """Load a module file on both Python 2 and Python 3."""
    try:
        import importlib.util as importlib_util
    except ImportError:  # Python 2
        import imp
        mod = imp.load_source(name, path)
        sys.modules[name] = mod
        return mod

    spec = importlib_util.spec_from_file_location(name, path)
    mod = importlib_util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _restore_sys_modules(before):
    """Undo sys.modules mutations so discovery order cannot leak stubs."""
    before_keys = set(before)
    after_keys = set(sys.modules)
    for key in after_keys - before_keys:
        sys.modules.pop(key, None)
    for key in before_keys:
        prev = before[key]
        if sys.modules.get(key) is not prev:
            sys.modules[key] = prev


def _load_qga_module():
    sys.modules['libvirt'] = mock.MagicMock()
    sys.modules['libvirt_qemu'] = mock.MagicMock()

    # qga.py uses bare `import log`
    log_mod = _ensure_module('log')
    if not hasattr(log_mod, 'get_logger'):
        log_mod.get_logger = mock.Mock(return_value=mock.Mock())

    here = os.path.dirname(os.path.abspath(__file__))
    qga_path = os.path.abspath(os.path.join(here, '..', 'utils', 'qga.py'))
    # Flat module name avoids Parent module RuntimeWarning and package pollution.
    return _load_module_from_path('qga_under_test', qga_path)


def setUpModule():
    global qga_mod, VmQga, _modules_before
    _modules_before = sys.modules.copy()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        qga_mod = _load_qga_module()
        parent_warns = [
            w for w in caught
            if issubclass(w.category, RuntimeWarning)
            and 'Parent module' in str(w.message)
        ]
        if parent_warns:
            raise AssertionError(
                'unexpected Parent module RuntimeWarning during qga load: %s'
                % parent_warns[0].message
            )
    VmQga = qga_mod.VmQga


def tearDownModule():
    global qga_mod, VmQga, _modules_before
    if _modules_before is not None:
        _restore_sys_modules(_modules_before)
        _modules_before = None
    qga_mod = None
    VmQga = None


def _make_qga():
    obj = VmQga.__new__(VmQga)
    obj.vm_uuid = 'test-vm'
    obj.os = 'mswindows'
    return obj


class TestGuestExecZsTools(unittest.TestCase):
    def setUp(self):
        self.qga = _make_qga()
        qga_mod.log.mask_sensitive_field = lambda config_obj, config: config

    def test_returns_stdout_and_stderr_with_newlines(self):
        self.qga.guest_exec = mock.Mock(return_value={'pid': 8})
        self.qga.guest_exec_status_with_timeout = mock.Mock(return_value={
            'exited': True, 'exitcode': 2,
            'out-data': b'line1\r\nline2', 'err-data': b'error1\r\nerror2'
        })
        with mock.patch.object(qga_mod.time, 'sleep', mock.Mock()):
            code, data = self.qga.guest_exec_zs_tools('net', '{}', wait=0, retry=1)
        self.assertEqual(code, 2)
        self.assertEqual(data, 'stdout:\nline1\nline2\nstderr:\nerror1\nerror2')

    def test_not_exited_returns_status_and_log_tail(self):
        self.qga.guest_exec = mock.Mock(return_value={'pid': 9})
        self.qga.guest_exec_status_with_timeout = mock.Mock(return_value={'exited': False})
        self.qga._try_read_zs_tools_log_tail = mock.Mock(return_value='last error')
        with mock.patch.object(qga_mod.time, 'sleep', mock.Mock()):
            code, data = self.qga.guest_exec_zs_tools('net', '{}', wait=0, retry=2)
        self.assertEqual(code, 1)
        self.assertIn('zs-tools pid 9 not exited after 2 retries', data)
        self.assertIn('status={"exited": false}', data)
        self.assertIn('zs-tools.log tail:\nlast error', data)

    def test_log_tail_reads_last_4096_bytes_and_closes(self):
        self.qga.guest_file_open = mock.Mock(return_value=11)
        self.qga.guest_file_close = mock.Mock()
        self.qga.call_qga_command = mock.Mock(side_effect=[
            {'position': 5000}, {'position': 904},
            {'buf-b64': b'tail\r\nline', 'count': 10, 'eof': True}
        ])
        data = self.qga._try_read_zs_tools_log_tail()
        self.assertEqual(data, 'tail\nline')
        self.assertEqual(self.qga.call_qga_command.call_args_list[1], mock.call(
            'guest-file-seek', args={'handle': 11, 'offset': 904, 'whence': 0}))
        self.qga.guest_file_close.assert_called_once_with(11)

if __name__ == '__main__':
    unittest.main()
