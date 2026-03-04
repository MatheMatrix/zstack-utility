"""Tests for network.ovs module."""

import pytest

from zstacklib.network.ovs.models import (
    BondType,
    VNicType,
    Bond,
    VHostAddOn,
    NicBackend,
    OvsVersionInfo,
)
from zstacklib.network.ovs.exceptions import (
    OvsError,
    OvsConfigError,
    OvsBridgeError,
    OvsPortError,
    OvsDaemonError,
    OvsDpdkError,
    OvsBondError,
)


class TestBondType:
    def test_bond_type_values(self):
        assert BondType.NormalIface.value == 0
        assert BondType.KernelBond.value == 1
        assert BondType.DpdkBond.value == 2
        assert BondType.OvsBond.value == 3
        assert BondType.VfLag.value == 4

    def test_bond_type_comparison(self):
        assert BondType.KernelBond != BondType.OvsBond


class TestVNicType:
    def test_vnic_type_values(self):
        assert VNicType.vDPA.value == 0
        assert VNicType.dpdkvhostuserclient.value == 1


class TestBond:
    def test_bond_defaults(self):
        bond = Bond()
        assert bond.name == "default"
        assert bond.mode == 1
        assert bond.lacp == "off"
        assert bond.slaves == []
        assert bond.options == "dpdkBond"

    def test_bond_custom(self):
        bond = Bond(
            name="bond0",
            mode=4,
            lacp="active",
            slaves=["eth0", "eth1"],
            options="ovsBond",
        )
        assert bond.name == "bond0"
        assert bond.mode == 4
        assert bond.lacp == "active"
        assert len(bond.slaves) == 2


class TestVHostAddOn:
    def test_vhost_addon_default(self):
        addon = VHostAddOn()
        assert addon.queue_num is None

    def test_vhost_addon_with_queues(self):
        addon = VHostAddOn(queue_num=4)
        assert addon.queue_num == 4


class TestNicBackend:
    def test_nic_backend_defaults(self):
        backend = NicBackend()
        assert backend.bridge_name == ""
        assert backend.type == "vNic"
        assert backend.vlan_id is None

    def test_nic_backend_dpdk(self):
        backend = NicBackend(
            bridge_name="br-dpdk",
            nic_internal_name="vhost0",
            type="dpdkvhostuserclient",
            pci_device_address="0000:1f:00.0",
        )
        assert backend.bridge_name == "br-dpdk"
        assert backend.type == "dpdkvhostuserclient"
        assert backend.pci_device_address == "0000:1f:00.0"


class TestOvsVersionInfo:
    def test_version_info_defaults(self):
        info = OvsVersionInfo()
        assert info.ofed_ver == "unknown"
        assert info.vswitch_ver == "unknown"
        assert info.dpdk_ver == "unknown"
        assert info.ovsdb_ver == "unknown"

    def test_is_dpdk_support_false(self):
        info = OvsVersionInfo()
        assert info.is_dpdk_support() is False

    def test_is_dpdk_support_true(self):
        info = OvsVersionInfo(dpdk_ver="21.11.1")
        assert info.is_dpdk_support() is True

    def test_is_mellanox_support_false(self):
        info = OvsVersionInfo()
        assert info.is_mellanox_support() is False

    def test_is_mellanox_support_true(self):
        info = OvsVersionInfo(ofed_ver="5.4-1.0.3.0")
        assert info.is_mellanox_support() is True

    def test_full_version_info(self):
        info = OvsVersionInfo(
            ofed_ver="5.4-1.0.3.0",
            vswitch_ver="2.17.0",
            dpdk_ver="21.11.1",
            ovsdb_ver="2.17.0",
        )
        assert info.is_dpdk_support() is True
        assert info.is_mellanox_support() is True


class TestOvsExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(OvsConfigError, OvsError)
        assert issubclass(OvsBridgeError, OvsError)

    def test_exception_message(self):
        err = OvsError("bridge creation failed")
        assert str(err) == "bridge creation failed"
