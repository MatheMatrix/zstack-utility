# -*- coding: utf-8 -*-
"""
Root conftest.py - Auto-discover subpackages + Py2 compatibility mocks.

This module:
1. Auto-discovers and adds all subpackage roots to sys.path
2. Provides Py2 compatibility mocks for legacy modules
3. Registers pytest plugins
4. Provides shared fixtures for the test hierarchy

KEY DESIGN: Mock system-level modules (libvirt, shell, linux) but let
application-level code (jsonobject, kvmagent, plugins) import for REAL.
This enables handler code to execute locally for coverage measurement.
"""
import builtins
import sys
import types
import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

# ============================================================================
# STEP 1: Auto-discover subpackages and add to sys.path (MUST be first!)
# ============================================================================
_repo_root = Path(__file__).resolve().parent.parent
for _child in sorted(_repo_root.iterdir()):
    if _child.is_dir() and ((_child / 'setup.py').exists() or (_child / 'setup.cfg').exists()):
        _child_str = str(_child)
        if _child_str not in sys.path:
            sys.path.insert(0, _child_str)

# ============================================================================
# STEP 2: Python 2/3 compatibility shims (before any subpackage imports)
# ============================================================================
# These shims allow Python 2 code to be parsed and executed by Python 3.

# builtins.reload — used by kvmagent.py `reload(sys)`
if not hasattr(builtins, 'reload'):
    builtins.reload = lambda m: m

# builtins.long — used by shared_block_plugin.py `long(...)` 
if not hasattr(builtins, 'long'):
    builtins.long = int

# builtins.unicode — used by some py2 code
if not hasattr(builtins, 'unicode'):
    builtins.unicode = str

# sys.setdefaultencoding — kvmagent.py calls this
if not hasattr(sys, 'setdefaultencoding'):
    sys.setdefaultencoding = lambda *a: None

# types module — Py2 type aliases used by jsonobject.py and others
_PY2_TYPE_SHIMS = {
    'DictType': dict, 'DictionaryType': dict, 'ListType': list,
    'StringType': str, 'UnicodeType': str, 'IntType': int,
    'LongType': int, 'FloatType': float, 'BooleanType': bool,
    'NoneType': type(None), 'ComplexType': complex, 'TupleType': tuple,
    'FileType': type(None),  # Py2 file type, no equivalent
    'XRangeType': range, 'DictProxyType': type(None),
    'NotImplementedType': type(NotImplemented),
    'UnboundMethodType': types.FunctionType,
}
for _name, _type in _PY2_TYPE_SHIMS.items():
    if not hasattr(types, _name):
        setattr(types, _name, _type)

# simplejson — redirect to stdlib json (must be before jsonobject import)
if 'simplejson' not in sys.modules:
    _simplejson = types.ModuleType('simplejson')
    _simplejson.dumps = json.dumps
    _simplejson.loads = json.loads
    _simplejson.JSONDecodeError = json.JSONDecodeError
    sys.modules['simplejson'] = _simplejson

# commands module — Py2 only, used by kvmagent.py
if 'commands' not in sys.modules:
    _mock_commands = types.ModuleType('commands')
    _mock_commands.getoutput = lambda cmd: ''
    sys.modules['commands'] = _mock_commands

# imp module — removed in Python 3.12+, needed by zstacklib.utils.plugin
if 'imp' not in sys.modules:
    sys.modules['imp'] = MagicMock()

# pipes module — removed in Python 3.13, replaced by shlex
if 'pipes' not in sys.modules:
    import shlex as _shlex
    _mock_pipes = types.ModuleType('pipes')
    _mock_pipes.quote = _shlex.quote
    sys.modules['pipes'] = _mock_pipes

# urlparse — Py2 module, Py3 uses urllib.parse
if 'urlparse' not in sys.modules:
    import urllib.parse as _urlparse
    sys.modules['urlparse'] = _urlparse

# cStringIO — Py2 module
if 'cStringIO' not in sys.modules:
    import io as _io
    _mock_cstringio = types.ModuleType('cStringIO')
    _mock_cstringio.StringIO = _io.StringIO
    sys.modules['cStringIO'] = _mock_cstringio

