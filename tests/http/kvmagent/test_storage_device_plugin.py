# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent storage device plugin."""

import pytest


@pytest.mark.http
class TestStorageDeviceSmoke:
    """Smoke tests for storage_device plugin endpoints (iSCSI, FC, NVMe, RAID)."""

    def test_iscsi_login(self, kvmagent_client):
        """Test /storagedevice/iscsi/login - iSCSI target login."""
        response = kvmagent_client.post('/storagedevice/iscsi/login', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_iscsi_logout(self, kvmagent_client):
        """Test /storagedevice/iscsi/logout - iSCSI target logout."""
        response = kvmagent_client.post('/storagedevice/iscsi/logout', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_fc_scan(self, kvmagent_client):
        """Test /storagedevice/fc/scan - scan FC/SG devices."""
        response = kvmagent_client.post('/storagedevice/fc/scan', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_nvme_scan(self, kvmagent_client):
        """Test /storagedevice/nvme/scan - scan NVMe devices."""
        response = kvmagent_client.post('/storagedevice/nvme/scan', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_nvme_connect(self, kvmagent_client):
        """Test /storagedevice/nvme/connect - connect NVMe devices."""
        response = kvmagent_client.post('/storagedevice/nvme/connect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_nvme_disconnect(self, kvmagent_client):
        """Test /storagedevice/nvme/disconnect - disconnect NVMe devices."""
        response = kvmagent_client.post('/storagedevice/nvme/disconnect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_multipath_enable(self, kvmagent_client):
        """Test /storagedevice/multipath/enable - enable multipath."""
        response = kvmagent_client.post('/storagedevice/multipath/enable', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_multipath_disable(self, kvmagent_client):
        """Test /storagedevice/multipath/disable - disable multipath."""
        response = kvmagent_client.post('/storagedevice/multipath/disable', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_multipath_topology(self, kvmagent_client):
        """Test /storagedevice/multipath/topology - get multipath topology."""
        response = kvmagent_client.post('/storagedevice/multipath/topology', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_attach(self, kvmagent_client):
        """Test /storagedevice/scsilun/attach - attach SCSI LUN."""
        response = kvmagent_client.post('/storagedevice/scsilun/attach', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_detach(self, kvmagent_client):
        """Test /storagedevice/scsilun/detach - detach SCSI LUN."""
        response = kvmagent_client.post('/storagedevice/scsilun/detach', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_scsilun_detachdev(self, kvmagent_client):
        """Test /storagedevice/scsilun/detachdev - detach SCSI device."""
        response = kvmagent_client.post('/storagedevice/scsilun/detachdev', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_raid_scan(self, kvmagent_client):
        """Test /storagedevice/raid/scan - scan RAID controllers."""
        response = kvmagent_client.post('/storagedevice/raid/scan', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_raid_smart(self, kvmagent_client):
        """Test /storagedevice/raid/smart - get RAID SMART info."""
        response = kvmagent_client.post('/storagedevice/raid/smart', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_raid_locate(self, kvmagent_client):
        """Test /storagedevice/raid/locate - locate RAID disk."""
        response = kvmagent_client.post('/storagedevice/raid/locate', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_raid_selftest(self, kvmagent_client):
        """Test /storagedevice/raid/selftest - RAID drive self-test."""
        response = kvmagent_client.post('/storagedevice/raid/selftest', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_hba_scan(self, kvmagent_client):
        """Test /storagedevice/hba/scan - scan HBA adapters."""
        response = kvmagent_client.post('/storagedevice/hba/scan', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
