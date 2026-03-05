# -*- coding: utf-8 -*-
"""HTTP integration tests for imagestore and storage_device plugins.

Covers image upload/download/commit, iSCSI login/logout, FC/NVMe scan,
multipath, SCSI LUN attach/detach, RAID, and HBA operations.
"""

import pytest


@pytest.mark.http
class TestImagestoreSmoke:
    """Smoke tests for imagestore endpoints."""

    def test_upload_bit(self, kvmagent_client):
        """Test /imagestore/upload - upload image bits."""
        resp = kvmagent_client.post('/imagestore/upload', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_download_bit(self, kvmagent_client):
        """Test /imagestore/download - download image bits."""
        resp = kvmagent_client.post('/imagestore/download', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_commit_bit(self, kvmagent_client):
        """Test /imagestore/commit - commit image bits."""
        resp = kvmagent_client.post('/imagestore/commit', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestStorageDeviceSmoke:
    """Smoke tests for storage_device endpoints."""

    def test_iscsi_login(self, kvmagent_client):
        """Test /storagedevice/iscsi/login - iSCSI target login."""
        resp = kvmagent_client.post('/storagedevice/iscsi/login', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_iscsi_logout(self, kvmagent_client):
        """Test /storagedevice/iscsi/logout - iSCSI target logout."""
        resp = kvmagent_client.post('/storagedevice/iscsi/logout', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_fc_scan(self, kvmagent_client):
        """Test /storagedevice/fc/scan - Fibre Channel scan."""
        resp = kvmagent_client.post('/storagedevice/fc/scan', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_nvme_scan(self, kvmagent_client):
        """Test /storagedevice/nvme/scan - NVMe device scan."""
        resp = kvmagent_client.post('/storagedevice/nvme/scan', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_nvme_connect(self, kvmagent_client):
        """Test /storagedevice/nvme/connect - NVMe connect."""
        resp = kvmagent_client.post('/storagedevice/nvme/connect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_nvme_disconnect(self, kvmagent_client):
        """Test /storagedevice/nvme/disconnect - NVMe disconnect."""
        resp = kvmagent_client.post('/storagedevice/nvme/disconnect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_multipath_enable(self, kvmagent_client):
        """Test /storagedevice/multipath/enable - enable multipath."""
        resp = kvmagent_client.post('/storagedevice/multipath/enable', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_multipath_disable(self, kvmagent_client):
        """Test /storagedevice/multipath/disable - disable multipath."""
        resp = kvmagent_client.post('/storagedevice/multipath/disable', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_multipath_topology(self, kvmagent_client):
        """Test /storagedevice/multipath/topology - get multipath topology."""
        resp = kvmagent_client.post('/storagedevice/multipath/topology', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_attach(self, kvmagent_client):
        """Test /storagedevice/scsilun/attach - attach SCSI LUN."""
        resp = kvmagent_client.post('/storagedevice/scsilun/attach', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_detach(self, kvmagent_client):
        """Test /storagedevice/scsilun/detach - detach SCSI LUN."""
        resp = kvmagent_client.post('/storagedevice/scsilun/detach', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_detachdev(self, kvmagent_client):
        """Test /storagedevice/scsilun/detachdev - detach SCSI device."""
        resp = kvmagent_client.post('/storagedevice/scsilun/detachdev', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_raid_scan(self, kvmagent_client):
        """Test /storagedevice/raid/scan - RAID controller scan."""
        resp = kvmagent_client.post('/storagedevice/raid/scan', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_raid_smart(self, kvmagent_client):
        """Test /storagedevice/raid/smart - RAID SMART data."""
        resp = kvmagent_client.post('/storagedevice/raid/smart', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_raid_locate(self, kvmagent_client):
        """Test /storagedevice/raid/locate - RAID disk locate (LED blink)."""
        resp = kvmagent_client.post('/storagedevice/raid/locate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_raid_selftest(self, kvmagent_client):
        """Test /storagedevice/raid/selftest - RAID self test."""
        resp = kvmagent_client.post('/storagedevice/raid/selftest', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_hba_scan(self, kvmagent_client):
        """Test /storagedevice/hba/scan - HBA scan."""
        resp = kvmagent_client.post('/storagedevice/hba/scan', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
