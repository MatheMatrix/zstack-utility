"""
Unit tests for on-demand hugepage sizing in kvmagent.plugins.zbs_vhost_target.

vhost-user-blk forces the guest RAM onto preallocated shared hugepages, so every
vhost VM consumes hugepages = its memory. These tests cover the pure sizing math,
the domain-XML gating/parsing, and the free-based grow/shrink logic (sysfs + bash
mocked).
"""
import pytest
from unittest.mock import patch

from zstacklib.utils import http
from zstacklib.utils import jsonobject
from kvmagent.plugins import zbs_vhost_target as t
from kvmagent.plugins import zbs_storage_plugin


HP = t.HUGEPAGE_SIZE_BYTES


class TestMemToPages:
    def test_exact_multiple(self):
        assert t.mem_to_pages(300 * 1024 * 1024) == 150

    def test_rounds_up_partial_page(self):
        assert t.mem_to_pages(HP + 1) == 2

    def test_zero(self):
        assert t.mem_to_pages(0) == 0


class TestDomainVhostuserPresent:
    def test_detects_vhostuser_disk(self):
        xml = """<domain><devices>
          <disk type='vhostuser' device='disk'>
            <source type='unix' path='/var/tmp/vhost-sockets/zbs-vhost-x'/>
          </disk></devices></domain>"""
        assert t.domain_vhostuser_present(xml) is True

    def test_ignores_plain_disk(self):
        xml = """<domain><devices>
          <disk type='network' device='disk'><source name='cbd:pool/vol'/></disk>
          </devices></domain>"""
        assert t.domain_vhostuser_present(xml) is False

    def test_malformed_xml_is_not_vhost(self):
        assert t.domain_vhostuser_present("not xml <<<") is False


class TestDomainMemoryBytes:
    def test_unit_kib_default_zstack(self):
        xml = "<domain><memory unit='k'>307200</memory></domain>"
        assert t.domain_memory_bytes(xml) == 300 * 1024 * 1024

    def test_unit_mib(self):
        xml = "<domain><memory unit='MiB'>512</memory></domain>"
        assert t.domain_memory_bytes(xml) == 512 * 1024 * 1024

    def test_unit_bytes(self):
        xml = "<domain><memory unit='b'>1048576</memory></domain>"
        assert t.domain_memory_bytes(xml) == 1048576

    def test_no_unit_defaults_kib(self):
        xml = "<domain><memory>1024</memory></domain>"
        assert t.domain_memory_bytes(xml) == 1024 * 1024


class TestReadHugepageFree:
    # regression guard for the aarch64 bug: free count MUST come from the 2MB pool's own
    # sysfs, never /proc/meminfo (which reports only the kernel default size, 512MB on ARM64).
    def test_reads_pool_sysfs_not_meminfo(self):
        with patch('os.path.exists', return_value=True), \
             patch.object(t.bash, 'bash_o', return_value="100\n") as bo:
            assert t._read_hugepage_free() == 100
            called = " ".join(str(c) for c in bo.call_args_list)
            assert t.HUGEPAGE_FREE_PATH in called
            assert "meminfo" not in called

    def test_free_path_targets_2mb_pool(self):
        assert t.HUGEPAGE_FREE_PATH == t.HUGEPAGE_DIR + "/free_hugepages"
        assert "hugepages-2048kB" in t.HUGEPAGE_FREE_PATH

    def test_raises_when_pool_sysfs_absent(self):
        with patch('os.path.exists', return_value=False):
            with pytest.raises(Exception):
                t._read_hugepage_free()


class TestEnsureFreeHugepages:
    def test_noop_when_free_sufficient(self):
        with patch.object(t, '_read_hugepage_nr', return_value=768), \
             patch.object(t, '_read_hugepage_free', return_value=200), \
             patch.object(t.bash, 'bash_o') as bo:
            t.ensure_free_hugepages(150)
            assert not any('nr_hugepages' in str(c) for c in bo.call_args_list)

    def test_grows_total_by_deficit(self):
        reads = {'free': [71, 150]}
        with patch.object(t, '_read_hugepage_nr', return_value=256), \
             patch.object(t, '_read_hugepage_free', side_effect=lambda: reads['free'].pop(0)), \
             patch.object(t.bash, 'bash_o') as bo:
            t.ensure_free_hugepages(150)
            writes = [str(c) for c in bo.call_args_list if 'nr_hugepages' in str(c)]
            assert any('335' in w for w in writes), writes

    def test_raises_when_cannot_satisfy(self):
        with patch.object(t, '_read_hugepage_nr', return_value=256), \
             patch.object(t, '_read_hugepage_free', side_effect=[71, 90]), \
             patch.object(t.bash, 'bash_o'):
            with pytest.raises(Exception):
                t.ensure_free_hugepages(150)


