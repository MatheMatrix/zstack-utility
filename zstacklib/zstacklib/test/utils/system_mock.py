# -*- coding: utf-8 -*-
"""
System-level mock fixtures for safe local testing of kvmagent plugins.

Provides a pytest fixture that mocks all dangerous system calls (bash, libvirt,
linux utilities, shell commands) so plugin business logic can execute locally
without a VM environment.

Usage:
    def test_something(system_mock):
        system_mock.bash_roe.return_value = (0, 'output', '')
        # ... call plugin handler ...
"""
import types
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest


class SystemMocks:
    """Container for all active system-level mocks.

    Attributes can be customized per-test via side_effect / return_value:
        system_mock.bash_roe.return_value = (0, 'custom output', '')
        system_mock.shell_run.return_value = 0
    """
    def __init__(self):
        self.bash_roe = None   # (ret, stdout, stderr)
        self.bash_ro = None    # (ret, stdout)
        self.bash_r = None     # ret
        self.bash_o = None     # stdout
        self.shell_run = None
        self.linux = None      # MagicMock for linux module
        self.libvirt = None    # MagicMock for libvirt module


@pytest.fixture
def system_mock():
    """Mock all dangerous system-level calls for safe local testing.

    Yields a SystemMocks instance whose attributes can be further customized.
    """
    import sys

    with ExitStack() as stack:
        mocks = SystemMocks()

        # --- bash layer ---
        bash_mod = sys.modules.get('zstacklib.utils.bash')
        if bash_mod and not isinstance(bash_mod, MagicMock):
            mocks.bash_roe = stack.enter_context(
                patch.object(bash_mod, 'bash_roe', return_value=(0, '', '')))
            mocks.bash_ro = stack.enter_context(
                patch.object(bash_mod, 'bash_ro', return_value=(0, '')))
            mocks.bash_r = stack.enter_context(
                patch.object(bash_mod, 'bash_r', return_value=0))
            mocks.bash_o = stack.enter_context(
                patch.object(bash_mod, 'bash_o', return_value=''))
        else:
            # bash module is already a mock (from conftest); set defaults
            mock_bash = sys.modules.get('zstacklib.utils.bash') or sys.modules.get('bash')
            if mock_bash:
                mock_bash.bash_roe = MagicMock(return_value=(0, '', ''))
                mock_bash.bash_ro = MagicMock(return_value=(0, ''))
                mock_bash.bash_r = MagicMock(return_value=0)
                mock_bash.bash_o = MagicMock(return_value='')
                mocks.bash_roe = mock_bash.bash_roe
                mocks.bash_ro = mock_bash.bash_ro
                mocks.bash_r = mock_bash.bash_r
                mocks.bash_o = mock_bash.bash_o

        # --- shell layer ---
        shell_mod = sys.modules.get('zstacklib.utils.shell')
        if shell_mod:
            if isinstance(shell_mod, MagicMock):
                shell_mod.run = MagicMock(return_value=0)
                shell_mod.call = MagicMock(return_value='')
                mocks.shell_run = shell_mod.run
            else:
                mocks.shell_run = stack.enter_context(
                    patch.object(shell_mod, 'run', return_value=0))

        # --- linux layer ---
        linux_mod = sys.modules.get('zstacklib.utils.linux')
        if linux_mod:
            if isinstance(linux_mod, MagicMock):
                linux_mod.write_file = MagicMock()
                linux_mod.write_uuids = MagicMock()
                linux_mod.fake_dead = MagicMock(return_value=False)
                linux_mod.recover_fake_dead = MagicMock()
                linux_mod.rm_file_force = MagicMock()
                linux_mod.get_exception_stacktrace = MagicMock(return_value='')
                linux_mod.wait_callback_success = MagicMock(side_effect=lambda f, **kw: f(None))
                linux_mod.HOST_ARCH = 'x86_64'
                mocks.linux = linux_mod

        # --- libvirt ---
        libvirt_mod = sys.modules.get('libvirt')
        if libvirt_mod and isinstance(libvirt_mod, MagicMock):
            mocks.libvirt = libvirt_mod

        yield mocks
