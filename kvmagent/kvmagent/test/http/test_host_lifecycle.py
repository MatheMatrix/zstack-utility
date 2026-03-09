# -*- coding: utf-8 -*-
"""Lifecycle tests for HostPlugin against real kvmagent.

Safe read-only operations: echo → ping → fact → capacity → check file.
No destructive operations (reboot, shutdown, password change).
"""
import uuid
import pytest

REQUEST_BODY = 'body'

pytestmark = pytest.mark.skipif("not config.getoption('--direct-host')",
                                reason='lifecycle tests require real kvmagent')


def _ok(rsp):
    """Check response is successful (field may be absent/None on success)."""
    return getattr(rsp, 'success', True) is not False


# ──────────────────────────────────────────────────────────────────────
# 1. Echo (sync, smoke test)
# ──────────────────────────────────────────────────────────────────────

class TestHostEcho:
    def test_echo(self, http_client, host_plugin):
        """Echo is the simplest handler — returns empty string."""
        rsp = http_client.post_sync('/host/echo', {})
        # echo returns empty string, parsed as empty object
        assert rsp is not None


# ──────────────────────────────────────────────────────────────────────
# 2. Ping
# ──────────────────────────────────────────────────────────────────────

class TestHostPing:
    def test_ping_returns_host_uuid(self, http_client, host_plugin):
        """Ping should return the hostUuid set during connect."""
        rsp = http_client.post_async('/host/ping', {})
        assert _ok(rsp)
        # hostUuid is set during /host/connect bootstrap
        assert rsp.hostUuid is not None, 'hostUuid should not be None after connect'

    def test_ping_returns_version(self, http_client, host_plugin):
        """Ping should return the kvmagent version."""
        rsp = http_client.post_async('/host/ping', {})
        assert _ok(rsp)
        # version may come from connect or from file
        assert rsp.version is not None, 'version should be available'


# ──────────────────────────────────────────────────────────────────────
# 3. Host Facts
# ──────────────────────────────────────────────────────────────────────

class TestHostFact:
    def test_fact_returns_os_info(self, http_client, host_plugin):
        """Fact should return OS distribution and version."""
        rsp = http_client.post_async('/host/fact', {})
        assert _ok(rsp)
        assert rsp.osDistribution is not None, 'osDistribution missing'
        assert rsp.osVersion is not None, 'osVersion missing'
        assert rsp.cpuArchitecture is not None, 'cpuArchitecture missing'

    def test_fact_returns_qemu_info(self, http_client, host_plugin):
        """Fact should return qemu and libvirt versions."""
        rsp = http_client.post_async('/host/fact', {})
        assert _ok(rsp)
        assert rsp.qemuImgVersion is not None, 'qemuImgVersion missing'
        assert rsp.libvirtVersion is not None, 'libvirtVersion missing'

    def test_fact_returns_ip_addresses(self, http_client, host_plugin):
        """Fact should return at least one IPv4 address."""
        rsp = http_client.post_async('/host/fact', {})
        assert _ok(rsp)
        assert rsp.ipAddresses is not None
        assert len(rsp.ipAddresses) > 0, 'should have at least one IP'

    def test_fact_returns_hardware_info(self, http_client, host_plugin):
        """Fact should return system serial number and product name."""
        rsp = http_client.post_async('/host/fact', {})
        assert _ok(rsp)
        # These come from dmidecode — may be 'unknown' but should not be None
        assert rsp.systemSerialNumber is not None
        assert rsp.systemProductName is not None


# ──────────────────────────────────────────────────────────────────────
# 4. Capacity
# ──────────────────────────────────────────────────────────────────────

class TestHostCapacity:
    def test_capacity_returns_cpu_info(self, http_client, host_plugin):
        """Capacity should return CPU count and speed."""
        rsp = http_client.post_async('/host/capacity', {})
        assert _ok(rsp)
        assert rsp.cpuNum > 0, 'cpuNum should be > 0'
        assert rsp.cpuSpeed > 0, 'cpuSpeed should be > 0'
        assert rsp.cpuSockets > 0, 'cpuSockets should be > 0'

    def test_capacity_returns_memory_info(self, http_client, host_plugin):
        """Capacity should return total memory."""
        rsp = http_client.post_async('/host/capacity', {})
        assert _ok(rsp)
        assert rsp.totalMemory > 0, 'totalMemory should be > 0'
        # usedMemory can be 0 if no VMs running
        assert rsp.usedMemory >= 0


# ──────────────────────────────────────────────────────────────────────
# 5. Check File on Host
# ──────────────────────────────────────────────────────────────────────

