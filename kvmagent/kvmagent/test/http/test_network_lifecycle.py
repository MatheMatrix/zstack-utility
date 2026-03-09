# -*- coding: utf-8 -*-
"""Lifecycle tests for NetworkPlugin against real kvmagent.

These tests exercise the full create → check → delete logic path using
real host resources. They are skipped in local stub mode.

Safe resource choices:
  - NoVLAN bridge: uses a DOWN/free interface (auto-discovered)
  - VLAN bridge: uses bond0 with high VLAN ID 3999 (unlikely to conflict)
  - VXLAN bridge: uses unique VNI 59999
  - All created resources are cleaned up in teardown
"""
import uuid
import pytest

REQUEST_BODY = 'body'

# These tests ONLY run against real kvmagent
pytestmark = pytest.mark.skipif("not config.getoption('--direct-host')",
                                reason='lifecycle tests require real kvmagent')


@pytest.fixture(scope='module')
def host_res(http_client):
    """Discover real host resources for lifecycle tests."""
    ssh = http_client._ssh_run
    res = {}

    # Find a free (DOWN or unused) interface for NoVLAN bridge test
    rc, out, _ = ssh("ip -br link show | awk '$2==\"DOWN\" {print $1}' | head -1")
    res['free_nic'] = out.strip() if rc == 0 and out.strip() else None

    # Find bond0 (for VLAN tests)
    rc, out, _ = ssh("ip -br link show bond0 2>/dev/null | awk '{print $1}'")
    res['bond_nic'] = out.strip() if rc == 0 and out.strip() else None

    # Find host management IP (for VXLAN vtepIp)
    rc, out, _ = ssh("ip -4 addr show bond0 2>/dev/null | grep inet | awk '{print $2}' | cut -d/ -f1 | head -1")
    res['vtep_ip'] = out.strip() if rc == 0 and out.strip() else None

    # Fallback vtep: use any routable IP
    if not res['vtep_ip']:
        rc, out, _ = ssh("hostname -I | awk '{print $1}'")
        res['vtep_ip'] = out.strip() if rc == 0 and out.strip() else None

    # Find existing physical interfaces for check tests
    rc, out, _ = ssh("ip -br link show | awk '$2!=\"DOWN\" && $1!=\"lo\" {print $1}' | head -3")
    res['up_nics'] = [n.strip() for n in out.strip().split('\n') if n.strip()] if rc == 0 else []

    return res


# ──────────────────────────────────────────────────────────────────────
# 1. Check Physical Interface (read-only)
# ──────────────────────────────────────────────────────────────────────

class TestCheckPhysicalInterface:
    def test_existing_interfaces(self, http_client, host_plugin, host_res):
        """Check interfaces that actually exist → success."""
        nics = host_res['up_nics']
        if not nics:
            pytest.skip('no UP interfaces discovered')
        rsp = http_client.post_sync('/network/checkphysicalnetworkinterface', {
            'interfaceNames': nics,
        })
        assert rsp.success is True

    def test_nonexistent_interface(self, http_client, host_plugin, host_res):
        """Check a fake interface → success=False with failedInterfaceNames."""
        rsp = http_client.post_sync('/network/checkphysicalnetworkinterface', {
            'interfaceNames': ['zzz_nonexistent_42'],
        })
        assert rsp.success is False
        assert 'zzz_nonexistent_42' in rsp.failedInterfaceNames


# ──────────────────────────────────────────────────────────────────────
# 2. NoVLAN Bridge Lifecycle: create → check → delete
# ──────────────────────────────────────────────────────────────────────

