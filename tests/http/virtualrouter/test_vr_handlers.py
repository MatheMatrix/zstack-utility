# -*- coding: utf-8 -*-
"""HTTP integration tests for virtualrouter handlers."""

import pytest


@pytest.mark.http
class TestVirtualRouterHandlers:
    """Test virtualrouter HTTP handlers."""

    def test_init(self, virtualrouter_client):
        """Test /init handler - initialize VR with UUID."""
        test_data = {'uuid': 'test-vr-uuid-12345'}
        response = virtualrouter_client.post('/init', data=test_data)

        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        assert data['success'] is True

    def test_ping(self, virtualrouter_client):
        """Test /ping handler - verify agent responds with uuid."""
        response = virtualrouter_client.post('/ping', data={})

        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        assert data['success'] is True
        # Ping returns uuid after init
        assert 'uuid' in data

    def test_echo(self, virtualrouter_client):
        """Test /echo handler - verify echo response."""
        test_data = {'message': 'test'}
        response = virtualrouter_client.post('/echo', data=test_data)

        assert response.status_code == 200
        # Echo handler returns empty string on success
