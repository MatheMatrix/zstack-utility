# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys
import types

import pytest


def _stub_module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _load_plugin():
    stub_names = [
        "kvmagent", "kvmagent.kvmagent", "zstacklib", "zstacklib.utils",
        "zstacklib.utils.http", "zstacklib.utils.jsonobject",
        "zstacklib.utils.ovs", "zstacklib.utils.log",
        "zstacklib.utils.bash", "zstacklib.utils.lock",
        "zstacklib.utils.ovn",
    ]
    sentinel = object()
    saved = {name: sys.modules.get(name, sentinel) for name in stub_names}

    kvmagent_pkg = _stub_module("kvmagent")
    kvmagent_mod = _stub_module("kvmagent.kvmagent")
    kvmagent_mod.AgentResponse = type("AgentResponse", (), {})
    kvmagent_mod.AgentCommand = type("AgentCommand", (), {})
    kvmagent_mod.KvmAgent = type("KvmAgent", (), {})
    kvmagent_mod.replyerror = lambda fn: fn
    kvmagent_mod.get_http_server = lambda: None
    kvmagent_pkg.kvmagent = kvmagent_mod

    _stub_module("zstacklib")
    utils_pkg = _stub_module("zstacklib.utils")
    for name in ("http", "jsonobject", "ovs"):
        module = _stub_module("zstacklib.utils.%s" % name)
        setattr(utils_pkg, name, module)

    log = _stub_module("zstacklib.utils.log")
    log.get_logger = lambda name: type("Logger", (), {
        "debug": lambda self, *args, **kwargs: None,
        "info": lambda self, *args, **kwargs: None,
        "warn": lambda self, *args, **kwargs: None,
        "error": lambda self, *args, **kwargs: None,
    })()
    utils_pkg.log = log

    bash = _stub_module("zstacklib.utils.bash")
    bash.in_bash = lambda fn: fn
    utils_pkg.bash = bash

    lock = _stub_module("zstacklib.utils.lock")
    lock.lock = lambda name: (lambda fn: fn)
    utils_pkg.lock = lock

    ovn = _stub_module("zstacklib.utils.ovn")
    ovn.VsCtl = type("VsCtl", (), {})
    utils_pkg.ovn = ovn

    path = pathlib.Path(__file__).parents[3] / "kvmagent/kvmagent/plugins/ovs_provision_plugin.py"
    spec = importlib.util.spec_from_file_location("ovs_provision_plugin_for_test", str(path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in saved.items():
            if old is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


class NicPciMap(object):
    pass


@pytest.mark.unit
def test_rejects_invalid_dpdk_pci_address_before_command_build():
    plugin = _load_plugin()
    pci_map = NicPciMap()
    pci_map.eth0 = "0000:00:04.0;touch /tmp/bad"
    spec = plugin.BondSpec("bond0", ["eth0"], switch_type="dpdk")

    with pytest.raises(ValueError):
        plugin.OvsReconciler._build_add_bond(
            plugin.OvsCommandBuilder(), "br0", spec, 1, pci_map)


@pytest.mark.unit
def test_accepts_valid_dpdk_pci_address():
    plugin = _load_plugin()
    pci_map = NicPciMap()
    pci_map.eth0 = "0000:00:04.0"
    spec = plugin.BondSpec("bond0", ["eth0"], switch_type="dpdk")
    builder = plugin.OvsCommandBuilder()

    plugin.OvsReconciler._build_add_bond(builder, "br0", spec, 1, pci_map)

    assert "options:dpdk-devargs=0000:00:04.0" in builder.build()
