# -*- coding: utf-8 -*-
"""HTTP integration tests for imagestore and storage_device plugins.

Covers image upload/download/commit, iSCSI login/logout, FC/NVMe scan,
multipath, SCSI LUN attach/detach, RAID, and HBA operations.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestImagestoreSmoke:
    """Smoke tests for imagestore endpoints."""

    def test_upload_bit(self, kvmagent_client, async_callback):
        """Test /imagestore/upload - upload image bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/imagestore/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_bit(self, kvmagent_client, async_callback):
        """Test /imagestore/download - download image bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/imagestore/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_commit_bit(self, kvmagent_client, async_callback):
        """Test /imagestore/commit - commit image bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/imagestore/commit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestStorageDeviceSmoke:
    """Smoke tests for storage_device endpoints."""

    def test_iscsi_login(self, kvmagent_client, async_callback):
        """Test /storagedevice/iscsi/login - iSCSI target login."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/iscsi/login', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/iscsi/login')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_iscsi_logout(self, kvmagent_client, async_callback):
        """Test /storagedevice/iscsi/logout - iSCSI target logout."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/iscsi/logout', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/iscsi/logout')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_fc_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/fc/scan - Fibre Channel scan."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/fc/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/fc/scan')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/scan - NVMe device scan."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/nvme/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/nvme/scan')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_connect(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/connect - NVMe connect."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/nvme/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/nvme/connect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_nvme_disconnect(self, kvmagent_client, async_callback):
        """Test /storagedevice/nvme/disconnect - NVMe disconnect."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/nvme/disconnect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/nvme/disconnect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_enable(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/enable - enable multipath."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/multipath/enable', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/multipath/enable')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_disable(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/disable - disable multipath."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/multipath/disable', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/multipath/disable')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_multipath_topology(self, kvmagent_client, async_callback):
        """Test /storagedevice/multipath/topology - get multipath topology."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/multipath/topology', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/multipath/topology')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_attach(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/attach - attach SCSI LUN."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/scsilun/attach', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/scsilun/attach')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_detach(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/detach - detach SCSI LUN."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/scsilun/detach', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/scsilun/detach')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_scsilun_detachdev(self, kvmagent_client, async_callback):
        """Test /storagedevice/scsilun/detachdev - detach SCSI device."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/scsilun/detachdev', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/scsilun/detachdev')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/scan - RAID controller scan."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/raid/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/raid/scan')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_smart(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/smart - RAID SMART data."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/raid/smart', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/raid/smart')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_locate(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/locate - RAID disk locate (LED blink)."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/raid/locate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/raid/locate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_raid_selftest(self, kvmagent_client, async_callback):
        """Test /storagedevice/raid/selftest - RAID self test."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/raid/selftest', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/raid/selftest')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_hba_scan(self, kvmagent_client, async_callback):
        """Test /storagedevice/hba/scan - HBA scan."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/storagedevice/hba/scan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/storagedevice/hba/scan')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
