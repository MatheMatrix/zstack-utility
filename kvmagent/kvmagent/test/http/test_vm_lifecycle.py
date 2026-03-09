# -*- coding: utf-8 -*-
"""Lifecycle tests for VmPlugin against real kvmagent.

Safe read-only operations only: vm_sync, get_console_port, get_cpu_xml.
No destructive operations (start/stop/destroy/migrate).
"""
import pytest

REQUEST_BODY = 'body'

pytestmark = pytest.mark.skipif("not config.getoption('--direct-host')",
                                reason='lifecycle tests require real kvmagent')


def _ok(rsp):
    """Check response is successful (field may be absent/None on success)."""
    return getattr(rsp, 'success', True) is not False


# ──────────────────────────────────────────────────────────────────────
# 1. VM Sync (list all VM states)
# ──────────────────────────────────────────────────────────────────────

class TestVmSync:
    def test_vm_sync_returns_states(self, http_client, host_plugin):
        """vm_sync should return a dict of vmUuid → state."""
        rsp = http_client.post_async('/vm/vmsync', {})
        assert _ok(rsp)
        assert rsp.states is not None, 'states should not be None'

    def test_vm_sync_states_are_valid(self, http_client, host_plugin):
        """Each VM state should be a known state string."""
        rsp = http_client.post_async('/vm/vmsync', {})
        assert _ok(rsp)
        valid_states = {
            'Running', 'Stopped', 'Paused', 'Shutdown', 'Crashed',
            'Suspended', 'Unknown',
        }
        states = rsp.states.__dict__ if hasattr(rsp.states, '__dict__') else {}
        for vm_uuid, state in states.items():
            assert state in valid_states, (
                'VM %s has unexpected state: %s' % (vm_uuid, state))

    def test_vm_sync_has_running_vms(self, http_client, host_plugin):
        """Host should have at least one running VM (CI environment)."""
        rsp = http_client.post_async('/vm/vmsync', {})
        assert _ok(rsp)
        states = rsp.states.__dict__ if hasattr(rsp.states, '__dict__') else {}
        running = [u for u, s in states.items() if s == 'Running']
        if not running:
            pytest.skip('no running VMs on host')
        assert len(running) > 0


# ──────────────────────────────────────────────────────────────────────
# 2. Get Console Port
# ──────────────────────────────────────────────────────────────────────

class TestGetConsolePort:
    @pytest.fixture(scope='module')
    def running_vm_uuid(self, http_client):
        """Find a running VM UUID for console port tests."""
        rsp = http_client.post_async('/vm/vmsync', {})
        if not _ok(rsp) or rsp.states is None:
            return None
        states = rsp.states.__dict__ if hasattr(rsp.states, '__dict__') else {}
        for vm_uuid, state in states.items():
            if state == 'Running':
                return vm_uuid
        return None

    def test_get_console_port(self, http_client, host_plugin, running_vm_uuid):
        """Get console port for a running VM → should have a port."""
        if not running_vm_uuid:
            pytest.skip('no running VM for console port test')
        rsp = http_client.post_async('/vm/getvncport', {
            'vmUuid': running_vm_uuid,
        })
        assert _ok(rsp), 'get console port failed: %s' % getattr(rsp, 'error', '')
        assert rsp.port is not None, 'port should not be None'
        assert int(rsp.port) > 0, 'port should be > 0, got: %s' % rsp.port
        assert rsp.protocol is not None, 'protocol should be set'

    def test_get_console_port_nonexistent_vm(self, http_client, host_plugin):
        """Get console port for fake VM → should fail."""
        rsp = http_client.post_async('/vm/getvncport', {
            'vmUuid': '00000000000000000000000000000000',
        })
        # Should return success=False with error
        assert rsp.success is False, 'should fail for nonexistent VM'


# ──────────────────────────────────────────────────────────────────────
# 3. Get CPU XML
# ──────────────────────────────────────────────────────────────────────

class TestGetCpuXml:
    def test_get_cpu_xml(self, http_client, host_plugin):
        """Get CPU baseline XML → should return valid XML."""
        rsp = http_client.post_async('/vm/get/cpu/xml', {})
        assert _ok(rsp), 'get cpu xml failed: %s' % getattr(rsp, 'error', '')
        assert rsp.cpuXml is not None, 'cpuXml should not be None'
        assert '<cpu' in rsp.cpuXml, 'cpuXml should contain <cpu element'
        assert rsp.cpuModelName is not None, 'cpuModelName should not be None'

    def test_compare_cpu_with_self(self, http_client, host_plugin):
        """Get CPU XML then compare with itself → should match."""
        rsp = http_client.post_async('/vm/get/cpu/xml', {})
        assert _ok(rsp)
        if not rsp.cpuXml:
            pytest.skip('no cpuXml returned')

        rsp2 = http_client.post_async('/vm/compare/cpu/function', {
            'cpuXml': rsp.cpuXml,
        })
        assert _ok(rsp2)
        # Comparing host baseline with itself should be compatible
        # match may be True or absent (handler only sets match=False on mismatch)
        assert getattr(rsp2, 'match', True) is not False

    def test_cpu_xml_has_features(self, http_client, host_plugin):
        """CPU XML should contain feature elements."""
        rsp = http_client.post_async('/vm/get/cpu/xml', {})
        assert _ok(rsp)
        if rsp.cpuXml:
            assert '<feature' in rsp.cpuXml, 'cpuXml should have feature elements'


# ──────────────────────────────────────────────────────────────────────
# 4. Virtualizer Info (QEMU/KVM version)
# ──────────────────────────────────────────────────────────────────────

class TestVirtualizerInfo:
    def test_get_virtualizer_info_host_only(self, http_client, host_plugin):
        """Get virtualizer info with no VM UUIDs → host info only."""
        rsp = http_client.post_async('/vm/getvirtualizerinfo', {
            'vmUuids': [],
        })
        assert _ok(rsp), 'get virtualizer info failed: %s' % getattr(rsp, 'error', '')
        assert rsp.hostInfo is not None, 'hostInfo should not be None'
        assert rsp.hostInfo.virtualizer == 'qemu-kvm'
        assert rsp.hostInfo.version is not None, 'version should not be None'

    def test_get_virtualizer_info_with_running_vm(self, http_client, host_plugin):
        """Get virtualizer info for a running VM → should have version."""
        # First find a running VM
        sync_rsp = http_client.post_async('/vm/vmsync', {})
        assert _ok(sync_rsp)
        states = sync_rsp.states.__dict__ if hasattr(sync_rsp.states, '__dict__') else {}
        running = [u for u, s in states.items() if s == 'Running']
        if not running:
            pytest.skip('no running VMs on host')

        rsp = http_client.post_async('/vm/getvirtualizerinfo', {
            'vmUuids': [running[0]],
        })
        assert _ok(rsp)
        assert rsp.hostInfo.version is not None
        assert len(rsp.vmInfoList) == 1
        vm_info = rsp.vmInfoList[0]
        assert vm_info.uuid == running[0]
        assert vm_info.virtualizer == 'qemu-kvm'
        assert vm_info.version is not None


