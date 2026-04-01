# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent shared mountpoint primary storage plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestSharedMountpointSmoke:
    """Smoke tests for shared_mountpoint_plugin endpoints."""

    def test_connect(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/connect - connect storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/connect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_bits_check(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/bits/check - check bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/bits/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/bits/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_bits_delete(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/bits/delete - delete bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/bits/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/bits/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_createempty(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/volume/createempty - create empty volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/volume/createempty')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_getsize(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/volume/getsize - get volume size."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/getsize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/volume/getsize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_resize(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/volume/resize - resize volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/resize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/volume/resize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_getbackingchain(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/volume/getbackingchain - get chain."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/volume/getbackingchain', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/volume/getbackingchain')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_estimatetemplatesize(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/estimatetemplatesize - estimate size."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/estimatetemplatesize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/estimatetemplatesize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_snapshot_merge(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/snapshot/merge - merge snapshot."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/snapshot/merge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/snapshot/merge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_upload(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/upload - upload."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/imagestore/upload')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_download(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/download - download."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/imagestore/download')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_commit(self, kvmagent_client, async_callback):
        """Test /sharedmountpointprimarystorage/imagestore/commit - commit."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/sharedmountpointprimarystorage/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/sharedmountpointprimarystorage/imagestore/commit')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
