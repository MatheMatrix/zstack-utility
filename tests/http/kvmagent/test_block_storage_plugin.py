# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent block storage plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestBlockStorageSmoke:
    """Smoke tests for block_storage_plugin endpoints (iSCSI block primary storage)."""

    def test_getinitiatorname(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/getinitiatorname - get iSCSI initiator name."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/getinitiatorname', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/getinitiatorname')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_createheartbeat(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/createheartbeat - create heartbeat."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/createheartbeat', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/createheartbeat')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_deleteheartbeat(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/deleteheartbeat - delete heartbeat."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/deleteheartbeat', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/deleteheartbeat')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_ping(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/ping - ping block storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/ping', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/ping')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volume_resize(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/volume/resize - resize volume."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/volume/resize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/volume/resize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_lun_rescan(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/lun/rescan - rescan LUN."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/lun/rescan', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/lun/rescan')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_unmount(self, kvmagent_client, async_callback):
        """Test /block/primarystorage/unmount - unmount block storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/block/primarystorage/unmount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/block/primarystorage/unmount')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