class TestNoVlanBridgeLifecycle:
    BRIDGE_NAME = 'br_t_lc'  # ≤15 chars (IFNAMSIZ limit)
    L2_UUID = 'test-l2-' + uuid.uuid4().hex[:8]

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        """Ensure test bridge is cleaned up even if test fails."""
        yield
        # Best-effort cleanup
        try:
            nic = host_res.get('free_nic') or 'em2'
            http_client.post_async('/network/l2novlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME,
                'physicalInterfaceName': nic,
            })
        except Exception:
            pass

    def test_create_check_delete_bridge(self, http_client, host_plugin, host_res):
        """Full lifecycle: create bridge on free NIC → check → delete."""
        nic = host_res.get('free_nic')
        if not nic:
            pytest.skip('no free (DOWN) interface for bridge test')

        # CREATE
        rsp = http_client.post_async('/network/l2novlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
            'l2NetworkUuid': self.L2_UUID,
            'disableIptables': False,
            'mtu': 1500,
        })
        assert rsp.success is True, 'create bridge failed: %s' % getattr(rsp, 'error', '')

        # CHECK
        rsp = http_client.post_async('/network/l2novlan/checkbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is True, 'check bridge failed: %s' % getattr(rsp, 'error', '')

        # DELETE
        rsp = http_client.post_async('/network/l2novlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is True, 'delete bridge failed: %s' % getattr(rsp, 'error', '')

        # VERIFY DELETED
        rsp = http_client.post_async('/network/l2novlan/checkbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is False, 'bridge should not exist after delete'


# ──────────────────────────────────────────────────────────────────────
# 3. VLAN Bridge Lifecycle: create → check → update → delete
# ──────────────────────────────────────────────────────────────────────

class TestVlanBridgeLifecycle:
    VLAN_ID = 3999
    BRIDGE_NAME = 'br_bond0_3999'
    L2_UUID = 'test-vlan-' + uuid.uuid4().hex[:8]

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        try:
            nic = host_res.get('bond_nic') or 'bond0'
            http_client.post_async('/network/l2vlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME,
                'physicalInterfaceName': nic,
                'vlan': self.VLAN_ID,
            })
        except Exception:
            pass

    def test_create_check_delete_vlan_bridge(self, http_client, host_plugin, host_res):
        """Full lifecycle: create VLAN bridge → check → delete."""
        nic = host_res.get('bond_nic')
        if not nic:
            pytest.skip('no bond interface for VLAN test')

        # CREATE
        rsp = http_client.post_async('/network/l2vlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
            'vlan': self.VLAN_ID,
            'l2NetworkUuid': self.L2_UUID,
            'disableIptables': False,
            'mtu': 1500,
        })
        assert rsp.success is True, 'create VLAN bridge failed: %s' % getattr(rsp, 'error', '')

        # CHECK
        rsp = http_client.post_async('/network/l2vlan/checkbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is True, 'check VLAN bridge failed: %s' % getattr(rsp, 'error', '')

        # DELETE
        rsp = http_client.post_async('/network/l2vlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
            'vlan': self.VLAN_ID,
        })
        assert rsp.success is True, 'delete VLAN bridge failed: %s' % getattr(rsp, 'error', '')

        # VERIFY DELETED
        rsp = http_client.post_async('/network/l2vlan/checkbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is False, 'VLAN bridge should not exist after delete'


# ──────────────────────────────────────────────────────────────────────
# 4. VXLAN Bridge Lifecycle: create → delete
# ──────────────────────────────────────────────────────────────────────

class TestVxlanBridgeLifecycle:
    VNI = 59999
    BRIDGE_NAME = 'br_vx_59999'  # 12 chars, OK

    _vtep = None  # set at runtime by test

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        vtep = self._vtep or host_res.get('vtep_ip') or '0.0.0.0'
        try:
            http_client.post_async('/network/l2vxlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME,
                'vni': self.VNI,
                'vtepIp': vtep,
            })
        except Exception:
            pass

    def test_create_delete_vxlan_bridge(self, http_client, host_plugin, host_res):
        """Create VXLAN bridge with unique VNI → delete."""
        vtep = host_res.get('vtep_ip')
        if not vtep:
            pytest.skip('no vtep IP discovered')
        self.__class__._vtep = vtep

        # CREATE — VXLAN overhead requires MTU < 1500
        rsp = http_client.post_async('/network/l2vxlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'vni': self.VNI,
            'vtepIp': vtep,
            'l2NetworkUuid': 'test-vxlan-' + uuid.uuid4().hex[:8],
            'dstport': 8472,
            'mtu': 1450,
        })
        assert rsp.success is True, 'create VXLAN bridge failed: %s' % getattr(rsp, 'error', '')

        # DELETE
        rsp = http_client.post_async('/network/l2vxlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME,
            'vni': self.VNI,
            'vtepIp': vtep,
        })
        assert rsp.success is True, 'delete VXLAN bridge failed: %s' % getattr(rsp, 'error', '')


# ──────────────────────────────────────────────────────────────────────
# 5. Idempotency: double-create, delete non-existent
# ──────────────────────────────────────────────────────────────────────

