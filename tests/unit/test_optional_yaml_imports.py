# -*- coding: utf-8 -*-
import builtins
import importlib
import sys


def test_kvmagent_and_ovs_modules_import_without_pyyaml(monkeypatch):
    sys.modules.pop('kvmagent.plugins.host_plugin', None)
    sys.modules.pop('zstacklib.utils.ovs', None)

    real_import = builtins.__import__

    def import_without_yaml(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'yaml' or name.startswith('yaml.'):
            raise ImportError('blocked PyYAML for import regression test')
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, '__import__', import_without_yaml)

    importlib.import_module('zstacklib.utils.ovs')
    importlib.import_module('kvmagent.plugins.host_plugin')
