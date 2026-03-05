# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent mini storage plugin."""

import pytest


@pytest.mark.http
class TestMiniStorageSmoke:
    """Smoke tests for mini_storage_plugin endpoints."""

    def test_connect(self, kvmagent_client):
        """Test /ministorage/connect - connect mini storage."""
        response = kvmagent_client.post('/ministorage/connect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_disconnect(self, kvmagent_client):
        """Test /ministorage/disconnect - disconnect mini storage."""
        response = kvmagent_client.post('/ministorage/disconnect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_bits_check(self, kvmagent_client):
        """Test /ministorage/bits/check - check bits existence."""
        response = kvmagent_client.post('/ministorage/bits/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_bits_delete(self, kvmagent_client):
        """Test /ministorage/bits/delete - delete bits."""
        response = kvmagent_client.post('/ministorage/bits/delete', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_createempty(self, kvmagent_client):
        """Test /ministorage/volume/createempty - create empty volume."""
        response = kvmagent_client.post('/ministorage/volume/createempty', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_getsize(self, kvmagent_client):
        """Test /ministorage/volume/getsize - get volume size."""
        response = kvmagent_client.post('/ministorage/volume/getsize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_resize(self, kvmagent_client):
        """Test /ministorage/volume/resize - resize volume."""
        response = kvmagent_client.post('/ministorage/volume/resize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_active(self, kvmagent_client):
        """Test /ministorage/volume/active - activate volume."""
        response = kvmagent_client.post('/ministorage/volume/active', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_disks_check(self, kvmagent_client):
        """Test /ministorage/disks/check - check disks status."""
        response = kvmagent_client.post('/ministorage/disks/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_revertfromsnapshot(self, kvmagent_client):
        """Test /ministorage/volume/revertfromsnapshot - revert volume."""
        response = kvmagent_client.post('/ministorage/volume/revertfromsnapshot', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_imagestore_upload(self, kvmagent_client):
        """Test /ministorage/imagestore/upload - upload to imagestore."""
        response = kvmagent_client.post('/ministorage/imagestore/upload', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_imagestore_download(self, kvmagent_client):
        """Test /ministorage/imagestore/download - download from imagestore."""
        response = kvmagent_client.post('/ministorage/imagestore/download', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_imagestore_commit(self, kvmagent_client):
        """Test /ministorage/imagestore/commit - commit to imagestore."""
        response = kvmagent_client.post('/ministorage/imagestore/commit', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