# urllib2 — Py2 module
if 'urllib2' not in sys.modules:
    sys.modules['urllib2'] = MagicMock()

# syslog — not available on macOS Python 3.13
if 'syslog' not in sys.modules:
    _mock_syslog = types.ModuleType('syslog')
    _mock_syslog.syslog = lambda *a: None
    sys.modules['syslog'] = _mock_syslog

# distutils.version — removed in Python 3.12+
if 'distutils' not in sys.modules:
    _mock_distutils = types.ModuleType('distutils')
    _mock_distutils.__path__ = []
    sys.modules['distutils'] = _mock_distutils
if 'distutils.version' not in sys.modules:
    _mock_dv = types.ModuleType('distutils.version')
    class _LooseVersion:
        def __init__(self, v='0'): self.version = str(v)
        def __lt__(self, o): return str(self.version) < str(getattr(o, 'version', o))
        def __le__(self, o): return str(self.version) <= str(getattr(o, 'version', o))
        def __gt__(self, o): return str(self.version) > str(getattr(o, 'version', o))
        def __ge__(self, o): return str(self.version) >= str(getattr(o, 'version', o))
        def __eq__(self, o): return str(self.version) == str(getattr(o, 'version', o))
        def __repr__(self): return 'LooseVersion(%r)' % self.version
    _mock_dv.LooseVersion = _LooseVersion
    sys.modules['distutils.version'] = _mock_dv

# Third-party libraries (not available in test venv)
_THIRD_PARTY_MOCKS = [
    'netaddr', 'jinja2', 'psutil', 'pyudev', 'rados', 'rbd',
    'prometheus_client', 'prometheus_client.core',
]
for _mod_name in _THIRD_PARTY_MOCKS:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


# platform.machine() returns 'arm64' on macOS ARM but kvmagent expects Linux arch names
import platform as _platform
if _platform.machine() not in ('x86_64', 'aarch64', 'mips64el', 'loongarch64'):
    _platform.machine = lambda: 'x86_64'

# platform.dist() removed in Python 3.8+
if not hasattr(_platform, 'dist'):
    _platform.dist = lambda: ('', '', '')
# ============================================================================
# STEP 3: Mock log module FIRST (many modules import it at module level)
# ============================================================================
_mock_logger = MagicMock()

_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: _mock_logger
_mock_log.get_logfile_path = lambda: '/dev/null'
_mock_log.sensitive_fields = lambda *fields: (lambda cls: cls)  # decorator passthrough
sys.modules['log'] = _mock_log
sys.modules['zstacklib.utils.log'] = _mock_log

# ============================================================================
# STEP 4: Mock bash module (gpu.py does `from bash import *`)
# ============================================================================
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log
_mock_bash.bash_roe = lambda *a, **kw: (0, '', '')
_mock_bash.bash_ro = lambda *a, **kw: (0, '')
_mock_bash.bash_r = lambda *a, **kw: 0
_mock_bash.bash_o = lambda *a, **kw: ''
_mock_bash.bash_errorout = lambda *a, **kw: ''
_mock_bash.bash = lambda *a, **kw: 0
_mock_bash.in_bash = lambda f: f  # decorator passthrough
_mock_bash.__all__ = ['log', 'bash_roe', 'bash_ro', 'bash_r', 'bash_o',
                       'bash_errorout', 'bash', 'in_bash']
sys.modules['zstacklib.utils.bash'] = _mock_bash

# ============================================================================
# STEP 5: Ensure zstacklib package hierarchy exists in sys.modules
# ============================================================================
# Set real paths so Python can find real submodules (like jsonobject)
_zstacklib_root = str(_repo_root / 'zstacklib')
_pkg_paths = {
    'zstacklib': [str(_repo_root / 'zstacklib' / 'zstacklib')],
    'zstacklib.utils': [str(_repo_root / 'zstacklib' / 'zstacklib' / 'utils')],
    'zstacklib.gpu': [],  # fully mocked
}
for _pkg, _path in _pkg_paths.items():
    if _pkg not in sys.modules:
        _p = types.ModuleType(_pkg)
        _p.__path__ = _path
        _p.__package__ = _pkg
        sys.modules[_pkg] = _p
    elif hasattr(sys.modules[_pkg], '__path__') and not sys.modules[_pkg].__path__:
        sys.modules[_pkg].__path__ = _path

