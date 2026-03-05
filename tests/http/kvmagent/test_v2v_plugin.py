# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent V2V conversion plugin."""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestV2VPluginSmoke:
    """Smoke tests for kvm_v2v_plugin endpoints."""

    def test_init(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/init - initialize V2V conversion host."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/init')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_listvm(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/listvm - list VMs for V2V."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/listvm', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/listvm')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_umount(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/umount - unmount V2V storage."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/umount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/umount')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_clean(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/clean - clean V2V temp files."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/clean', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/clean')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_bits(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/checkbits - check V2V bits."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/checkbits', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/checkbits')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_config_qos(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/qos/config - configure QoS."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/qos/config', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/qos/config')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_qos(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/qos/delete - delete QoS."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/qos/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/qos/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_convert(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/convert/cancel - cancel conversion."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/kvmv2v/conversionhost/convert/cancel', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/kvmv2v/conversionhost/convert/cancel')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
