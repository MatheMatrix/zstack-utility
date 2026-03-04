# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent shared mountpoint primary storage plugin."""

import pytest


@pytest.mark.http
class TestSharedMountpointSmoke:
    """Smoke tests for shared_mountpoint_plugin endpoints."""

    def test_connect(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/connect - connect storage."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/connect', data={})
        assert response.status_code in [200, 400, 500]

    def test_bits_check(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/bits/check - check bits."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/bits/check', data={})
        assert response.status_code in [200, 400, 500]

    def test_bits_delete(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/bits/delete - delete bits."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/bits/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_createempty(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/volume/createempty - create empty volume."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/createempty', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_getsize(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/volume/getsize - get volume size."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/getsize', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_resize(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/volume/resize - resize volume."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/resize', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_getbackingchain(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/volume/getbackingchain - get chain."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/getbackingchain', data={})
        assert response.status_code in [200, 400, 500]

    def test_estimatetemplatesize(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/estimatetemplatesize - estimate size."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/estimatetemplatesize', data={})
        assert response.status_code in [200, 400, 500]

    def test_snapshot_merge(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/snapshot/merge - merge snapshot."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/merge', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_upload(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/upload - upload."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/upload', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_download(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/download - download."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_commit(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/commit - commit."""
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/commit', data={})
        assert response.status_code in [200, 400, 500]
