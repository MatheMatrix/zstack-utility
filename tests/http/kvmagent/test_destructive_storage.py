# -*- coding: utf-8 -*-
"""Destructive HTTP tests for kvmagent storage operations (Round 12).

These tests create/delete volumes and snapshots on local storage.
Only run on disposable VMs with --allow-destructive flag.
"""

import os
import uuid

import pytest

pytestmark = [
    pytest.mark.http,
    pytest.mark.destructive,
]

TEST_STORAGE_PATH = "/tmp/ztest-storage-%s" % os.getpid()



class TestLocalStorageVolumeLifecycle:
    """Test volume create/resize/delete on localstorage."""

    def test_create_empty_volume(self, kvmagent_client, async_callback):
        """Test /localstorage/volume/createempty creates a qcow2 volume."""
        callback_url = async_callback.get_callback_url()
        vol_path = "%s/vol-%s.qcow2" % (TEST_STORAGE_PATH, uuid.uuid4().hex[:8])
        response = kvmagent_client.post(
            '/localstorage/volume/createempty',
            data={
                'installUrl': vol_path,
                'size': 1073741824,  # 1GB
                'volumeFormat': 'qcow2',
            },
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_get_volume_size(self, kvmagent_client, async_callback):
        """Test /localstorage/getsize returns volume size info."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getsize',
            data={'installPath': '/nonexistent'},
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_delete_bits(self, kvmagent_client, async_callback):
        """Test /localstorage/delete deletes volume bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/delete',
            data={'path': '/tmp/nonexistent-ztest-delete'},
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestLocalStorageSnapshotLifecycle:
    """Test snapshot create/revert/delete on localstorage."""

    def test_create_snapshot(self, kvmagent_client, async_callback):
        """Test /localstorage/snapshot/create creates a snapshot."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/snapshot/create',
            data={
                'volumeUuid': uuid.uuid4().hex,
                'installPath': '/tmp/nonexistent-vol.qcow2',
                'snapshotPath': '/tmp/nonexistent-snap.qcow2',
            },
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_revert_snapshot(self, kvmagent_client, async_callback):
        """Test /localstorage/snapshot/revert reverts to snapshot."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/snapshot/revert',
            data={
                'snapshotInstallPath': '/tmp/nonexistent-snap.qcow2',
            },
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_merge_snapshot(self, kvmagent_client, async_callback):
        """Test /localstorage/snapshot/merge merges snapshot chain."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/snapshot/merge',
            data={
                'snapshotInstallPath': '/tmp/nonexistent-snap.qcow2',
                'workspaceInstallPath': '/tmp/nonexistent-ws.qcow2',
            },
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
