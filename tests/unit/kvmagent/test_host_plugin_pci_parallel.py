# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnusedImport=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnannotatedClassAttribute=false, reportAny=false, reportAttributeAccessIssue=false
from __future__ import annotations
"""
Tests for parallel PCI/mdev device mapping in host_plugin (ZSTAC-83709).

Verifies that _collect_vm_mappings_parallel dispatches mapping queries
across a bounded thread pool, filters empty results, and isolates
per-VM failures.  Also verifies get_all_vm_{pci,mdev}_mappings flatten
results correctly.
"""
import concurrent.futures
import pytest
from unittest.mock import patch, MagicMock

from kvmagent.plugins import host_plugin


def _make_plugin():
    """Create a minimal HostPlugin instance for testing."""
    return host_plugin.HostPlugin.__new__(host_plugin.HostPlugin)


# ---------------------------------------------------------------------------
# _collect_vm_mappings_parallel
# ---------------------------------------------------------------------------

@pytest.mark.kvmagent
class TestCollectVmMappingsParallel:
    """Thread-pool dispatch, filtering, and error isolation."""

    def _run(self, uuids, mapping_side_effect=None, conn=None):
        """Helper: invoke _collect_vm_mappings_parallel with mocks.

        Args:
            uuids: list of VM UUID strings
            mapping_side_effect: side_effect for the mapping_func mock
            conn: optional mock libvirt connection; auto-created if None
        Returns:
            (result_list, mapping_func_mock)
        """
        plugin = _make_plugin()
        plugin.list_vm_uuids = MagicMock(return_value=uuids)

        mock_conn = conn or MagicMock()
        mock_singleton = MagicMock()
        mock_singleton.conn = mock_conn

        mapping_func = MagicMock(side_effect=mapping_side_effect)

        with patch.object(host_plugin, 'LibvirtSingleton', return_value=mock_singleton), \
             patch.object(host_plugin, 'log') as mock_log:
            mock_log.get_task_uuid.return_value = 'test-task-uuid'
            result = plugin._collect_vm_mappings_parallel(mapping_func)

        return result, mapping_func

    def test_empty_vm_list_returns_empty(self):
        result, mf = self._run(uuids=[])
        assert result == []
        mf.assert_not_called()

    def test_filters_out_empty_mappings(self):
        """VMs without passthrough return {} which is filtered by `if m`."""
        result, mf = self._run(
            uuids=['vm1', 'vm2', 'vm3'],
            mapping_side_effect=[
                {},
                {'0000:05:00.0': '0000:3b:00.0'},
                {},
            ],
        )
        assert len(result) == 1
        assert result[0] == {'0000:05:00.0': '0000:3b:00.0'}
        assert mf.call_count == 3

    def test_exception_in_one_vm_isolated(self):
        """Exception querying one VM must not block others."""
        mock_conn = MagicMock()
        domain2 = MagicMock()
        mock_conn.lookupByName.side_effect = [
            Exception("domain not found"),
            domain2,
        ]

        result, mf = self._run(
            uuids=['vm1', 'vm2'],
            mapping_side_effect=[{'k': 'v'}],
            conn=mock_conn,
        )
        assert len(result) == 1
        mf.assert_called_once_with(domain2)

    def test_none_domain_skipped(self):
        """lookupByName returning None should skip the VM."""
        mock_conn = MagicMock()
        mock_conn.lookupByName.return_value = None

        result, mf = self._run(
            uuids=['vm1'],
            conn=mock_conn,
        )
        assert result == []
        mf.assert_not_called()

    def test_all_vms_have_passthrough(self):
        """All VMs return mappings — all results collected."""
        result, mf = self._run(
            uuids=['vm1', 'vm2', 'vm3'],
            mapping_side_effect=[
                {'a1': 'h1'},
                {'a2': 'h2'},
                {'a3': 'h3'},
            ],
        )
        assert len(result) == 3

    def test_thread_pool_bounded_by_max_workers(self):
        """max_workers = min(len(uuids), _PCI_QUERY_MAX_WORKERS)."""
        plugin = _make_plugin()
        uuids = ['vm{}'.format(i) for i in range(50)]
        plugin.list_vm_uuids = MagicMock(return_value=uuids)

        mock_singleton = MagicMock()
        mock_singleton.conn = MagicMock()
        mapping_func = MagicMock(return_value={})

        with patch.object(host_plugin, 'LibvirtSingleton', return_value=mock_singleton), \
             patch.object(host_plugin, 'log') as mock_log, \
             patch('concurrent.futures.ThreadPoolExecutor', wraps=concurrent.futures.ThreadPoolExecutor) as mock_tpe:
            mock_log.get_task_uuid.return_value = None
            plugin._collect_vm_mappings_parallel(mapping_func)

            # _PCI_QUERY_MAX_WORKERS = 16, so 50 VMs → max_workers=16
            mock_tpe.assert_called_once_with(max_workers=host_plugin._PCI_QUERY_MAX_WORKERS)

    def test_small_vm_count_uses_vm_count_as_workers(self):
        """When VM count < _PCI_QUERY_MAX_WORKERS, use VM count."""
        plugin = _make_plugin()
        uuids = ['vm1', 'vm2', 'vm3']
        plugin.list_vm_uuids = MagicMock(return_value=uuids)

        mock_singleton = MagicMock()
        mock_singleton.conn = MagicMock()
        mapping_func = MagicMock(return_value={})

        with patch.object(host_plugin, 'LibvirtSingleton', return_value=mock_singleton), \
             patch.object(host_plugin, 'log') as mock_log, \
             patch('concurrent.futures.ThreadPoolExecutor', wraps=concurrent.futures.ThreadPoolExecutor) as mock_tpe:
            mock_log.get_task_uuid.return_value = None
            plugin._collect_vm_mappings_parallel(mapping_func)

            mock_tpe.assert_called_once_with(max_workers=3)


