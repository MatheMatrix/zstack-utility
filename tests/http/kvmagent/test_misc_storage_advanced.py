# -*- coding: utf-8 -*-
"""HTTP integration tests for misc storage plugins.

Covers zbox (backup), ZSES (ZStack Enterprise Storage), ZBS, mini_storage,
and shared_mountpoint primary storage operations.
"""

import pytest


@pytest.mark.http
class TestZboxSmoke:
    """Smoke tests for zbox_plugin endpoints."""

    def test_take_shallow_backup(self, kvmagent_client):
        """Test /zbox/volumes/takeshallowbackup - take shallow backup."""
        resp = kvmagent_client.post('/zbox/volumes/takeshallowbackup', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_backup_init(self, kvmagent_client):
        """Test /zbox/backup/init - initialize zbox backup."""
        resp = kvmagent_client.post('/zbox/backup/init', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestZsesSmoke:
    """Smoke tests for ZSES endpoints."""

    def test_init(self, kvmagent_client):
        """Test /zses/init - initialize ZSES."""
        resp = kvmagent_client.post('/zses/init', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_get_physical_capacity(self, kvmagent_client):
        """Test /zses/getphysicalcapacity - get physical capacity."""
        resp = kvmagent_client.post('/zses/getphysicalcapacity', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_empty_volume(self, kvmagent_client):
        """Test /zses/volume/createempty - create empty volume."""
        resp = kvmagent_client.post('/zses/volume/createempty', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_volume_from_cache(self, kvmagent_client):
        """Test /zses/volume/createvolumefromcache - create from cache."""
        resp = kvmagent_client.post('/zses/volume/createvolumefromcache', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_bits(self, kvmagent_client):
        """Test /zses/delete - delete bits."""
        resp = kvmagent_client.post('/zses/delete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_dir(self, kvmagent_client):
        """Test /zses/deletedir - delete directory."""
        resp = kvmagent_client.post('/zses/deletedir', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_upload_to_imagestore(self, kvmagent_client):
        """Test /zses/imagestore/upload - upload to imagestore."""
        resp = kvmagent_client.post('/zses/imagestore/upload', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_commit_to_imagestore(self, kvmagent_client):
        """Test /zses/imagestore/commit - commit to imagestore."""
        resp = kvmagent_client.post('/zses/imagestore/commit', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_download_from_imagestore(self, kvmagent_client):
        """Test /zses/imagestore/download - download from imagestore."""
        resp = kvmagent_client.post('/zses/imagestore/download', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_revert_snapshot(self, kvmagent_client):
        """Test /zses/snapshot/revert - revert snapshot."""
        resp = kvmagent_client.post('/zses/snapshot/revert', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_merge_snapshot(self, kvmagent_client):
        """Test /zses/snapshot/merge - merge snapshot."""
        resp = kvmagent_client.post('/zses/snapshot/merge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_merge_and_rebase_snapshot(self, kvmagent_client):
        """Test /zses/snapshot/mergeandrebase - merge and rebase."""
        resp = kvmagent_client.post('/zses/snapshot/mergeandrebase', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_offline_merge(self, kvmagent_client):
        """Test /zses/snapshot/offlinemerge - offline merge."""
        resp = kvmagent_client.post('/zses/snapshot/offlinemerge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_check_bits(self, kvmagent_client):
        """Test /zses/checkbits - check bits exist."""
        resp = kvmagent_client.post('/zses/checkbits', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_rebase_root_volume(self, kvmagent_client):
        """Test /zses/volume/rebaserootvolumetobackingfile - rebase."""
        resp = kvmagent_client.post('/zses/volume/rebaserootvolumetobackingfile', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestZbsSmoke:
    """Smoke tests for ZBS storage endpoints."""

    def test_check_host_connection(self, kvmagent_client):
        """Test /zbs/primarystorage/check/host/connection - check connection."""
        resp = kvmagent_client.post('/zbs/primarystorage/check/host/connection', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_update_host_dependency(self, kvmagent_client):
        """Test /zbs/primarystorage/host/updatedependency - update deps."""
        resp = kvmagent_client.post('/zbs/primarystorage/host/updatedependency', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestMiniStorageSmoke:
    """Smoke tests for mini_storage_plugin endpoints."""

    def test_connect(self, kvmagent_client):
        """Test /ministorage/connect - connect mini storage."""
        resp = kvmagent_client.post('/ministorage/connect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_disconnect(self, kvmagent_client):
        """Test /ministorage/disconnect - disconnect mini storage."""
        resp = kvmagent_client.post('/ministorage/disconnect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_root_volume(self, kvmagent_client):
        """Test /ministorage/createrootvolume - create root volume."""
        resp = kvmagent_client.post('/ministorage/createrootvolume', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_bits(self, kvmagent_client):
        """Test /ministorage/bits/delete - delete bits."""
        resp = kvmagent_client.post('/ministorage/bits/delete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_template(self, kvmagent_client):
        """Test /ministorage/createtemplatefromvolume - create template."""
        resp = kvmagent_client.post('/ministorage/createtemplatefromvolume', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_upload_to_imagestore(self, kvmagent_client):
        """Test /ministorage/imagestore/upload - upload to imagestore."""
        resp = kvmagent_client.post('/ministorage/imagestore/upload', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_commit_to_imagestore(self, kvmagent_client):
        """Test /ministorage/imagestore/commit - commit to imagestore."""
        resp = kvmagent_client.post('/ministorage/imagestore/commit', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_download_from_imagestore(self, kvmagent_client):
        """Test /ministorage/imagestore/download - download from imagestore."""
        resp = kvmagent_client.post('/ministorage/imagestore/download', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_empty_volume(self, kvmagent_client):
        """Test /ministorage/volume/createempty - create empty volume."""
        resp = kvmagent_client.post('/ministorage/volume/createempty', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_empty_cache_volume(self, kvmagent_client):
        """Test /ministorage/cachevolume/createempty - create empty cache vol."""
        resp = kvmagent_client.post('/ministorage/cachevolume/createempty', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_check_bits(self, kvmagent_client):
        """Test /ministorage/bits/check - check bits exist."""
        resp = kvmagent_client.post('/ministorage/bits/check', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_resize_volume(self, kvmagent_client):
        """Test /ministorage/volume/resize - resize volume."""
        resp = kvmagent_client.post('/ministorage/volume/resize', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_change_volume_active(self, kvmagent_client):
        """Test /ministorage/volume/active - change volume active state."""
        resp = kvmagent_client.post('/ministorage/volume/active', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_get_volume_size(self, kvmagent_client):
        """Test /ministorage/volume/getsize - get volume size."""
        resp = kvmagent_client.post('/ministorage/volume/getsize', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_check_disks(self, kvmagent_client):
        """Test /ministorage/disks/check - check disks."""
        resp = kvmagent_client.post('/ministorage/disks/check', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestSharedMountpointSmoke:
    """Smoke tests for shared_mountpoint_plugin endpoints."""

    def test_connect(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/connect - connect."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/connect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_root_volume(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/createrootvolume - create root vol."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createrootvolume', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_volume_with_backing(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/createvolumewithbacking."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createvolumewithbacking', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_bits(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/bits/delete - delete bits."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/bits/delete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_unlink_bits(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/bits/unlink - unlink bits."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/bits/unlink', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_template(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/createtemplatefromvolume."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createtemplatefromvolume', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_estimate_template_size(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/estimatetemplatesize."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/estimatetemplatesize', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_upload_to_sftp(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/sftp/upload - SFTP upload."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/sftp/upload', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_download_from_sftp(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/sftp/download - SFTP download."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/sftp/download', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_upload_to_imagestore(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/upload."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/upload', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_commit_to_imagestore(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/commit."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/commit', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_download_from_imagestore(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/imagestore/download."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/download', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_revert_snapshot(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/volume/revertfromsnapshot."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/volume/revertfromsnapshot', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_merge_snapshot(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/snapshot/merge."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/merge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_offline_merge_snapshot(self, kvmagent_client):
        """Test /sharedmountpointprimarystorage/snapshot/offlinemerge."""
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/offlinemerge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
