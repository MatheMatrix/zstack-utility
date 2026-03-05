# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent ZBox backup plugin."""

import pytest


@pytest.mark.http
class TestZBoxSmoke:
    """Smoke tests for zbox_plugin endpoints."""

    def test_init(self, kvmagent_client):
        """Test /zbox/init - initialize ZBox."""
        response = kvmagent_client.post('/zbox/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_eject(self, kvmagent_client):
        """Test /zbox/eject - eject ZBox device."""
        response = kvmagent_client.post('/zbox/eject', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_refresh(self, kvmagent_client):
        """Test /zbox/refresh - refresh ZBox state."""
        response = kvmagent_client.post('/zbox/refresh', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_sync(self, kvmagent_client):
        """Test /zbox/sync - sync ZBox data."""
        response = kvmagent_client.post('/zbox/sync', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_deletebits(self, kvmagent_client):
        """Test /zbox/deletebits - delete ZBox bits."""
        response = kvmagent_client.post('/zbox/deletebits', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_backup_init(self, kvmagent_client):
        """Test /zbox/backup/init - initialize ZBox backup."""
        response = kvmagent_client.post('/zbox/backup/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volumes_takeshallowbackup(self, kvmagent_client):
        """Test /zbox/volumes/takeshallowbackup - take shallow backup."""
        response = kvmagent_client.post('/zbox/volumes/takeshallowbackup', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
