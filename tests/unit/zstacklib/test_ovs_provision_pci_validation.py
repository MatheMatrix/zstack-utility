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
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load ovs_provision_plugin.py for test: %s" % path)
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


class Obj(object):
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


@pytest.mark.unit
def test_rejects_unsafe_external_id_value_in_builder():
    plugin = _load_plugin()
    builder = plugin.OvsCommandBuilder()

    with pytest.raises(ValueError):
        builder.set_bridge_external_id("br0", "host-uuid", "host;touch /tmp/bad")

    with pytest.raises(ValueError):
        builder.set_port_external_id("bond0", "managed-by", "zstack-agent;bad")

    with pytest.raises(ValueError):
        builder.set_interface_external_id("eth0", "config-version", "1;bad")


@pytest.mark.unit
def test_accepts_safe_external_id_value_in_builder():
    plugin = _load_plugin()
    builder = plugin.OvsCommandBuilder()

    builder.set_bridge_external_id("br0", "host-uuid", "host-uuid_1")
    builder.set_port_external_id("bond0", "managed-by", "zstack-agent")
    builder.set_interface_external_id("eth0", "config-version", "1")

    command = builder.build()
    assert "br-set-external-id br0 host-uuid host-uuid_1" in command
    assert "set port bond0 external_ids:managed-by=zstack-agent" in command
    assert "set interface eth0 external_ids:config-version=1" in command


@pytest.mark.unit
def test_unwrap_spec_copies_sdn_controller_uuid():
    plugin = _load_plugin()
    cmd = Obj()
    cmd.spec = Obj()
    cmd.spec.hostUuid = "host-uuid"
    cmd.spec.configVersion = 3
    cmd.spec.sdnControllerUuid = "sdn-controller-uuid"

    plugin.OvsProvisionPlugin._unwrap_spec(cmd)

    assert cmd.hostUuid == "host-uuid"
    assert cmd.configVersion == 3
    assert cmd.sdnControllerUuid == "sdn-controller-uuid"


@pytest.mark.unit
def test_reconcile_ip_addresses_skips_when_desired_address_exists():
    plugin = _load_plugin()
    desired = plugin.OvsDesiredState()
    actual = plugin.OvsActualState()
    desired.ip_addresses["br0"] = plugin.IpAddressSpec("br0", "10.0.0.2/24")
    actual.ip_addresses["br0"] = ["10.0.0.2/24", "10.0.0.3/24"]

    calls = []
    plugin.bash.bash_roe = lambda cmd: calls.append(cmd) or (0, "", "")

    plugin.OvsReconciler._reconcile_ip_addresses(desired, actual)

    assert calls == []


@pytest.mark.unit
def test_reconcile_ip_addresses_updates_when_desired_address_missing():
    plugin = _load_plugin()
    desired = plugin.OvsDesiredState()
    actual = plugin.OvsActualState()
    desired.ip_addresses["br0"] = plugin.IpAddressSpec("br0", "10.0.0.2/24")
    actual.ip_addresses["br0"] = ["10.0.0.3/24"]

    calls = []
    plugin.bash.bash_roe = lambda cmd: calls.append(cmd) or (0, "", "")

    plugin.OvsReconciler._reconcile_ip_addresses(desired, actual)

    assert calls == [
        "ip addr flush dev br0",
        "ip addr add 10.0.0.2/24 dev br0",
        "ip link set br0 up",
    ]