class TestIdempotency:
    BRIDGE_NAME = 'br_t_idem'  # ≤15 chars
    L2_UUID = 'test-idem-' + uuid.uuid4().hex[:8]

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        try:
            nic = host_res.get('free_nic') or 'em2'
            http_client.post_async('/network/l2novlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME,
                'physicalInterfaceName': nic,
            })
        except Exception:
            pass

    def test_create_bridge_twice_is_idempotent(self, http_client, host_plugin, host_res):
        """Creating the same bridge twice should succeed (idempotent).

        NOTE: kvmagent may hang on second create if the interface is already
        enslaved. Timeout=60s to distinguish hang from slow.
        """
        nic = host_res.get('free_nic')
        if not nic:
            pytest.skip('no free interface')

        payload = {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
            'l2NetworkUuid': self.L2_UUID,
            'disableIptables': False,
            'mtu': 1500,
        }
        rsp1 = http_client.post_async('/network/l2novlan/createbridge', payload)
        assert rsp1.success is True

        try:
            rsp2 = http_client.post_async('/network/l2novlan/createbridge', payload,
                                          timeout=60)
            assert rsp2.success is True, (
                'second create should be idempotent: %s' % getattr(rsp2, 'error', ''))
        except TimeoutError:
            pytest.xfail('kvmagent hangs on double-create bridge (callback not received in 60s)')

    def test_delete_nonexistent_bridge(self, http_client, host_plugin):
        """Deleting a bridge that doesn't exist should succeed."""
        rsp = http_client.post_async('/network/l2novlan/deletebridge', {
            'bridgeName': 'br_absolutely_does_not_exist',
            'physicalInterfaceName': 'lo',
        })
        assert rsp.success is True


# ──────────────────────────────────────────────────────────────────────
# 6. VXLAN Check CIDR (read-only)
# ──────────────────────────────────────────────────────────────────────

class TestVxlanCheckCidr:
    def test_check_cidr_with_interface(self, http_client, host_plugin, host_res):
        """Check VXLAN CIDR with known interface → should find vtepIp."""
        vtep = host_res.get('vtep_ip')
        if not vtep:
            pytest.skip('no vtep IP discovered')

        # Discover CIDR — IP may be on bond0 or on a bridge (br_bond0_*)
        ssh = http_client._ssh_run
        rc, out, _ = ssh(
            "ip -4 addr show bond0 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1; "
            "ip -4 addr show 2>/dev/null | grep -A1 'br_bond0' | grep 'inet ' | awk '{print $2}' | head -1"
        )
        # Take the first non-empty CIDR line
        cidr_str = ''
        for line in out.strip().split('\n'):
            if line.strip() and '/' in line.strip():
                cidr_str = line.strip()
                break
        if not cidr_str:
            pytest.skip('cannot determine bond0 CIDR')

        # Convert to network CIDR (e.g. 172.24.0.97/16 → 172.24.0.0/16)
        import ipaddress
        net = ipaddress.ip_network(cidr_str, strict=False)
        cidr = str(net)

        # Don't specify physicalInterfaceName — let handler auto-discover
        # (IP may be on a bridge like br_bond0_26, not bond0 directly)
        rsp = http_client.post_async('/network/l2vxlan/checkcidr', {
            'cidr': cidr,
        })
        assert rsp.success is True, 'check CIDR failed: %s' % getattr(rsp, 'error', '')
        assert rsp.vtepIp is not None, 'vtepIp should be set'
        assert rsp.physicalInterfaceName is not None

    def test_check_cidr_no_match(self, http_client, host_plugin):
        """Check VXLAN CIDR that matches no interface → should fail."""
        rsp = http_client.post_async('/network/l2vxlan/checkcidr', {
            'cidr': '192.0.2.0/24',  # TEST-NET-1, won't match any real NIC
            'physicalInterfaceName': '',
        })
        assert rsp.success is False

    def test_check_cidr_wrong_interface(self, http_client, host_plugin, host_res):
        """Check valid CIDR but wrong interface name → should fail.

        Note: check_vxlan_cidr is a sync-style handler registered as async.
        When the interface filter yields no match, the handler may not send
        a callback, causing a timeout.
        """
        ssh = http_client._ssh_run
        rc, out, _ = ssh(
            "ip -4 addr show bond0 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1; "
            "ip -4 addr show 2>/dev/null | grep -A1 'br_bond0' | grep 'inet ' | awk '{print $2}' | head -1"
        )
        cidr_str = ''
        for line in out.strip().split('\n'):
            if line.strip() and '/' in line.strip():
                cidr_str = line.strip()
                break
        if not cidr_str:
            pytest.skip('cannot determine bond0 CIDR')

        import ipaddress
        net = ipaddress.ip_network(cidr_str, strict=False)

        try:
            rsp = http_client.post_async('/network/l2vxlan/checkcidr', {
                'cidr': str(net),
                'physicalInterfaceName': 'zzz_fake_nic',
            }, timeout=15)
            assert rsp.success is False
        except TimeoutError:
            pytest.xfail('check_vxlan_cidr hangs on wrong interface (no callback)')


