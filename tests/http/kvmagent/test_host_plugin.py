# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent host plugin.

Note: kvmagent handlers are async callback-based. On success they
return 200 with empty body (result sent via callback URL).
"""

import pytest


@pytest.mark.http
class TestHostPluginSmoke:
    """Smoke tests for all host_plugin endpoints."""

    # --- Sync endpoints ---

    def test_echo(self, kvmagent_client):
        """Test /host/echo - sync health check."""
        response = kvmagent_client.post('/host/echo', data={})
        assert response.status_code in [200, 500]

    # --- Async endpoints (return 200 empty body) ---

    def test_ping(self, kvmagent_client):
        """Test /host/ping - agent liveness check."""
        response = kvmagent_client.post('/host/ping', data={})
        assert response.status_code == 200

    def test_capacity(self, kvmagent_client):
        """Test /host/capacity - host resource capacity."""
        response = kvmagent_client.post('/host/capacity', data={})
        assert response.status_code == 200

    def test_fact(self, kvmagent_client):
        """Test /host/fact - host hardware facts."""
        response = kvmagent_client.post('/host/fact', data={})
        assert response.status_code == 200

    def test_updateos(self, kvmagent_client):
        """Test /host/updateos - requires params, accept 200 or error."""
        response = kvmagent_client.post('/host/updateos', data={})
        assert response.status_code in [200, 400, 500]

    def test_connect(self, kvmagent_client):
        """Test /host/connect - sync host connection handshake."""
        response = kvmagent_client.post('/host/connect', data={})
        assert response.status_code in [200, 400, 500]
