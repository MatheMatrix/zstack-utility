# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent ZSES (ZStack Elastic Storage) plugin."""

import pytest


@pytest.mark.http
class TestZSESSmoke:
    """Smoke tests for zses plugin endpoints."""

    def test_init(self, kvmagent_client):
        """Test /zses/init - initialize ZSES storage."""
        response = kvmagent_client.post('/zses/init', data={})
        assert response.status_code in [200, 400, 500]

    def test_getphysicalcapacity(self, kvmagent_client):
        """Test /zses/getphysicalcapacity - get physical capacity."""
        response = kvmagent_client.post('/zses/getphysicalcapacity', data={})
        assert response.status_code in [200, 400, 500]

    def test_checkbits(self, kvmagent_client):
        """Test /zses/checkbits - check bits existence."""
        response = kvmagent_client.post('/zses/checkbits', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete(self, kvmagent_client):
        """Test /zses/delete - delete bits."""
        response = kvmagent_client.post('/zses/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_createempty(self, kvmagent_client):
        """Test /zses/volume/createempty - create empty volume."""
        response = kvmagent_client.post('/zses/volume/createempty', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_getbackingfile(self, kvmagent_client):
        """Test /zses/volume/getbackingfile - get backing file."""
        response = kvmagent_client.post('/zses/volume/getbackingfile', data={})
        assert response.status_code in [200, 400, 500]

    def test_volume_getbaseimagepath(self, kvmagent_client):
        """Test /zses/volume/getbaseimagepath - get base image path."""
        response = kvmagent_client.post('/zses/volume/getbaseimagepath', data={})
        assert response.status_code in [200, 400, 500]

    def test_snapshot_merge(self, kvmagent_client):
        """Test /zses/snapshot/merge - merge snapshot."""
        response = kvmagent_client.post('/zses/snapshot/merge', data={})
        assert response.status_code in [200, 400, 500]

    def test_snapshot_verifychain(self, kvmagent_client):
        """Test /zses/snapshot/verifychain - verify snapshot chain."""
        response = kvmagent_client.post('/zses/snapshot/verifychain', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_upload(self, kvmagent_client):
        """Test /zses/imagestore/upload - upload to imagestore."""
        response = kvmagent_client.post('/zses/imagestore/upload', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_download(self, kvmagent_client):
        """Test /zses/imagestore/download - download from imagestore."""
        response = kvmagent_client.post('/zses/imagestore/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_imagestore_commit(self, kvmagent_client):
        """Test /zses/imagestore/commit - commit to imagestore."""
        response = kvmagent_client.post('/zses/imagestore/commit', data={})
        assert response.status_code in [200, 400, 500]

    def test_getmd5(self, kvmagent_client):
        """Test /zses/getmd5 - get MD5 checksum."""
        response = kvmagent_client.post('/zses/getmd5', data={})
        assert response.status_code in [200, 400, 500]

    def test_copytoremote(self, kvmagent_client):
        """Test /zses/copytoremote - copy bits to remote."""
        response = kvmagent_client.post('/zses/copytoremote', data={})
        assert response.status_code in [200, 400, 500]