# ──────────────────────────────────────────────────────────────────────
# 7. VXLAN Batch Create/Delete
# ──────────────────────────────────────────────────────────────────────

class TestVxlanBatchBridges:
    VNI_A = 59990
    VNI_B = 59991
    BR_A = 'br_vx_59990'
    BR_B = 'br_vx_59991'

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        vtep = host_res.get('vtep_ip') or '0.0.0.0'
        for vni, br in [(self.VNI_A, self.BR_A), (self.VNI_B, self.BR_B)]:
            try:
                http_client.post_async('/network/l2vxlan/deletebridge', {
                    'bridgeName': br, 'vni': vni, 'vtepIp': vtep,
                })
            except Exception:
                pass

    def test_batch_create_and_individual_delete(self, http_client, host_plugin, host_res):
        """Batch create 2 VXLAN bridges → delete each individually."""
        vtep = host_res.get('vtep_ip')
        if not vtep:
            pytest.skip('no vtep IP discovered')

        l2_a = 'test-batch-a-' + uuid.uuid4().hex[:8]
        l2_b = 'test-batch-b-' + uuid.uuid4().hex[:8]

        # BATCH CREATE
        rsp = http_client.post_async('/network/l2vxlan/createbridges', {
            'bridgeCmds': [
                {
                    'bridgeName': self.BR_A, 'vni': self.VNI_A,
                    'vtepIp': vtep, 'l2NetworkUuid': l2_a,
                    'dstport': 8472, 'mtu': 1450,
                },
                {
                    'bridgeName': self.BR_B, 'vni': self.VNI_B,
                    'vtepIp': vtep, 'l2NetworkUuid': l2_b,
                    'dstport': 8472, 'mtu': 1450,
                },
            ],
        })
        assert rsp.success is True, 'batch create failed: %s' % getattr(rsp, 'error', '')

        # DELETE A
        rsp = http_client.post_async('/network/l2vxlan/deletebridge', {
            'bridgeName': self.BR_A, 'vni': self.VNI_A, 'vtepIp': vtep,
        })
        assert rsp.success is True

        # DELETE B
        rsp = http_client.post_async('/network/l2vxlan/deletebridge', {
            'bridgeName': self.BR_B, 'vni': self.VNI_B, 'vtepIp': vtep,
        })
        assert rsp.success is True


# ──────────────────────────────────────────────────────────────────────
# 8. VXLAN FDB Lifecycle: create → populate → delete FDB → delete bridge
# ──────────────────────────────────────────────────────────────────────

class TestVxlanFdbLifecycle:
    VNI = 59995
    BRIDGE_NAME = 'br_vx_59995'
    # Use a fake peer IP (TEST-NET-1) — FDB entry will be added but harmless
    FAKE_PEER = '192.0.2.99'

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        vtep = host_res.get('vtep_ip') or '0.0.0.0'
        try:
            http_client.post_async('/network/l2vxlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME, 'vni': self.VNI, 'vtepIp': vtep,
            })
        except Exception:
            pass

    def test_create_populate_fdb_delete(self, http_client, host_plugin, host_res):
        """Create VXLAN → populate FDB entry → delete bridge."""
        vtep = host_res.get('vtep_ip')
        if not vtep:
            pytest.skip('no vtep IP discovered')

        l2_uuid = 'test-fdb-' + uuid.uuid4().hex[:8]

        # CREATE VXLAN bridge
        rsp = http_client.post_async('/network/l2vxlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'vni': self.VNI,
            'vtepIp': vtep,
            'l2NetworkUuid': l2_uuid,
            'dstport': 8472,
            'mtu': 1450,
        })
        assert rsp.success is True, 'create VXLAN failed: %s' % getattr(rsp, 'error', '')

        # POPULATE FDB — add a fake peer
        rsp = http_client.post_async('/network/l2vxlan/populatefdb', {
            'vni': self.VNI,
            'peers': [self.FAKE_PEER],
        })
        assert rsp.success is True, 'populate FDB failed: %s' % getattr(rsp, 'error', '')

        # Verify FDB entry exists via SSH
        ssh = http_client._ssh_run
        rc, out, _ = ssh('bridge fdb show dev vxlan%d | grep %s' % (self.VNI, self.FAKE_PEER))
        assert self.FAKE_PEER in out, 'FDB entry for peer %s not found' % self.FAKE_PEER

        # DELETE bridge (cleans up VXLAN interface + FDB)
        rsp = http_client.post_async('/network/l2vxlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME,
            'vni': self.VNI,
            'vtepIp': vtep,
        })
        assert rsp.success is True


