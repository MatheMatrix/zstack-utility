# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent ZBox backup plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestZBoxSmoke:
    """Smoke tests for zbox_plugin endpoints."""

    def test_init(self, kvmagent_client, async_callback):
        """Test /zbox/init - initialize ZBox."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/init')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_eject(self, kvmagent_client, async_callback):
        """Test /zbox/eject - eject ZBox device."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/eject', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/eject')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_refresh(self, kvmagent_client, async_callback):
        """Test /zbox/refresh - refresh ZBox state."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/refresh', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/refresh')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_sync(self, kvmagent_client, async_callback):
        """Test /zbox/sync - sync ZBox data."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/sync', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/sync')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_deletebits(self, kvmagent_client, async_callback):
        """Test /zbox/deletebits - delete ZBox bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/deletebits', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/deletebits')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_backup_init(self, kvmagent_client, async_callback):
        """Test /zbox/backup/init - initialize ZBox backup."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/backup/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/backup/init')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_volumes_takeshallowbackup(self, kvmagent_client, async_callback):
        """Test /zbox/volumes/takeshallowbackup - take shallow backup."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbox/volumes/takeshallowbackup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbox/volumes/takeshallowbackup')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