class TestEnsure2mHugetlbfsMount:
    def test_reuses_existing_default_hugepages_when_it_is_2mb(self):
        with patch.object(t.bash, 'bash_o', return_value="/dev/hugepages rw,pagesize=2M\n"), \
             patch.object(t.bash, 'bash_errorout') as errorout:
            assert t.ensure_2m_hugetlbfs_mount() == "/dev/hugepages"
            errorout.assert_not_called()

    def test_mounts_2mb_hugetlbfs_when_absent(self):
        with patch.object(t.bash, 'bash_o', return_value=""), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs') as makedirs, \
             patch.object(t.bash, 'bash_r', return_value=1), \
             patch.object(t.bash, 'bash_errorout') as errorout:
            assert t.ensure_2m_hugetlbfs_mount() == t.DEFAULT_VHOST_TARGET_HUGEPAGE_DIR
            makedirs.assert_called_once_with(t.DEFAULT_VHOST_TARGET_HUGEPAGE_DIR)
            assert "pagesize=2M" in errorout.call_args[0][0]

    def test_reuses_existing_2mb_hugetlbfs_mount(self):
        with patch.object(t.bash, 'bash_o', return_value=""), \
             patch('os.path.exists', return_value=True), \
             patch.object(t.bash, 'bash_r', return_value=0), \
             patch.object(t.bash, 'bash_errorout') as errorout:
            assert t.ensure_2m_hugetlbfs_mount("/dev/hugepages2m") == "/dev/hugepages2m"
            errorout.assert_not_called()


class TestPrepareVhostTargetEnv:
    def test_ensures_2m_mount_and_free_hugepages(self):
        body = '{"hugepageNr":1024}'
        req = {http.REQUEST_BODY: body}
        with patch.object(t, 'ensure_docker'), \
             patch.object(t, 'ensure_2m_hugetlbfs_mount') as ensure_mount, \
             patch.object(t, 'ensure_free_hugepages') as ensure_free:
            out = zbs_storage_plugin.ZbsStoragePlugin().prepare_vhost_target_env(req)
            rsp = jsonobject.loads(out)
            assert rsp.success is True
            ensure_mount.assert_called_once_with()
            ensure_free.assert_called_once_with(1024)


class TestEnsureHugepagesForDomain:
    def test_vhost_domain_triggers_ensure(self):
        xml = """<domain><memory unit='k'>307200</memory><devices>
          <disk type='vhostuser'><source type='unix' path='/x'/></disk>
          </devices></domain>"""
        with patch.object(t, 'ensure_free_hugepages') as ef:
            t.ensure_hugepages_for_domain(xml)
            ef.assert_called_once_with(150)

    def test_non_vhost_domain_is_noop(self):
        xml = "<domain><memory unit='k'>307200</memory><devices></devices></domain>"
        with patch.object(t, 'ensure_free_hugepages') as ef:
            t.ensure_hugepages_for_domain(xml)
            ef.assert_not_called()


class TestReclaimHugepages:
    def test_shrinks_to_used_plus_slack(self):
        with patch.object(t, '_read_hugepage_nr', return_value=768), \
             patch.object(t, '_read_hugepage_free', return_value=433), \
             patch.object(t.bash, 'bash_o') as bo:
            t.reclaim_hugepages(slack=0)
            writes = [str(c) for c in bo.call_args_list if 'nr_hugepages' in str(c)]
            assert any('335' in w for w in writes), writes

    def test_noop_when_nothing_free_to_reclaim(self):
        with patch.object(t, '_read_hugepage_nr', return_value=335), \
             patch.object(t, '_read_hugepage_free', return_value=0), \
             patch.object(t.bash, 'bash_o') as bo:
            t.reclaim_hugepages(slack=0)
            assert not any('nr_hugepages' in str(c) for c in bo.call_args_list)
