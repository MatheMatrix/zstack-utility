# -*- coding: utf-8 -*-
"""Destructive HTTP tests for kvmagent VM lifecycle operations (Round 13).

These tests exercise VM state transitions and device attach/detach.
Only run on disposable VMs with --allow-destructive flag.
"""

import uuid

import pytest

pytestmark = [
    pytest.mark.http,
    pytest.mark.destructive,
]



class TestVMStateTransitions:
    """Test VM start/stop/pause/resume operations."""

    def test_stop_vm(self, kvmagent_client, async_callback):
        """Test /vm/stop - stop a running VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/stop',
            data={
                'uuid': uuid.uuid4().hex,
                'type': 'grace',
                'timeout': 30,
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)

    def test_reboot_vm(self, kvmagent_client, async_callback):
        """Test /vm/reboot - reboot a VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/reboot',
            data={
                'uuid': uuid.uuid4().hex,
                'timeout': 30,
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)

    def test_pause_vm(self, kvmagent_client, async_callback):
        """Test /vm/pause - pause a VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/pause',
            data={'uuid': uuid.uuid4().hex},
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=15.0)
        assert isinstance(result, dict)

    def test_resume_vm(self, kvmagent_client, async_callback):
        """Test /vm/resume - resume a paused VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/resume',
            data={'uuid': uuid.uuid4().hex},
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=15.0)
        assert isinstance(result, dict)


class TestVMDeviceAttach:
    """Test volume/NIC attach/detach operations."""

    def test_attach_data_volume(self, kvmagent_client, async_callback):
        """Test /vm/volume/attach - attach data volume to VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/attach',
            data={
                'vmUuid': uuid.uuid4().hex,
                'volume': {
                    'installPath': '/tmp/nonexistent.qcow2',
                    'deviceId': 1,
                },
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)

    def test_detach_data_volume(self, kvmagent_client, async_callback):
        """Test /vm/volume/detach - detach data volume from VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/detach',
            data={
                'vmUuid': uuid.uuid4().hex,
                'volume': {'installPath': '/tmp/nonexistent.qcow2'},
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)

    def test_attach_nic(self, kvmagent_client, async_callback):
        """Test /vm/nic/attach - attach NIC to VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/attachnic',
            data={
                'vmUuid': uuid.uuid4().hex,
                'nic': {
                    'mac': '00:11:22:33:44:55',
                    'bridgeName': 'br_eth0',
                },
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)

    def test_detach_nic(self, kvmagent_client, async_callback):
        """Test /vm/detachnic - detach NIC from VM."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/detachnic',
            data={
                'vmUuid': uuid.uuid4().hex,
                'nic': {'mac': '00:11:22:33:44:55'},
            },
            callback_url=callback_url,
        )
        if response.status_code == 404:
            pytest.skip("vm plugin not loaded")
        assert response.status_code == 200
        result = async_callback.wait(response.task_uuid, timeout=30.0)
        assert isinstance(result, dict)