# ============================================================================
# STEP 6: Mock system-level modules (keep as functional MagicMock)
# These are OS/hardware-dependent and cannot run locally on macOS.
# ============================================================================

# --- Functional mock for linux module ---
_mock_linux = MagicMock()
_mock_linux.HOST_ARCH = 'x86_64'
_mock_linux.DEB_BASED_OS = ['ubuntu', 'debian']
_mock_linux.DIST_WITH_RPM_DEB = ['centos', 'redhat', 'ubuntu', 'debian']
_mock_linux.get_cpu_num.return_value = 4
_mock_linux.get_total_memory.return_value = 8 * 1024 * 1024 * 1024  # 8GB
_mock_linux.get_used_memory.return_value = 2 * 1024 * 1024 * 1024  # 2GB
_mock_linux.get_cpu_speed.return_value = 2400
_mock_linux.get_cpu_model.return_value = 'Intel(R) Xeon(R) CPU'
_mock_linux.get_host_physicl_cpu_num.return_value = 1
_mock_linux.get_cpu_core_num.return_value = 4
_mock_linux.mkdir = MagicMock()
_mock_linux.recover_fake_dead = MagicMock()
_mock_linux.rm_file_checked = MagicMock()
_mock_linux.rm_file_force = MagicMock()
_mock_linux.rmdir_if_empty = MagicMock()
_mock_linux.write_file = MagicMock()
sys.modules['zstacklib.utils.linux'] = _mock_linux

# --- Functional mock for http module ---
_mock_http = types.ModuleType('zstacklib.utils.http')
_mock_http.build_url = lambda parts: 'http://%s:%s%s' % (parts[1], parts[2], parts[3])
_mock_http.HttpServer = MagicMock()
_mock_http.REQUEST_BODY = 'body'
_mock_http.REQUEST_HEADER = 'header'
_mock_http.path_msg = lambda path, msg='': '[%s] %s' % (path, msg)

class _MockUriBuilder:
    def __init__(self, base=''):
        self._base = base
        self._paths = []
    def add_path(self, p):
        self._paths.append(p)
        return self
    def build(self):
        return self._base + '/' + '/'.join(self._paths)

_mock_http.UriBuilder = _MockUriBuilder
sys.modules['zstacklib.utils.http'] = _mock_http

# --- Simple MagicMock modules (system-level, no functional behavior needed) ---
_SIMPLE_MOCKS = [
    'libvirt',
    'zstacklib.utils.shell',
    'zstacklib.utils.lock',
    'zstacklib.utils.daemon',
    'zstacklib.utils.filedb',
    'zstacklib.utils.salt',
    'zstacklib.utils.ovs',
    'zstacklib.utils.qemu',
    'zstacklib.utils.sizeunit',
    'zstacklib.utils.thread',
    'zstacklib.utils.qga',
    'zstacklib.utils.iptables',
    'zstacklib.utils.ebtables',
    'zstacklib.utils.iproute',
    'zstacklib.utils.plugin',
    'zstacklib.utils.xmlobject',
    'zstacklib.utils.misc',
    'zstacklib.utils.ovn',
    'zstacklib.utils.lvm',
    'zstacklib.utils.ceph',
    'zstacklib.utils.pci',
    'zstacklib.utils.ip',
    'zstacklib.utils.libvirt_singleton',
    'zstacklib.utils.report',
    'zstacklib.gpu',
    'zstacklib.gpu.base',
    # --- vm_plugin dependencies ---
    'zstacklib.utils.iscsi',
    'zstacklib.utils.ft',
    'zstacklib.utils.uuidhelper',
    'zstacklib.utils.xmlhook',
    'zstacklib.utils.qemu_img',
    'zstacklib.utils.qmp',
    'zstacklib.utils.vm_operator',
    'zstacklib.utils.image',
    'zstacklib.utils.drbd',
    'zstacklib.utils.qemu_nbd',
    'zstacklib.utils.vm_plugin_queue_singleton',
    # --- kvmagent plugin submodules ---
    'kvmagent.plugins.baremetal_v2_gateway_agent',
    'kvmagent.plugins.bmv2_gateway_agent',
    'kvmagent.plugins.bmv2_gateway_agent.utils',
    'kvmagent.plugins.imagestore',
]
for _mod_name in _SIMPLE_MOCKS:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

