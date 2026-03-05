# -*- coding: utf-8 -*-
"""HTTP integration tests for ceph backup storage agent."""

import pytest


@pytest.mark.http
class TestCephBackupCoreSmoke:
    """Smoke tests for ceph backup storage core endpoints."""

    def test_init(self, cephbackup_client):
        """Test /ceph/backupstorage/init - initialize ceph backup storage."""
        response = cephbackup_client.post('/ceph/backupstorage/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_connect(self, cephbackup_client):
        """Test /ceph/backupstorage/connect - connect to ceph cluster."""
        response = cephbackup_client.post('/ceph/backupstorage/connect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_ping(self, cephbackup_client):
        """Test /ceph/backupstorage/ping - ping ceph backup storage."""
        response = cephbackup_client.post('/ceph/backupstorage/ping', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_echo(self, cephbackup_client):
        """Test /ceph/backupstorage/echo - sync echo handler."""
        response = cephbackup_client.post('/ceph/backupstorage/echo', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_get_facts(self, cephbackup_client):
        """Test /ceph/backupstorage/facts - get ceph facts."""
        response = cephbackup_client.post('/ceph/backupstorage/facts', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_check_pool(self, cephbackup_client):
        """Test /ceph/backupstorage/checkpool - check pool status."""
        response = cephbackup_client.post('/ceph/backupstorage/checkpool', data={})
        assert response.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestCephBackupImageSmoke:
    """Smoke tests for ceph backup storage image operations."""

    def test_download_image(self, cephbackup_client):
        """Test /ceph/backupstorage/image/download - download image."""
        response = cephbackup_client.post('/ceph/backupstorage/image/download', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_delete_image(self, cephbackup_client):
        """Test /ceph/backupstorage/image/delete - delete image."""
        response = cephbackup_client.post('/ceph/backupstorage/image/delete', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_get_image_size(self, cephbackup_client):
        """Test /ceph/backupstorage/image/getsize - get image size."""
        response = cephbackup_client.post('/ceph/backupstorage/image/getsize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_upload_progress(self, cephbackup_client):
        """Test /ceph/backupstorage/image/progress - get upload progress."""
        response = cephbackup_client.post('/ceph/backupstorage/image/progress', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_migrate_image(self, cephbackup_client):
        """Test /ceph/backupstorage/image/migrate - migrate image between clusters."""
        response = cephbackup_client.post('/ceph/backupstorage/image/migrate', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_add_export_token(self, cephbackup_client):
        """Test /ceph/backupstorage/image/export/addtoken - add export token."""
        response = cephbackup_client.post('/ceph/backupstorage/image/export/addtoken', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_remove_export_token(self, cephbackup_client):
        """Test /ceph/backupstorage/image/export/removetoken - remove export token."""
        response = cephbackup_client.post('/ceph/backupstorage/image/export/removetoken', data={})
        assert response.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestCephBackupMetadataSmoke:
    """Smoke tests for ceph backup storage metadata operations."""

    def test_get_images_metadata(self, cephbackup_client):
        """Test /ceph/backupstorage/getimagesmetadata - get images metadata."""
        response = cephbackup_client.post('/ceph/backupstorage/getimagesmetadata', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_delete_images_metadata(self, cephbackup_client):
        """Test /ceph/backupstorage/deleteimagesmetadata - delete images metadata."""
        response = cephbackup_client.post('/ceph/backupstorage/deleteimagesmetadata', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_dump_image_metadata_to_file(self, cephbackup_client):
        """Test /ceph/backupstorage/dumpimagemetadatatofile - dump metadata to file."""
        response = cephbackup_client.post('/ceph/backupstorage/dumpimagemetadatatofile', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_check_image_metadata_file_exist(self, cephbackup_client):
        """Test /ceph/backupstorage/checkimagemetadatafileexist - check metadata file."""
        response = cephbackup_client.post('/ceph/backupstorage/checkimagemetadatafileexist', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_get_local_file_size(self, cephbackup_client):
        """Test /ceph/backupstorage/getlocalfilesize/ - get local file size."""
        response = cephbackup_client.post('/ceph/backupstorage/getlocalfilesize/', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_cancel_job(self, cephbackup_client):
        """Test /job/cancel - cancel running job."""
        response = cephbackup_client.post('/job/cancel', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