# ---------------------------------------------------------------------------
# get_all_vm_pci_mappings
# ---------------------------------------------------------------------------

@pytest.mark.kvmagent
class TestGetAllVmPciMappings:
    """Verify host→vm mapping flattening."""

    def test_flattens_per_vm_mappings(self):
        plugin = _make_plugin()
        per_vm = [
            {'vm_addr_1': 'host_addr_1', 'vm_addr_2': 'host_addr_2'},
            {'vm_addr_3': 'host_addr_3'},
        ]
        with patch.object(plugin, '_collect_vm_mappings_parallel', return_value=per_vm):
            result = plugin.get_all_vm_pci_mappings()

        assert result == {
            'host_addr_1': 'vm_addr_1',
            'host_addr_2': 'vm_addr_2',
            'host_addr_3': 'vm_addr_3',
        }

    def test_empty_parallel_result(self):
        plugin = _make_plugin()
        with patch.object(plugin, '_collect_vm_mappings_parallel', return_value=[]):
            result = plugin.get_all_vm_pci_mappings()
        assert result == {}


# ---------------------------------------------------------------------------
# get_all_vm_mdev_mappings
# ---------------------------------------------------------------------------

@pytest.mark.kvmagent
class TestGetAllVmMdevMappings:
    """Verify mdev mapping merging."""

    def test_merges_per_vm_mappings(self):
        plugin = _make_plugin()
        per_vm = [
            {'mdev_uuid_1': 'vm_addr_1'},
            {'mdev_uuid_2': 'vm_addr_2'},
        ]
        with patch.object(plugin, '_collect_vm_mappings_parallel', return_value=per_vm):
            result = plugin.get_all_vm_mdev_mappings()

        assert result == {
            'mdev_uuid_1': 'vm_addr_1',
            'mdev_uuid_2': 'vm_addr_2',
        }

    def test_empty_parallel_result(self):
        plugin = _make_plugin()
        with patch.object(plugin, '_collect_vm_mappings_parallel', return_value=[]):
            result = plugin.get_all_vm_mdev_mappings()
        assert result == {}
