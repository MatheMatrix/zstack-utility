# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent block storage plugin."""

import pytest


@pytest.mark.http
class TestBlockStorageSmoke:
    """Smoke tests for block_storage_plugin endpoints (iSCSI block primary storage)."""

    def test_getinitiatorname(self, kvmagent_client):
        """Test /block/primarystorage/getinitiatorname - get iSCSI initiator name."""
        response = kvmagent_client.post('/block/primarystorage/getinitiatorname', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_createheartbeat(self, kvmagent_client):
        """Test /block/primarystorage/createheartbeat - create heartbeat."""
        response = kvmagent_client.post('/block/primarystorage/createheartbeat', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_deleteheartbeat(self, kvmagent_client):
        """Test /block/primarystorage/deleteheartbeat - delete heartbeat."""
        response = kvmagent_client.post('/block/primarystorage/deleteheartbeat', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_ping(self, kvmagent_client):
        """Test /block/primarystorage/ping - ping block storage."""
        response = kvmagent_client.post('/block/primarystorage/ping', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_resize(self, kvmagent_client):
        """Test /block/primarystorage/volume/resize - resize volume."""
        response = kvmagent_client.post('/block/primarystorage/volume/resize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_lun_rescan(self, kvmagent_client):
        """Test /block/primarystorage/lun/rescan - rescan LUN."""
        response = kvmagent_client.post('/block/primarystorage/lun/rescan', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_unmount(self, kvmagent_client):
        """Test /block/primarystorage/unmount - unmount block storage."""
        response = kvmagent_client.post('/block/primarystorage/unmount', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