# sizeunit needs get_size to be callable
sys.modules['zstacklib.utils.sizeunit'].get_size = lambda s: int(s) if isinstance(s, (int, float)) else 0

# plugin module needs Plugin base class
_mock_plugin = sys.modules['zstacklib.utils.plugin']
class _PluginBase:
    def __init__(self):
        pass
    def start(self):
        pass
    def stop(self):
        pass
    def configure(self, config):
        pass
_mock_plugin.Plugin = _PluginBase
_mock_plugin.PluginRegistry = MagicMock()

# thread module needs timer to be callable
_mock_thread = sys.modules['zstacklib.utils.thread']
_mock_thread.timer = MagicMock()
_mock_thread.AsyncTimer = MagicMock()

# gpu.base needs VendorEnum
_mock_gpu_base = sys.modules['zstacklib.gpu.base']
_mock_gpu_base.VendorEnum = type('VendorEnum', (), {'NVIDIA': 'nvidia', 'AMD': 'amd', 'INTEL': 'intel'})

# qemu needs get_path
_mock_qemu = sys.modules['zstacklib.utils.qemu']
_mock_qemu.get_path.return_value = '/usr/bin/qemu-system-x86_64'

# qga and report use `from ... import *` in vm_plugin — they must export `log`
_mock_qga = sys.modules['zstacklib.utils.qga']
_mock_qga.log = _mock_log
_mock_qga.__all__ = ['log']

_mock_report = sys.modules['zstacklib.utils.report']
_mock_report.log = _mock_log
_mock_report.__all__ = ['log', 'Report']
_mock_report.Report = MagicMock()

# plugin module needs TaskManager and TaskResult for vm_plugin
_mock_plugin.TaskManager = MagicMock()
_mock_plugin.TaskResult = MagicMock()

# libvirt_singleton needs LibvirtEventManager classes
_mock_ls = sys.modules['zstacklib.utils.libvirt_singleton']
_mock_ls.LibvirtEventManager = MagicMock()
_mock_ls.LibvirtEventManagerSingleton = MagicMock()
_mock_ls.LibvirtSingleton = MagicMock()

# vm_plugin_queue_singleton needs VmPluginQueueSingleton class
sys.modules['zstacklib.utils.vm_plugin_queue_singleton'].VmPluginQueueSingleton = MagicMock()

# qmp needs get_block_node_name_and_file
sys.modules['zstacklib.utils.qmp'].get_block_node_name_and_file = MagicMock(return_value=('', ''))

# ovn needs delVnicFromOvsByVmUuidIfExist
sys.modules['zstacklib.utils.ovn'].delVnicFromOvsByVmUuidIfExist = MagicMock()

# linux needs is_virtual_machine
sys.modules['zstacklib.utils.linux'].is_virtual_machine = MagicMock(return_value=False)

# ip module needs get_nic_supported_max_speed and get_nic_driver_type
sys.modules['zstacklib.utils.ip'].get_nic_supported_max_speed = MagicMock(return_value=1000)
sys.modules['zstacklib.utils.ip'].get_nic_driver_type = MagicMock(return_value='virtio')

# imagestore module needs ImageStoreClient
_mock_imagestore = sys.modules.get('kvmagent.plugins.imagestore')
if _mock_imagestore is not None:
    _mock_imagestore.ImageStoreClient = MagicMock()

