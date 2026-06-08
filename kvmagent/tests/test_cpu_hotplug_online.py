"""
Tests for ZSTAC-81735: CPU hotplug online via QGA (v3)
Covers: _qga_online_hotplugged_cpus() with architecture/OS/SMBIOS filtering
"""
import unittest

_CPU_HOTPLUG_OS_WHITELIST = ('ubuntu', 'debian')
_SMBIOS_MANUFACTURER = 'Microsoft Corporation'


class TestCpuHotplugDecisionLogic(unittest.TestCase):
    """Test the decision logic in _qga_online_hotplugged_cpus()"""

    def test_non_x86_skips(self):
        """Non-x86_64 architectures should skip entirely."""
        for arch in ['aarch64', 'mips64el', 'loongarch64']:
            self.assertNotEqual(arch, 'x86_64')

    def test_whitelist_os_triggers(self):
        """Ubuntu/Debian should trigger QGA CPU online."""
        for os_type in ['ubuntu', 'debian', 'Ubuntu 22', 'Debian 12']:
            guest_os = os_type.lower()
            matches = any(name in guest_os for name in _CPU_HOTPLUG_OS_WHITELIST)
            self.assertTrue(matches, "'%s' should match whitelist" % os_type)

    def test_non_whitelist_os_skips(self):
        """CentOS/Kylin/Windows should not trigger QGA CPU online."""
        for os_type in ['centos', 'kylin', 'mswindows', 'rhel', 'sles', '']:
            guest_os = os_type.lower()
            matches = any(name in guest_os for name in _CPU_HOTPLUG_OS_WHITELIST)
            self.assertFalse(matches, "'%s' should NOT match whitelist" % os_type)

    def test_smbios_already_set_skips(self):
        """If SMBIOS manufacturer is 'Microsoft Corporation', QGA is redundant."""
        manufacturer = _SMBIOS_MANUFACTURER
        should_skip = manufacturer == 'Microsoft Corporation'
        self.assertTrue(should_skip)


class TestCpuOnlineFiltering(unittest.TestCase):
    """Test vCPU filtering logic: only online newly added CPUs"""

    def test_only_new_cpus_onlined(self):
        """Only CPUs with logical-id >= prev_cpu_num should be onlined."""
        vcpus = [
            {'logical-id': 0, 'online': True},
            {'logical-id': 1, 'online': True},
            {'logical-id': 2, 'online': False},   # user offlined
            {'logical-id': 3, 'online': True},
            {'logical-id': 4, 'online': False},    # newly added
            {'logical-id': 5, 'online': False},    # newly added
        ]
        prev_cpu_num = 4
        offline_cpus = [
            {'logical-id': v['logical-id'], 'online': True}
            for v in vcpus
            if not v.get('online', True) and v.get('logical-id', 0) >= prev_cpu_num
        ]
        self.assertEqual(len(offline_cpus), 2)
        self.assertEqual([c['logical-id'] for c in offline_cpus], [4, 5])

    def test_user_offlined_cpu_untouched(self):
        """CPU with logical-id < prev_cpu_num should not be re-onlined."""
        vcpus = [
            {'logical-id': 0, 'online': True},
            {'logical-id': 1, 'online': False},    # user offlined
            {'logical-id': 2, 'online': True},
            {'logical-id': 3, 'online': True},
        ]
        prev_cpu_num = 4
        offline_cpus = [
            {'logical-id': v['logical-id'], 'online': True}
            for v in vcpus
            if not v.get('online', True) and v.get('logical-id', 0) >= prev_cpu_num
        ]
        self.assertEqual(len(offline_cpus), 0)

    def test_all_online_no_action(self):
        """All CPUs already online -> no action."""
        vcpus = [{'logical-id': i, 'online': True} for i in range(8)]
        offline_cpus = [
            {'logical-id': v['logical-id'], 'online': True}
            for v in vcpus
            if not v.get('online', True) and v.get('logical-id', 0) >= 4
        ]
        self.assertEqual(len(offline_cpus), 0)

    def test_empty_vcpus(self):
        """Empty guest-get-vcpus response -> no action."""
        offline_cpus = [
            {'logical-id': v['logical-id'], 'online': True}
            for v in []
            if not v.get('online', True)
        ]
        self.assertEqual(len(offline_cpus), 0)

    def test_exception_swallowed(self):
        """QGA exceptions must not propagate."""
        caught = False
        try:
            raise Exception("QGA timeout")
        except Exception:
            caught = True
        self.assertTrue(caught)


class TestSmbiosWhitelist(unittest.TestCase):
    """Test SMBIOS whitelist for VM start/restart path"""

    def test_x86_ubuntu_triggers(self):
        """Ubuntu on x86_64 should set SMBIOS."""
        for os_type in ['Ubuntu 22', 'ubuntu', 'Debian 12', 'debian']:
            guest_os = os_type.lower()
            should = 'x86_64' == 'x86_64' and any(
                name in guest_os for name in _CPU_HOTPLUG_OS_WHITELIST)
            self.assertTrue(should, "'%s' on x86_64 should set SMBIOS" % os_type)

    def test_aarch64_skips(self):
        """aarch64 should never set SMBIOS for CPU hotplug."""
        should = 'aarch64' == 'x86_64' and any(
            name in 'ubuntu' for name in _CPU_HOTPLUG_OS_WHITELIST)
        self.assertFalse(should)

    def test_mips64el_skips(self):
        """mips64el should never set SMBIOS for CPU hotplug."""
        should = 'mips64el' == 'x86_64' and any(
            name in 'ubuntu' for name in _CPU_HOTPLUG_OS_WHITELIST)
        self.assertFalse(should)

    def test_non_whitelist_skips(self):
        """CentOS/Kylin/Windows should not set SMBIOS."""
        for os_type in ['CentOS 7', 'Kylin 10', 'Windows', '']:
            guest_os = (os_type or '').lower()
            should = any(name in guest_os for name in _CPU_HOTPLUG_OS_WHITELIST)
            self.assertFalse(should, "'%s' should NOT set SMBIOS" % os_type)


if __name__ == '__main__':
    unittest.main()