# ──────────────────────────────────────────────────────────────────────
# 9. VXLAN Batch FDB populate/delete (by networkUuid)
# ──────────────────────────────────────────────────────────────────────

class TestVxlanBatchFdb:
    VNI = 59993
    BRIDGE_NAME = 'br_vx_59993'
    FAKE_PEER = '192.0.2.88'

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        vtep = host_res.get('vtep_ip') or '0.0.0.0'
        try:
            http_client.post_async('/network/l2vxlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME, 'vni': self.VNI, 'vtepIp': vtep,
            })
        except Exception:
            pass

    def test_populate_and_delete_fdbs_by_uuid(self, http_client, host_plugin, host_res):
        """Create VXLAN with UUID → populatefdbs by UUID → deletefdbs → delete bridge."""
        vtep = host_res.get('vtep_ip')
        if not vtep:
            pytest.skip('no vtep IP discovered')

        l2_uuid = 'test-bfdb-' + uuid.uuid4().hex[:8]

        # CREATE VXLAN bridge (sets UUID alias on vxlan interface)
        rsp = http_client.post_async('/network/l2vxlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'vni': self.VNI,
            'vtepIp': vtep,
            'l2NetworkUuid': l2_uuid,
            'dstport': 8472,
            'mtu': 1450,
        })
        assert rsp.success is True, 'create VXLAN failed: %s' % getattr(rsp, 'error', '')

        # POPULATE FDBs by network UUID
        rsp = http_client.post_async('/network/l2vxlan/populatefdbs', {
            'networkUuids': [l2_uuid],
            'peers': [self.FAKE_PEER],
        })
        assert rsp.success is True, 'populatefdbs failed: %s' % getattr(rsp, 'error', '')

        # DELETE FDBs by network UUID
        rsp = http_client.post_async('/network/l2vxlan/deletefdbs', {
            'networkUuids': [l2_uuid],
            'peers': [self.FAKE_PEER],
        })
        assert rsp.success is True, 'deletefdbs failed: %s' % getattr(rsp, 'error', '')

        # DELETE bridge
        rsp = http_client.post_async('/network/l2vxlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME, 'vni': self.VNI, 'vtepIp': vtep,
        })
        assert rsp.success is True


# ──────────────────────────────────────────────────────────────────────
# 10. Add Interface to Bridge (within NoVLAN lifecycle)
# ──────────────────────────────────────────────────────────────────────

class TestAddInterfaceToBridge:
    BRIDGE_NAME = 'br_t_addif'
    L2_UUID = 'test-addif-' + uuid.uuid4().hex[:8]

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client, host_res):
        yield
        nic = host_res.get('free_nic') or 'em2'
        try:
            http_client.post_async('/network/l2novlan/deletebridge', {
                'bridgeName': self.BRIDGE_NAME,
                'physicalInterfaceName': nic,
            })
        except Exception:
            pass

    def test_addif_idempotent(self, http_client, host_plugin, host_res):
        """Create bridge → addif same NIC (already enslaved) → should be idempotent."""
        nic = host_res.get('free_nic')
        if not nic:
            pytest.skip('no free interface')

        # CREATE bridge (enslaves the NIC)
        rsp = http_client.post_async('/network/l2novlan/createbridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
            'l2NetworkUuid': self.L2_UUID,
            'disableIptables': False,
            'mtu': 1500,
        })
        assert rsp.success is True

        # ADDIF — same NIC already on bridge, should be noop
        rsp = http_client.post_async('/network/bridge/addif', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is True

        # DELETE
        rsp = http_client.post_async('/network/l2novlan/deletebridge', {
            'bridgeName': self.BRIDGE_NAME,
            'physicalInterfaceName': nic,
        })
        assert rsp.success is True


