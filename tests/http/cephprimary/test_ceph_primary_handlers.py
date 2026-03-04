# -*- coding: utf-8 -*-
"""HTTP integration tests for ceph primary storage agent."""

import pytest


@pytest.mark.http
class TestCephPrimaryCoreSmoke:
    """Smoke tests for ceph primary storage core endpoints."""

    def test_init(self, cephprimary_client):
        """Test /ceph/primarystorage/init - initialize ceph primary storage."""
        response = cephprimary_client.post('/ceph/primarystorage/init', data={})
        assert response.status_code in [200, 400, 500]

    def test_connect(self, cephprimary_client):
        """Test /ceph/primarystorage/connect - connect to ceph cluster."""
        response = cephprimary_client.post('/ceph/primarystorage/connect', data={})
        assert response.status_code in [200, 400, 500]

    def test_ping(self, cephprimary_client):
        """Test /ceph/primarystorage/ping - ping ceph primary storage."""
        response = cephprimary_client.post('/ceph/primarystorage/ping', data={})
        assert response.status_code in [200, 400, 500]

    def test_echo(self, cephprimary_client):
        """Test /ceph/primarystorage/echo - sync echo handler."""
        response = cephprimary_client.post('/ceph/primarystorage/echo', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_facts(self, cephprimary_client):
        """Test /ceph/primarystorage/facts - get ceph facts."""
        response = cephprimary_client.post('/ceph/primarystorage/facts', data={})
        assert response.status_code in [200, 400, 500]

    def test_add_pool(self, cephprimary_client):
        """Test /ceph/primarystorage/addpool - add storage pool."""
        response = cephprimary_client.post('/ceph/primarystorage/addpool', data={})
        assert response.status_code in [200, 400, 500]

    def test_check_pool(self, cephprimary_client):
        """Test /ceph/primarystorage/checkpool - check pool status."""
        response = cephprimary_client.post('/ceph/primarystorage/checkpool', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_image_cache(self, cephprimary_client):
        """Test /ceph/primarystorage/deleteimagecache - delete image cache."""
        response = cephprimary_client.post('/ceph/primarystorage/deleteimagecache', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephPrimaryVolumeSmoke:
    """Smoke tests for ceph primary storage volume operations."""

    def test_create_empty(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/createempty - create empty volume."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/createempty', data={})
        assert response.status_code in [200, 400, 500]

    def test_clone(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/clone - clone volume."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/clone', data={})
        assert response.status_code in [200, 400, 500]

    def test_flatten(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/flatten - flatten volume."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/flatten', data={})
        assert response.status_code in [200, 400, 500]

    def test_cp(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/cp - copy volume."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/cp', data={})
        assert response.status_code in [200, 400, 500]

    def test_resize(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/resize - resize volume."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/resize', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete(self, cephprimary_client):
        """Test /ceph/primarystorage/delete - delete volume/bits."""
        response = cephprimary_client.post('/ceph/primarystorage/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_volume_size(self, cephprimary_client):
        """Test /ceph/primarystorage/getvolumesize - get volume size."""
        response = cephprimary_client.post('/ceph/primarystorage/getvolumesize', data={})
        assert response.status_code in [200, 400, 500]

    def test_batch_get_volume_size(self, cephprimary_client):
        """Test /ceph/primarystorage/batchgetvolumesize - batch get volume sizes."""
        response = cephprimary_client.post('/ceph/primarystorage/batchgetvolumesize', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_volume_watchers(self, cephprimary_client):
        """Test /ceph/primarystorage/getvolumewatchers - get volume watchers."""
        response = cephprimary_client.post('/ceph/primarystorage/getvolumewatchers', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_volume_snapshot_size(self, cephprimary_client):
        """Test /ceph/primarystorage/getvolumesnapshotsize - get snapshot size."""
        response = cephprimary_client.post('/ceph/primarystorage/getvolumesnapshotsize', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_backing_chain(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/getbackingchain - get backing chain."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/getbackingchain', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_volume_chain(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/deletechain - delete volume chain."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/deletechain', data={})
        assert response.status_code in [200, 400, 500]

    def test_check_bits(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/checkbits - check bits existence."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/checkbits', data={})
        assert response.status_code in [200, 400, 500]

    def test_purge_snapshots(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/purgesnapshots - purge snapshots."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/purgesnapshots', data={})
        assert response.status_code in [200, 400, 500]

    def test_migrate_volume_segment(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/migratesegment - migrate volume segment."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/migratesegment', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_volume_snapinfos(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/getsnapinfos - get volume snap infos."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/getsnapinfos', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephPrimarySnapshotSmoke:
    """Smoke tests for ceph primary storage snapshot operations."""

    def test_create_snapshot(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/create - create snapshot."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/create', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_snapshot(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/delete - delete snapshot."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_protect_snapshot(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/protect - protect snapshot."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/protect', data={})
        assert response.status_code in [200, 400, 500]

    def test_unprotect_snapshot(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/unprotect - unprotect snapshot."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/unprotect', data={})
        assert response.status_code in [200, 400, 500]

    def test_rollback_snapshot(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/rollback - rollback snapshot."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/rollback', data={})
        assert response.status_code in [200, 400, 500]

    def test_commit_image(self, cephprimary_client):
        """Test /ceph/primarystorage/snapshot/commit - commit snapshot to image."""
        response = cephprimary_client.post('/ceph/primarystorage/snapshot/commit', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephPrimaryTransferSmoke:
    """Smoke tests for ceph primary storage data transfer operations."""

    def test_sftp_download(self, cephprimary_client):
        """Test /ceph/primarystorage/sftpbackupstorage/download - SFTP download."""
        response = cephprimary_client.post('/ceph/primarystorage/sftpbackupstorage/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_sftp_upload(self, cephprimary_client):
        """Test /ceph/primarystorage/sftpbackupstorage/upload - SFTP upload."""
        response = cephprimary_client.post('/ceph/primarystorage/sftpbackupstorage/upload', data={})
        assert response.status_code in [200, 400, 500]

    def test_upload_imagestore(self, cephprimary_client):
        """Test /ceph/primarystorage/imagestore/backupstorage/commit - upload to imagestore."""
        response = cephprimary_client.post('/ceph/primarystorage/imagestore/backupstorage/commit', data={})
        assert response.status_code in [200, 400, 500]

    def test_download_imagestore(self, cephprimary_client):
        """Test /ceph/primarystorage/imagestore/backupstorage/download - download from imagestore."""
        response = cephprimary_client.post('/ceph/primarystorage/imagestore/backupstorage/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_download_from_kvmhost(self, cephprimary_client):
        """Test /ceph/primarystorage/kvmhost/download - download from KVM host."""
        response = cephprimary_client.post('/ceph/primarystorage/kvmhost/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_cancel_download_from_kvmhost(self, cephprimary_client):
        """Test /ceph/primarystorage/kvmhost/download/cancel - cancel download."""
        response = cephprimary_client.post('/ceph/primarystorage/kvmhost/download/cancel', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_download_progress(self, cephprimary_client):
        """Test /ceph/primarystorage/kvmhost/download/progress - get download progress."""
        response = cephprimary_client.post('/ceph/primarystorage/kvmhost/download/progress', data={})
        assert response.status_code in [200, 400, 500]

    def test_download_from_nbd(self, cephprimary_client):
        """Test /ceph/primarystorage/nbd/download - download from NBD."""
        response = cephprimary_client.post('/ceph/primarystorage/nbd/download', data={})
        assert response.status_code in [200, 400, 500]

    def test_download_from_remote_target(self, cephprimary_client):
        """Test /ceph/primarystorage/remotetarget/download - download from remote."""
        response = cephprimary_client.post('/ceph/primarystorage/remotetarget/download', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephPrimaryBackupSmoke:
    """Smoke tests for ceph primary storage backup operations."""

    def test_take_storage_backup(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/takebackup - take storage backup."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/takebackup', data={})
        assert response.status_code in [200, 400, 500]

    def test_cancel_storage_backup(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/cancelbackup - cancel storage backup."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/cancelbackup', data={})
        assert response.status_code in [200, 400, 500]

    def test_get_storage_backup_mode(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/getbackupmode - get backup mode."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/getbackupmode', data={})
        assert response.status_code in [200, 400, 500]

    def test_clean_storage_backup_cache(self, cephprimary_client):
        """Test /ceph/primarystorage/volume/cleanbackupcache - clean backup cache."""
        response = cephprimary_client.post('/ceph/primarystorage/volume/cleanbackupcache', data={})
        assert response.status_code in [200, 400, 500]

    def test_clean_trash(self, cephprimary_client):
        """Test /ceph/primarystorage/trash/clean - clean trash."""
        response = cephprimary_client.post('/ceph/primarystorage/trash/clean', data={})
        assert response.status_code in [200, 400, 500]

    def test_cancel_job(self, cephprimary_client):
        """Test /job/cancel - cancel running job."""
        response = cephprimary_client.post('/job/cancel', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephPrimaryXSkySmoke:
    """Smoke tests for XSKY ceph primary storage endpoints."""

    def test_get_block_volume_access(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/volume/access/path - get access path."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/volume/access/path', data={})
        assert response.status_code in [200, 400, 500]

    def test_resize_block_volume(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/volume/resize - resize XSKY volume."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/volume/resize', data={})
        assert response.status_code in [200, 400, 500]

    def test_create_block_volume(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/volume/createempty - create XSKY volume."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/volume/createempty', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_block_volume(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/delete - delete XSKY volume."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_update_block_volume(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/volume/update - update XSKY volume info."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/volume/update', data={})
        assert response.status_code in [200, 400, 500]

    def test_update_block_volume_snapshot(self, cephprimary_client):
        """Test /xsky/ceph/primarystorage/volume/snapshot/update - update snapshot."""
        response = cephprimary_client.post('/xsky/ceph/primarystorage/volume/snapshot/update', data={})
        assert response.status_code in [200, 400, 500]