# libvirt_singleton conn must return valid XML for getCapabilities()
# (vm_plugin.LibvirtAutoReconnect calls conn.getCapabilities() at class definition time)
_MINIMAL_LIBVIRT_CAPS = '''<capabilities>
  <host><uuid>00000000-0000-0000-0000-000000000000</uuid>
    <cpu><arch>x86_64</arch></cpu><cells num="1"><cell id="0"><memory unit="KiB">8388608</memory></cell></cells>
  </host>
  <guest><os_type>hvm</os_type><arch name="x86_64"><machine>pc</machine></arch></guest>
</capabilities>'''
_mock_ls.LibvirtSingleton.return_value.conn.getCapabilities.return_value = _MINIMAL_LIBVIRT_CAPS
_mock_ls.LibvirtSingleton.return_value.libvirt_event_callbacks = {}

# ============================================================================
# STEP 7: NOW import the real jsonobject (after simplejson shim is in place)
# ============================================================================
# Remove the MagicMock if it was previously set, then let real import happen
if 'zstacklib.utils.jsonobject' in sys.modules:
    del sys.modules['zstacklib.utils.jsonobject']

from zstacklib.utils import jsonobject as _real_jsonobject
sys.modules['zstacklib.utils.jsonobject'] = _real_jsonobject

# Also make sure the parent package knows about it
_utils_pkg = sys.modules.get('zstacklib.utils')
if _utils_pkg is not None:
    _utils_pkg.jsonobject = _real_jsonobject

# ============================================================================
# STEP 8: Mock inventory module (used by apibinding.api)
# ============================================================================
_mock_inventory = types.ModuleType('inventory')
_mock_inventory.Session = type('Session', (), {'uuid': None})
sys.modules['inventory'] = _mock_inventory

# ============================================================================
# STEP 9: pytest configuration and plugins
# ============================================================================

import os
import pytest

# Register pytest plugins
pytest_plugins = [
    'tests.plugins.ssh_plugin',
    'tests.plugins.vm_deploy_plugin',
    'tests.plugins.markers',
]


@pytest.fixture(autouse=True, scope='session')
def mock_zstacklib_imports():
    """
    Py2 compatibility mock fixture (session scope).
    
    Auto-used for all tests to ensure mocked modules remain active
    throughout the test session. The actual mocking happens at module
    load time (above), this fixture just verifies and maintains state.
    """
    # Verify mock modules are in sys.modules
    assert 'zstacklib.utils.log' in sys.modules, 'log mock not installed'
    assert 'zstacklib.utils.bash' in sys.modules, 'bash mock not installed'
    assert 'zstacklib.utils.jsonobject' in sys.modules, 'jsonobject not installed'
    # Verify jsonobject is REAL (not MagicMock)
    jo = sys.modules['zstacklib.utils.jsonobject']
    assert hasattr(jo, 'loads') and hasattr(jo, 'dumps'), 'jsonobject must be real module'
    yield
    # Mocks stay active for entire session

# ============================================================================
# STEP 10: Import shared fixtures from tests.fixtures.common
# ============================================================================
from tests.fixtures.common import (
    project_root,
    tmp_test_dir,
    sample_vm_xml,
    fake_zstack_config,
    isolated_env,
)

# ============================================================================
# STEP 11: Pytest hooks for CLI validation and mode display
# ============================================================================

def pytest_configure(config):
    """
    Validate mutually exclusive CLI options at pytest startup.
    """
    ssh_host = config.getoption("--ssh-host", default=None)
    vm_deploy = config.getoption("--vm-deploy", default=False)
    target = config.getoption("--target", default=None)
    
    if ssh_host and vm_deploy:
        raise pytest.UsageError(
            "--ssh-host and --vm-deploy are mutually exclusive"
            "(cannot use both at the same time)"
        )
    
    if vm_deploy and not target:
        raise pytest.UsageError(
            "--vm-deploy requires --target to be specified (IP[:port] format)"
        )


def pytest_report_header(config):
    """
    Display current running mode at test output header.
    """
    ssh_host = config.getoption("--ssh-host", default=None)
    vm_deploy = config.getoption("--vm-deploy", default=False)
    target = config.getoption("--target", default=None)
    
    if vm_deploy and target:
        return f"Mode: VM Deploy → {target}"
    elif ssh_host:
        return f"Mode: SSH → {ssh_host}"
    else:
        return "Mode: local (unit tests)"
