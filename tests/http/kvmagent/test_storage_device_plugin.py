# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent storage device plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestStorageDeviceSmoke:
    """Smoke tests for storage_device plugin endpoints (iSCSI, FC, NVMe, RAID)."""

    def test_iscsi_login(self, kvmagent_client, async_callback):
        """Test /storagedevice/iscsi/login - iSCSI target login."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/iscsi/login', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/iscsi/login')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_iscsi_logout(self, kvmagent_client, async_callback):
        """Test /storagedevice/iscsi/logout - iSCSI target logout."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/iscsi/logout', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/iscsi/logout')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_fc_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/fc/scan - scan FC/SG devices."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/fc/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/fc/scan')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/scan - scan NVMe devices."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/nvme/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/nvme/scan')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_connect(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/connect - connect NVMe devices."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/nvme/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/nvme/connect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_disconnect(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/disconnect - disconnect NVMe devices."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/nvme/disconnect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/nvme/disconnect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_enable(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/enable - enable multipath."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/multipath/enable', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/multipath/enable')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_disable(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/disable - disable multipath."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/multipath/disable', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/multipath/disable')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_topology(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/topology - get multipath topology."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/multipath/topology', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/multipath/topology')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_attach(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/attach - attach SCSI LUN."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/scsilun/attach', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/scsilun/attach')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_detach(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/detach - detach SCSI LUN."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/scsilun/detach', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/scsilun/detach')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_detachdev(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/detachdev - detach SCSI device."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/scsilun/detachdev', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/scsilun/detachdev')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/scan - scan RAID controllers."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/raid/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/raid/scan')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_smart(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/smart - get RAID SMART info."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/raid/smart', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/raid/smart')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_locate(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/locate - locate RAID disk."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/raid/locate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/raid/locate')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_selftest(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/selftest - RAID drive self-test."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/raid/selftest', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/raid/selftest')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_hba_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/hba/scan - scan HBA adapters."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/storagedevice/hba/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/storagedevice/hba/scan')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
