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
def test_rejects_unsafe_ovs_key_in_builder():
    plugin = _load_plugin()
    builder = plugin.OvsCommandBuilder()

    with pytest.raises(ValueError):
        builder.set_bridge("br0", "datapath_type;bad", "system")

    with pytest.raises(ValueError):
        builder.set_port("bond0", "tag;bad", "100")

    with pytest.raises(ValueError):
        builder.clear_port_attr("bond0", "tag;bad")

    with pytest.raises(ValueError):
        builder.set_interface("eth0", "type;bad", "dpdk")


@pytest.mark.unit
def test_quotes_ovs_values_in_builder():
    plugin = _load_plugin()
    builder = plugin.OvsCommandBuilder()

    builder.set_interface("eth0", "type", "dpdk;touch /tmp/bad")

    assert "set interface eth0 type='dpdk;touch /tmp/bad'" in builder.build()


@pytest.mark.unit
def test_unwrap_spec_copies_sdn_controller_uuid():
    plugin = _load_plugin()
    cmd = Obj()
    cmd.spec = Obj()
    cmd.spec.hostUuid = "host-uuid"
    cmd.spec.configVersion = 3
    cmd.spec.sdnControllerUuid = "sdn-controller-uuid"
    cmd.spec.force = True
    cmd.spec.cloudCallbackUrl = "callback-url"
    cmd.spec.cloudTaskUuid = "task-uuid"
    cmd.spec.triggerUrl = "trigger-url"

    plugin.OvsProvisionPlugin._unwrap_spec(cmd)

    assert cmd.hostUuid == "host-uuid"
    assert cmd.configVersion == 3
    assert cmd.sdnControllerUuid == "sdn-controller-uuid"
    assert cmd.force is True
    assert cmd.cloudCallbackUrl == "callback-url"
    assert cmd.cloudTaskUuid == "task-uuid"
    assert cmd.triggerUrl == "trigger-url"


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


@pytest.mark.unit
def test_reconcile_system_id_conf_without_ovsdb_change_does_not_restart_ovn_controller(tmp_path):
    plugin = _load_plugin()
    plugin.OVS_SYSTEM_ID_CONF_PATH = str(tmp_path / "system-id.conf")
    desired = plugin.OvsDesiredState()
    actual = plugin.OvsActualState()
    desired.ovs_external_ids["system-id"] = "host-uuid"
    actual.ovs_external_ids["system-id"] = "host-uuid"

    calls = []
    plugin.bash.bash_roe = lambda cmd: calls.append(cmd) or (0, "", "")

    plugin.OvsReconciler().reconcile(desired, actual)

    assert pathlib.Path(plugin.OVS_SYSTEM_ID_CONF_PATH).read_text() == "host-uuid\n"
    assert "systemctl restart ovn-controller" not in calls


@pytest.mark.unit
def test_reconcile_system_id_restarts_ovn_controller_when_ovsdb_changes(tmp_path):
    plugin = _load_plugin()
    plugin.OVS_SYSTEM_ID_CONF_PATH = str(tmp_path / "system-id.conf")
    desired = plugin.OvsDesiredState()
    actual = plugin.OvsActualState()
    desired.ovs_external_ids["system-id"] = "host-uuid"
    actual.ovs_external_ids["system-id"] = "old-random-uuid"

    calls = []
    plugin.bash.bash_roe = lambda cmd: calls.append(cmd) or (0, "", "")

    plugin.OvsReconciler().reconcile(desired, actual)

    assert pathlib.Path(plugin.OVS_SYSTEM_ID_CONF_PATH).read_text() == "host-uuid\n"
    assert calls == [
        "ovs-vsctl set Open_vSwitch . external_ids:system-id=host-uuid",
        "systemctl stop ovn-controller",
        "systemctl start ovn-controller",
    ]


@pytest.mark.unit
def test_reconcile_system_id_deletes_stale_chassis_when_ovn_remote_exists(tmp_path):
    plugin = _load_plugin()
    plugin.OVS_SYSTEM_ID_CONF_PATH = str(tmp_path / "system-id.conf")
    desired = plugin.OvsDesiredState()
    actual = plugin.OvsActualState()
    desired.ovs_external_ids["system-id"] = "host-uuid"
    desired.ovs_external_ids["ovn-remote"] = "tcp:172.20.13.51:6642"
    actual.ovs_external_ids["system-id"] = "old-random-uuid"

    calls = []
    plugin.bash.bash_roe = lambda cmd: calls.append(cmd) or (0, "", "")

    plugin.OvsReconciler().reconcile(desired, actual)

    assert calls == [
        "ovs-vsctl set Open_vSwitch . external_ids:system-id=host-uuid external_ids:ovn-remote=tcp:172.20.13.51:6642",
        "systemctl stop ovn-controller",
        "ovn-sbctl --timeout=5 --db=tcp:172.20.13.51:6642 chassis-del old-random-uuid",
        "systemctl start ovn-controller",
    ]


