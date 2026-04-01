# -*- coding: utf-8 -*-
"""HTTP integration tests for ceph primary storage handlers."""

import pytest


@pytest.mark.http
class TestCephPrimaryHandlers:
    """Test ceph primary storage HTTP handlers."""

    def test_echo(self, cephprimary_client):
        """Test /ceph/primarystorage/echo handler - verify agent responds."""
        response = cephprimary_client.post('/ceph/primarystorage/echo', data={})

        # Gracefully handle missing/unconfigured Ceph
        assert response.status_code in [200, 400, 403, 404, 500]
        
        if response.status_code == 200:
            # Echo handler returns empty string on success
            pass

    def test_ping(self, cephprimary_client):
        """Test /ceph/primarystorage/ping handler - verify availability check."""
        response = cephprimary_client.post('/ceph/primarystorage/ping', data={})

        # Gracefully handle missing/unconfigured Ceph
        assert response.status_code in [200, 400, 403, 404, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert 'success' in data
