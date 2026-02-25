# -*- coding: utf-8 -*-
"""
Root conftest.py - Auto-discover subpackages + Py2 compatibility mocks.

This module:
1. Auto-discovers and adds all subpackage roots to sys.path
2. Provides Py2 compatibility mocks for legacy modules
3. Registers pytest plugins
4. Provides shared fixtures for the test hierarchy
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ============================================================================
# STEP 1: Auto-discover subpackages and add to sys.path (MUST be first!)
# ============================================================================
# This runs at conftest module load time, before pytest loads test modules.
# Any subpackage imports in conftest or test collection need sys.path ready.
_repo_root = Path(__file__).resolve().parent.parent
for _child in sorted(_repo_root.iterdir()):
    if _child.is_dir() and ((_child / 'setup.py').exists() or (_child / 'setup.cfg').exists()):
        _child_str = str(_child)
        if _child_str not in sys.path:
            sys.path.insert(0, _child_str)

# ============================================================================
# STEP 2: Create Py2 compatibility mock layer (before any subpackage imports)
# ============================================================================
# zstacklib targets Python 2.7 in production. Many utility modules use Py2
# syntax that fails in Python 3. Mock these modules to allow test collection.

# Mock log module (used by many modules)
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_log.get_logger = lambda name: MagicMock()
sys.modules['log'] = _mock_log  # bare `import log` in thread.py etc.
sys.modules['zstacklib.utils.log'] = _mock_log

# Mock bash module (gpu.py does `from bash import *`)
_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log  # `from bash import *` brings `log` into scope
_mock_bash.bash_roe = lambda *a, **kw: (0, '', '')
_mock_bash.bash_ro = lambda *a, **kw: (0, '')
_mock_bash.bash_r = lambda *a, **kw: 0
sys.modules['zstacklib.utils.bash'] = _mock_bash

# Mock remaining Py2-only / unavailable modules
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

# ============================================================================
# STEP 3: pytest configuration and plugins
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
    yield
    # Mocks stay active for entire session

# ============================================================================
# STEP 4: Import shared fixtures from tests.fixtures.common
# ============================================================================
# Import all fixtures from common.py to make them globally available.
# This includes: project_root, tmp_test_dir, sample_vm_xml, fake_zstack_config, isolated_env
from tests.fixtures.common import (
    project_root,
    tmp_test_dir,
    sample_vm_xml,
    fake_zstack_config,
    isolated_env,
)