@pytest.mark.unit
def test_deprovision_ownership_check_fails_closed_on_read_error():
    plugin = _load_plugin()

    class VsCtl(object):
        def getOvsExternalIdsConfig(self, key):
            return True, None

    plugin.ovn.VsCtl = VsCtl

    with pytest.raises(Exception) as exc:
        plugin.OvsProvisionPlugin._check_deprovision_ownership("controller-a")

    assert "unable to read sdn-controller-uuid" in str(exc.value)


@pytest.mark.unit
def test_deprovision_ownership_check_fails_closed_on_exception():
    plugin = _load_plugin()

    class VsCtl(object):
        def getOvsExternalIdsConfig(self, key):
            raise RuntimeError("ovsdb unavailable")

    plugin.ovn.VsCtl = VsCtl

    with pytest.raises(Exception) as exc:
        plugin.OvsProvisionPlugin._check_deprovision_ownership("controller-a")

    assert "ovsdb unavailable" in str(exc.value)


@pytest.mark.unit
def test_deprovision_ownership_check_rejects_other_controller():
    plugin = _load_plugin()

    class VsCtl(object):
        def getOvsExternalIdsConfig(self, key):
            return False, "controller-b"

    plugin.ovn.VsCtl = VsCtl

    with pytest.raises(Exception) as exc:
        plugin.OvsProvisionPlugin._check_deprovision_ownership("controller-a")

    assert "already managed by another SdnController" in str(exc.value)


@pytest.mark.unit
def test_deprovision_ownership_check_accepts_current_controller():
    plugin = _load_plugin()

    class VsCtl(object):
        def getOvsExternalIdsConfig(self, key):
            return False, "controller-a"

    plugin.ovn.VsCtl = VsCtl

    plugin.OvsProvisionPlugin._check_deprovision_ownership("controller-a")


@pytest.mark.unit
def test_fallback_dpdk_switches_to_system_clears_dpdk_config():
    plugin = _load_plugin()
    cmd = Obj()
    cmd.dpdkConfig = Obj()
    switch_with_type = Obj()
    switch_with_type.type = "dpdk"
    switch_with_type_ = Obj()
    switch_with_type_.type_ = "dpdk"

    plugin.OvsProvisionPlugin._fallback_dpdk_switches_to_system(
        cmd, [switch_with_type, switch_with_type_])

    assert cmd.dpdkConfig is None
    assert switch_with_type.type == "system"
    assert switch_with_type_.type_ == "system"


@pytest.mark.unit
def test_build_nic_pci_map_logs_sysfs_failure_and_uses_dpdk_fallback():
    plugin = _load_plugin()
    messages = []
    plugin.logger.debug = lambda msg: messages.append(msg)

    def get_bdf(member):
        raise RuntimeError("sysfs unavailable")

    plugin.ovs_utils.getBDFOfInterface = get_bdf
    dpdk_nic = Obj()
    dpdk_nic.name = "eth0"
    dpdk_nic.pciAddress = "0000:00:04.0"
    plugin.ovn.getAllDpdkNic = lambda: [dpdk_nic]

    lag = Obj()
    lag.members = ["eth0"]
    uplink = Obj()
    uplink.lag = [lag]
    sw = Obj()
    sw.uplinkProfile = uplink

    result = plugin.OvsProvisionPlugin._build_nic_pci_map_from_uplink([sw])

    assert result.eth0 == "0000:00:04.0"
    assert "getBDFOfInterface(eth0) failed" in messages[0]


@pytest.mark.unit
def test_stop_openvswitch_before_nic_restore_raises_on_failure():
    plugin = _load_plugin()
    plugin.bash.bash_roe = lambda cmd: (1, "", "stop failed")

    with pytest.raises(Exception) as exc:
        plugin.OvsProvisionPlugin._stop_openvswitch_before_nic_restore()

    assert "failed to stop openvswitch before restoring NIC drivers" in str(exc.value)


@pytest.mark.unit
def test_deprovision_unwraps_spec_before_reading_fields():
    plugin = _load_plugin()
    plugin.http.REQUEST_BODY = "body"
    cmd = Obj()
    cmd.spec = Obj()
    cmd.spec.hostUuid = "host-uuid"
    cmd.spec.sdnControllerUuid = "controller-uuid"
    cmd.spec.force = True
    cmd.spec.cloudCallbackUrl = "callback-url"
    cmd.spec.cloudTaskUuid = "task-uuid"
    cmd.spec.triggerUrl = "trigger-url"
    plugin.jsonobject.loads = lambda body: cmd
    plugin.jsonobject.dumps = lambda obj: obj

    def bash_roe(command):
        if command.startswith("systemctl is-active "):
            return 3, "inactive\n", ""
        if command == "timeout 5 ovs-vsctl show":
            return 1, "", "unreachable"
        raise AssertionError("unexpected command: %s" % command)

    plugin.bash.bash_roe = bash_roe

    rsp = plugin.OvsProvisionPlugin().deprovision({"body": "{}"})

    assert not hasattr(rsp, "error")
    assert rsp.hostUuid == "host-uuid"
    assert rsp.cloudCallbackUrl == "callback-url"
    assert rsp.cloudTaskUuid == "task-uuid"
    assert rsp.triggerUrl == "trigger-url"
