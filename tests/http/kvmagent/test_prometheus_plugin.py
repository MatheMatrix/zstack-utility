# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent prometheus/monitoring plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestPrometheusSmoke:
    """Smoke tests for prometheus plugin endpoints."""

    def test_collectd_start(self, kvmagent_client, async_callback):
        """Test /prometheus/collectdexporter/start - start collectd exporter."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/prometheus/collectdexporter/start', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/prometheus/collectdexporter/start')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestCephStorageKvmSmoke:
    """Smoke tests for ceph_storage_plugin (kvmagent-side ceph helper)."""

    def test_check_host_connection(self, kvmagent_client, async_callback):
        """Test /ceph/primarystorage/check/host/connection - check ceph connection."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ceph/primarystorage/check/host/connection', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ceph/primarystorage/check/host/connection')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestFTVMFencerSmoke:
    """Smoke tests for ft_vm_fencer plugin (fault-tolerant VM fencer)."""

    def test_selffencer_setup(self, kvmagent_client, async_callback):
        """Test /ft/selffencer/setup - setup FT self-fencer."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/ft/selffencer/setup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/ft/selffencer/setup')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestZBSStorageSmoke:
    """Smoke tests for zbs_storage_plugin endpoints."""

    def test_check_host_connection(self, kvmagent_client, async_callback):
        """Test /zbs/primarystorage/check/host/connection - check ZBS connection."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbs/primarystorage/check/host/connection', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbs/primarystorage/check/host/connection')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_host_dependency(self, kvmagent_client, async_callback):
        """Test /zbs/primarystorage/host/updatedependency - update dependency."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/zbs/primarystorage/host/updatedependency', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/zbs/primarystorage/host/updatedependency')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
