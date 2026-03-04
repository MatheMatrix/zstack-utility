# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent VM plugin."""

import pytest


@pytest.mark.http
class TestVMPlugin:
    """Test kvmagent VM plugin HTTP handlers (non-destructive queries only).

    Note: kvmagent handlers are async callback-based. On success they
    return 200 with empty body (result sent via callback URL).
    """

    def test_checkstate(self, kvmagent_client):
        """Test /vm/checkstate handler - verify endpoint is reachable."""
        test_data = {'vmUuids': []}
        response = kvmagent_client.post('/vm/checkstate', data=test_data)
        assert response.status_code == 200

    def test_getvncport(self, kvmagent_client):
        """Test /vm/getvncport handler - verify endpoint is reachable."""
        test_data = {}
        response = kvmagent_client.post('/vm/getvncport', data=test_data)
        # Accept 200 (async accepted) or 400/500 (missing required fields)
        assert response.status_code in [200, 400, 500]

    def test_getdeviceaddress(self, kvmagent_client):
        """Test /vm/getdeviceaddress handler - verify endpoint is reachable."""
        test_data = {}
        response = kvmagent_client.post('/vm/getdeviceaddress', data=test_data)
        # Accept 200 (async accepted) or 400/500 (missing required fields)
        assert response.status_code in [200, 400, 500]
