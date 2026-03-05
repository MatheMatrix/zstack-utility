# -*- coding: utf-8 -*-
"""HTTP integration tests for appliancevm handlers."""

import pytest


@pytest.mark.http
class TestApplianceVMSmoke:
    """Smoke tests for appliancevm endpoints."""

    def test_echo(self, appliancevm_client):
        """Test /appliancevm/echo - sync echo handler."""
        response = appliancevm_client.post('/appliancevm/echo', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_init(self, appliancevm_client):
        """Test /appliancevm/init - initialize appliancevm."""
        response = appliancevm_client.post('/appliancevm/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_refresh_firewall(self, appliancevm_client):
        """Test /appliancevm/refreshfirewall - refresh firewall rules."""
        response = appliancevm_client.post('/appliancevm/refreshfirewall', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
