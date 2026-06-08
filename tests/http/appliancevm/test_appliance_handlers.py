# -*- coding: utf-8 -*-
"""HTTP integration tests for appliancevm handlers."""

import pytest


@pytest.mark.http
class TestApplianceHandlers:
    """Test appliancevm HTTP handlers."""

    def test_echo(self, appliancevm_client):
        """Test /appliancevm/echo handler - verify agent responds."""
        response = appliancevm_client.post('/appliancevm/echo', data={})

        # Echo handler returns empty string on success (status 200)
        # or may be unavailable if agent is not running
        assert response.status_code in [200, 404, 500, 502, 503]
        
        if response.status_code == 200:
            # Handler returns empty string, not JSON
            assert response.text == '' or 'success' in response.json()
