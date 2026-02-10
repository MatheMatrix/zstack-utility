# -*- coding: utf-8 -*-
"""
Root conftest.py - Pre-import mocks for Python 3 test compatibility.

zstacklib targets Python 2.7 in production. Many utility modules use Python 2
syntax (octal 0755, tab/space mixing, etc.). This conftest patches them before
any zstacklib import so pytest can collect and run GPU unit tests under Python 3.

Only GPU-related tests (pure parsing / data-flow logic) are covered here.
Tests that need real shell execution should run in the production Python 2 env.
"""
import sys
import types
from unittest.mock import MagicMock

# ---- Step 1: Create mock log module (used by many modules) ----------------
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: MagicMock()
sys.modules['log'] = _mock_log  # bare `import log` in thread.py etc.
sys.modules['zstacklib.utils.log'] = _mock_log

# ---- Step 2: Create mock bash module (gpu.py does `from bash import *`) ----
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log  # `from bash import *` brings `log` into scope
_mock_bash.bash_roe = lambda *a, **kw: (0, '', '')
_mock_bash.bash_ro = lambda *a, **kw: (0, '')
_mock_bash.bash_r = lambda *a, **kw: 0
sys.modules['zstacklib.utils.bash'] = _mock_bash

# ---- Step 3: Mock remaining Py2-only / unavailable modules -----------------
_SIMPLE_MOCKS = [
    'libvirt',
    'zstacklib.utils.shell',
    'zstacklib.utils.lock',
    'zstacklib.utils.linux',
    'zstacklib.utils.daemon',
    'zstacklib.utils.filedb',
    'zstacklib.utils.salt',
    'zstacklib.utils.ovs',
    'zstacklib.utils.qemu',
    'zstacklib.utils.sizeunit',
    'zstacklib.utils.thread',
    'zstacklib.utils.qga',
]
for _mod_name in _SIMPLE_MOCKS:
    sys.modules[_mod_name] = MagicMock()
