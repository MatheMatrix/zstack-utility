# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent host plugin."""

import pytest


@pytest.mark.http
class TestHostPlugin:
    """Test kvmagent host plugin HTTP handlers."""

    def test_ping(self, kvmagent_client):
        """Test /host/ping handler - verify agent responds."""
        response = kvmagent_client.post('/host/ping', data={})

        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        assert data['success'] is True

    def test_echo(self, kvmagent_client):
        """Test /host/echo handler - verify echo response."""
        test_data = {'message': 'test'}
        response = kvmagent_client.post('/host/echo', data=test_data)

        assert response.status_code == 200
        # Echo handler returns empty string on success

    def test_capacity(self, kvmagent_client):
        """Test /host/capacity handler - verify returns capacity data."""
        response = kvmagent_client.post('/host/capacity', data={})

        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        assert data['success'] is True
        # Capacity response should contain resource fields
        assert 'cpuNum' in data
        assert 'totalMemory' in data
        assert 'usedMemory' in data
        assert 'cpuSockets' in data

    def test_fact(self, kvmagent_client):
        """Test /host/fact handler - verify returns host facts."""
        response = kvmagent_client.post('/host/fact', data={})

        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        assert data['success'] is True
        # Fact response should contain host information fields
        assert 'osDistribution' in data
        assert 'osVersion' in data
        assert 'cpuModelName' in data
        assert 'libvirtVersion' in data
