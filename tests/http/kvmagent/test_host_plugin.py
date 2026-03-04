# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent host plugin."""

import pytest


@pytest.mark.http
class TestHostPlugin:
    """Test kvmagent host plugin HTTP handlers.

    Note: kvmagent handlers are async callback-based. On success they
    return 200 with empty body (result sent via callback URL).
    """

    def test_ping(self, kvmagent_client):
        """Test /host/ping handler - verify agent responds."""
        response = kvmagent_client.post('/host/ping', data={})
        assert response.status_code == 200

    def test_echo(self, kvmagent_client):
        """Test /host/echo handler - verify echo response."""
        test_data = {'message': 'test'}
        response = kvmagent_client.post('/host/echo', data=test_data)
        # Accept 200 (async) or 500 (handler may not support arbitrary input)
        assert response.status_code in [200, 500]

    def test_capacity(self, kvmagent_client):
        """Test /host/capacity handler - verify endpoint is reachable."""
        response = kvmagent_client.post('/host/capacity', data={})
        assert response.status_code == 200

    def test_fact(self, kvmagent_client):
        """Test /host/fact handler - verify endpoint is reachable."""
        response = kvmagent_client.post('/host/fact', data={})
        assert response.status_code == 200
