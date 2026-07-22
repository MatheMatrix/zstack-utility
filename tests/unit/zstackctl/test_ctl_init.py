# -*- coding: utf-8 -*-
import sys
import types

import pytest


def _install_missing_imports():
    try:
        import OpenSSL  # noqa: F401
    except ImportError:
        sys.modules['OpenSSL'] = types.ModuleType('OpenSSL')

    try:
        from Crypto.Cipher import AES  # noqa: F401
        from Crypto.Util.py3compat import __all__  # noqa: F401
    except ImportError:
        crypto = types.ModuleType('Crypto')
        crypto.__path__ = []
        cipher = types.ModuleType('Crypto.Cipher')
        cipher.AES = types.SimpleNamespace()
        util = types.ModuleType('Crypto.Util')
        util.__path__ = []
        py3compat = types.ModuleType('Crypto.Util.py3compat')
        py3compat.__all__ = []
        sys.modules.update({
            'Crypto': crypto,
            'Crypto.Cipher': cipher,
            'Crypto.Util': util,
            'Crypto.Util.py3compat': py3compat,
        })


_install_missing_imports()

from zstackctl import ctl


@pytest.mark.parametrize(
    'version_content',
    [None, '', ' \n', '5.5.28\n'],
    ids=['missing', 'empty', 'whitespace', 'normal'],
)
def test_ctl_initialization_reaches_command_dispatch_for_any_ui_version(
        tmp_path, monkeypatch, version_content):
    ui_home = tmp_path / 'zstack-ui'
    ui_home.mkdir()
    if version_content is not None:
        (ui_home / 'VERSION').write_text(version_content)

    monkeypatch.setattr(ctl.Ctl, 'ZSTACK_UI_HOME', str(ui_home))

    controller = ctl.Ctl()

    assert controller.commands == {}
    assert controller.command_list == []
    assert controller.main_parser.prog == 'zstack-ctl'
