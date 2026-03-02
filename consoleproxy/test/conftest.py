# -*- coding: utf-8 -*-
"""
conftest.py for consoleproxy tests.
Mocks all zstacklib dependencies so tests run under Python 3 without
a full KVM environment.
"""
import sys
import os
import types
from unittest.mock import MagicMock

# ---- Add package roots to sys.path ------------------------------------
_root = os.path.join(os.path.dirname(__file__), '..', '..')
_cp_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(_root))
sys.path.insert(0, os.path.abspath(_cp_root))

# ---- log --------------------------------------------------------------
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: MagicMock()
_mock_log.get_logfile_path = lambda: '/dev/null'
sys.modules['log'] = _mock_log
sys.modules['zstacklib.utils.log'] = _mock_log

# ---- bash -------------------------------------------------------------
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log
_mock_bash.bash_roe = MagicMock(return_value=(0, '', ''))
_mock_bash.bash_ro = MagicMock(return_value=(0, ''))
_mock_bash.bash_r = MagicMock(return_value=0)
_mock_bash.in_bash = lambda f: f  # no-op decorator
sys.modules['bash'] = _mock_bash
sys.modules['zstacklib.utils.bash'] = _mock_bash

# ---- http -------------------------------------------------------------
_mock_http = MagicMock()
_mock_http.HttpServer = MagicMock(return_value=MagicMock())
_mock_http.REQUEST_BODY = 'body'
sys.modules['zstacklib.utils.http'] = _mock_http

# ---- remaining zstacklib mocks ----------------------------------------
for mod in [
    'zstacklib.utils.plugin',
    'zstacklib.utils.shell',
    'zstacklib.utils.daemon',
    'zstacklib.utils.linux',
    'zstacklib.utils.filedb',
    'zstacklib.utils.lock',
    'zstacklib.utils.jsonobject',
]:
    sys.modules[mod] = MagicMock()

# lock.lock must be a no-op decorator
sys.modules['zstacklib.utils.lock'].lock = lambda name: (lambda f: f)

# filedb.FileDB returns a mock instance
sys.modules['zstacklib.utils.filedb'].FileDB = MagicMock

# jsonobject helpers used in agent
import json
_jmod = sys.modules['zstacklib.utils.jsonobject']
_jmod.loads = lambda s: json.loads(s) if isinstance(s, str) else s
_jmod.dumps = lambda obj, **kw: json.dumps(
    obj if isinstance(obj, dict) else obj.__dict__, default=str)
