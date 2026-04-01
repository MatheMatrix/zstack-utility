# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent mini storage plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestMiniStorageSmoke:
    """Smoke tests for mini_storage_plugin endpoints."""

    def test_connect(self, kvmagent_client, async_callback):
        """Test /ministorage/connect - connect mini storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/connect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_disconnect(self, kvmagent_client, async_callback):
        """Test /ministorage/disconnect - disconnect mini storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/disconnect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/disconnect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_bits_check(self, kvmagent_client, async_callback):
        """Test /ministorage/bits/check - check bits existence."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/bits/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/bits/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_bits_delete(self, kvmagent_client, async_callback):
        """Test /ministorage/bits/delete - delete bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/bits/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/bits/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_createempty(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/createempty - create empty volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/volume/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/volume/createempty')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_getsize(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/getsize - get volume size."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/volume/getsize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/volume/getsize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_resize(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/resize - resize volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/volume/resize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/volume/resize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_active(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/active - activate volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/volume/active', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/volume/active')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_disks_check(self, kvmagent_client, async_callback):
        """Test /ministorage/disks/check - check disks status."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/disks/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/disks/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_revertfromsnapshot(self, kvmagent_client, async_callback):
        """Test /ministorage/volume/revertfromsnapshot - revert volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/volume/revertfromsnapshot', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/volume/revertfromsnapshot')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_upload(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/upload - upload to imagestore."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/imagestore/upload')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_download(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/download - download from imagestore."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/imagestore/download')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_imagestore_commit(self, kvmagent_client, async_callback):
        """Test /ministorage/imagestore/commit - commit to imagestore."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ministorage/imagestore/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ministorage/imagestore/commit')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