class TestCheckFileOnHost:
    def test_check_existing_file(self, http_client, host_plugin):
        """Check a file that definitely exists → should be in existPaths."""
        rsp = http_client.post_async('/host/checkfile', {
            'paths': ['/etc/hosts'],
            'md5Return': False,
        })
        assert _ok(rsp)
        # existPaths is a JsonObject — use hasattr for key lookup
        assert hasattr(rsp.existPaths, '/etc/hosts'), 'existPaths should contain /etc/hosts'

    def test_check_existing_file_with_md5(self, http_client, host_plugin):
        """Check file with MD5 → existPaths should contain non-empty hash."""
        rsp = http_client.post_async('/host/checkfile', {
            'paths': ['/etc/hosts'],
            'md5Return': True,
        })
        assert _ok(rsp)
        assert hasattr(rsp.existPaths, '/etc/hosts')
        md5 = getattr(rsp.existPaths, '/etc/hosts')
        assert len(md5) == 32, 'MD5 hash should be 32 hex chars, got: %s' % md5

    def test_check_nonexistent_file(self, http_client, host_plugin):
        """Check a file that doesn't exist → should NOT be in existPaths."""
        rsp = http_client.post_async('/host/checkfile', {
            'paths': ['/nonexistent/file/that/does/not/exist.txt'],
            'md5Return': False,
        })
        assert _ok(rsp)
        paths = rsp.existPaths.__dict__ if hasattr(rsp.existPaths, '__dict__') else {}
        assert '/nonexistent/file/that/does/not/exist.txt' not in paths

    def test_check_mixed_files(self, http_client, host_plugin):
        """Check mix of existing and nonexistent files."""
        rsp = http_client.post_async('/host/checkfile', {
            'paths': ['/etc/hosts', '/nonexistent/xyz', '/etc/hostname'],
            'md5Return': False,
        })
        assert _ok(rsp)
        paths = rsp.existPaths.__dict__ if hasattr(rsp.existPaths, '__dict__') else {}
        assert '/etc/hosts' in paths
        assert '/nonexistent/xyz' not in paths


# ──────────────────────────────────────────────────────────────────────
# 6. NUMA Topology
# ──────────────────────────────────────────────────────────────────────

class TestNumaTopology:
    def test_get_numa_topology(self, http_client, host_plugin):
        """Get NUMA topology → should return node info."""
        rsp = http_client.post_async('/numa/topology', {})
        assert _ok(rsp), 'get numa topology failed: %s' % getattr(rsp, 'error', '')


# ──────────────────────────────────────────────────────────────────────
# 7. Physical Memory Facts
# ──────────────────────────────────────────────────────────────────────

class TestPhysicalMemoryFacts:
    def test_get_physical_memory_facts(self, http_client, host_plugin):
        """Get physical memory DIMM info from dmidecode."""
        rsp = http_client.post_async('/host/physicalmemoryfacts', {})
        assert _ok(rsp), 'get memory facts failed: %s' % getattr(rsp, 'error', '')
        assert rsp.physicalMemoryFacts is not None
        # Server should have at least one DIMM installed
        assert len(rsp.physicalMemoryFacts) > 0, 'should have at least one DIMM'
        dimm = rsp.physicalMemoryFacts[0]
        assert dimm.size is not None, 'DIMM size should be set'

    def test_dimm_has_required_fields(self, http_client, host_plugin):
        """Each DIMM should have manufacturer, type, serial number."""
        rsp = http_client.post_async('/host/physicalmemoryfacts', {})
        assert _ok(rsp)
        if not rsp.physicalMemoryFacts:
            pytest.skip('no DIMM info')
        dimm = rsp.physicalMemoryFacts[0]
        assert dimm.manufacturer is not None
        assert dimm.type is not None
        assert dimm.serialNumber is not None


# ──────────────────────────────────────────────────────────────────────
# 8. Device Capacity
# ──────────────────────────────────────────────────────────────────────

class TestDevCapacity:
    def test_get_dev_capacity_root(self, http_client, host_plugin):
        """Get device capacity for root filesystem."""
        rsp = http_client.post_async('/host/dev/capacity', {
            'dirPath': '/',
        })
        assert _ok(rsp), 'get dev capacity failed: %s' % getattr(rsp, 'error', '')
        assert rsp.totalSize > 0
        assert rsp.availableSize > 0
        assert rsp.totalSize >= rsp.availableSize

    def test_get_dev_capacity_zstack_ps(self, http_client, host_plugin):
        """Get device capacity for /zstack_ps if it exists."""
        ssh = http_client._ssh_run
        rc, out, _ = ssh('test -d /zstack_ps && echo yes || echo no')
        if out.strip() != 'yes':
            pytest.skip('/zstack_ps does not exist')

        rsp = http_client.post_async('/host/dev/capacity', {
            'dirPath': '/zstack_ps',
        })
        assert _ok(rsp)
        assert rsp.totalSize > 0
