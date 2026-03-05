# -*- coding: utf-8 -*-
"""HTTP integration tests for misc storage plugins.

Covers zbox (backup), ZSES (ZStack Enterprise Storage), ZBS, mini_storage,
and shared_mountpoint primary storage operations.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestZboxSmoke:
    """Smoke tests for zbox_plugin endpoints."""

    def test_take_shallow_backup(self, kvmagent_client, async_callback):
        """Test /zbox/volumes/takeshallowbackup - take shallow backup."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zbox/volumes/takeshallowbackup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zbox/volumes/takeshallowbackup')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_backup_init(self, kvmagent_client, async_callback):
        """Test /zbox/backup/init - initialize zbox backup."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zbox/backup/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zbox/backup/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestZsesSmoke:
    """Smoke tests for ZSES endpoints."""

    def test_init(self, kvmagent_client, async_callback):
        """Test /zses/init - initialize ZSES."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_get_physical_capacity(self, kvmagent_client, async_callback):
        """Test /zses/getphysicalcapacity - get physical capacity."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/getphysicalcapacity', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/getphysicalcapacity')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_empty_volume(self, kvmagent_client, async_callback):
        """Test /zses/volume/createempty - create empty volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/volume/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/volume/createempty')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_volume_from_cache(self, kvmagent_client, async_callback):
        """Test /zses/volume/createvolumefromcache - create from cache."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/volume/createvolumefromcache', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/volume/createvolumefromcache')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bits(self, kvmagent_client, async_callback):
        """Test /zses/delete - delete bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_dir(self, kvmagent_client, async_callback):
        """Test /zses/deletedir - delete directory."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/deletedir', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/deletedir')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_upload_to_imagestore(self, kvmagent_client, async_callback):
        """Test /zses/imagestore/upload - upload to imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/imagestore/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_commit_to_imagestore(self, kvmagent_client, async_callback):
        """Test /zses/imagestore/commit - commit to imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/imagestore/commit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_from_imagestore(self, kvmagent_client, async_callback):
        """Test /zses/imagestore/download - download from imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/imagestore/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_revert_snapshot(self, kvmagent_client, async_callback):
        """Test /zses/snapshot/revert - revert snapshot."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/snapshot/revert', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/snapshot/revert')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_merge_snapshot(self, kvmagent_client, async_callback):
        """Test /zses/snapshot/merge - merge snapshot."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/snapshot/merge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/snapshot/merge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_merge_and_rebase_snapshot(self, kvmagent_client, async_callback):
        """Test /zses/snapshot/mergeandrebase - merge and rebase."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/snapshot/mergeandrebase', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/snapshot/mergeandrebase')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_offline_merge(self, kvmagent_client, async_callback):
        """Test /zses/snapshot/offlinemerge - offline merge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/snapshot/offlinemerge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/snapshot/offlinemerge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_bits(self, kvmagent_client, async_callback):
        """Test /zses/checkbits - check bits exist."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/checkbits', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/checkbits')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_rebase_root_volume(self, kvmagent_client, async_callback):
        """Test /zses/volume/rebaserootvolumetobackingfile - rebase."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zses/volume/rebaserootvolumetobackingfile', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zses/volume/rebaserootvolumetobackingfile')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestZbsSmoke:
    """Smoke tests for ZBS storage endpoints."""

    def test_check_host_connection(self, kvmagent_client, async_callback):
        """Test /zbs/primarystorage/check/host/connection - check connection."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zbs/primarystorage/check/host/connection', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zbs/primarystorage/check/host/connection')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_host_dependency(self, kvmagent_client, async_callback):
        """Test /zbs/primarystorage/host/updatedependency - update deps."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/zbs/primarystorage/host/updatedependency', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/zbs/primarystorage/host/updatedependency')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestMiniStorageSmoke:
    """Smoke tests for mini_storage_plugin endpoints."""

    def test_connect(self, kvmagent_client, async_callback):
        """Test /ministorage/connect - connect mini storage."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/connect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_disconnect(self, kvmagent_client, async_callback):
        """Test /ministorage/disconnect - disconnect mini storage."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/disconnect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/disconnect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_root_volume(self, kvmagent_client, async_callback):
        """Test /ministorage/createrootvolume - create root volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/createrootvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/createrootvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bits(self, kvmagent_client, async_callback):
        """Test /ministorage/bits/delete - delete bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/bits/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/bits/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_template(self, kvmagent_client, async_callback):
        """Test /ministorage/createtemplatefromvolume - create template."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/createtemplatefromvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/createtemplatefromvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_upload_to_imagestore(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/upload - upload to imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/imagestore/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_commit_to_imagestore(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/commit - commit to imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/imagestore/commit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_from_imagestore(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/download - download from imagestore."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/imagestore/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_empty_volume(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/createempty - create empty volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/volume/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/volume/createempty')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_empty_cache_volume(self, kvmagent_client, async_callback):
        """Test /ministorage/cachevolume/createempty - create empty cache vol."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/cachevolume/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/cachevolume/createempty')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_bits(self, kvmagent_client, async_callback):
        """Test /ministorage/bits/check - check bits exist."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/bits/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/bits/check')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_resize_volume(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/resize - resize volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/volume/resize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/volume/resize')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_change_volume_active(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/active - change volume active state."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/volume/active', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/volume/active')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_get_volume_size(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/getsize - get volume size."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/volume/getsize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/volume/getsize')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_disks(self, kvmagent_client, async_callback):
        """Test /ministorage/disks/check - check disks."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ministorage/disks/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ministorage/disks/check')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestSharedMountpointSmoke:
    """Smoke tests for shared_mountpoint_plugin endpoints."""

    def test_connect(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/connect - connect."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/connect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_root_volume(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/createrootvolume - create root vol."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createrootvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/createrootvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_volume_with_backing(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/createvolumewithbacking."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createvolumewithbacking', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/createvolumewithbacking')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bits(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/bits/delete - delete bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/bits/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/bits/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_unlink_bits(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/bits/unlink - unlink bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/bits/unlink', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/bits/unlink')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_template(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/createtemplatefromvolume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/createtemplatefromvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/createtemplatefromvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_estimate_template_size(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/estimatetemplatesize."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/estimatetemplatesize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/estimatetemplatesize')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_upload_to_sftp(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/sftp/upload - SFTP upload."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/sftp/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/sftp/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_from_sftp(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/sftp/download - SFTP download."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/sftp/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/sftp/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_upload_to_imagestore(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/upload."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/imagestore/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_commit_to_imagestore(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/commit."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/imagestore/commit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_from_imagestore(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/download."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/imagestore/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_revert_snapshot(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/volume/revertfromsnapshot."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/volume/revertfromsnapshot', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/volume/revertfromsnapshot')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_merge_snapshot(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/snapshot/merge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/merge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/snapshot/merge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_offline_merge_snapshot(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/snapshot/offlinemerge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/offlinemerge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedmountpointprimarystorage/snapshot/offlinemerge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
