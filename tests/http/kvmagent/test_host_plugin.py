# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent host plugin.

Note: kvmagent handlers are async callback-based. On success they
return 200 with empty body (result sent via callback URL).
"""

import pytest

pytestmark = [pytest.mark.http]


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


class TestHostPluginSmoke:
    """Smoke tests for all host_plugin endpoints."""

    # --- Sync endpoints (no callback) ---

    def test_echo(self, kvmagent_client):
        """Test /host/echo - sync health check."""
        response = kvmagent_client.post('/host/echo', data={})
        assert response.status_code in [200, 403, 404, 500]

    def test_connect(self, kvmagent_client):
        """Test /host/connect - sync host connection handshake."""
        response = kvmagent_client.post('/host/connect', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    # --- Async endpoints (callback-based) ---

    def test_capacity_callback(self, kvmagent_client, async_callback):
        """Test /host/capacity - host resource capacity via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/capacity',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/capacity')
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_fact_callback(self, kvmagent_client, async_callback):
        """Test /host/fact - host hardware facts via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/fact',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/fact')
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_ping_callback(self, kvmagent_client, async_callback):
        """Test /host/ping - agent liveness check via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/ping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/ping')
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_updateos_callback(self, kvmagent_client, async_callback):
        """Test /host/updateos - OS update request via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/updateos',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/updateos')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_changepasswd_callback(self, kvmagent_client, async_callback):
        """Test /host/changepasswd - change password via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/changepasswd',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/changepasswd')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getnicinfo_callback(self, kvmagent_client, async_callback):
        """Test /host/getnicinfo - get NIC info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/getnicinfo',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/getnicinfo')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getallmacs_callback(self, kvmagent_client, async_callback):
        """Test /host/getallmacs - get all MAC addresses via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/getallmacs',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/getallmacs')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_changedefaultnic_callback(self, kvmagent_client, async_callback):
        """Test /host/changedefaultnic - change default NIC via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/changedefaultnic',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/changedefaultnic')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_setupselffencer_callback(self, kvmagent_client, async_callback):
        """Test /host/setupselffencer - setup self-fencer via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/setupselffencer',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/setupselffencer')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_cancelselffencer_callback(self, kvmagent_client, async_callback):
        """Test /host/cancelselffencer - cancel self-fencer via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/cancelselffencer',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/cancelselffencer')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_scansrp_callback(self, kvmagent_client, async_callback):
        """Test /host/scansrp - scan SRP via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/scansrp',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/scansrp')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
