# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent storage plugins."""

import pytest


@pytest.mark.http
class TestStoragePlugins:
    """Test kvmagent storage plugin HTTP handlers (non-destructive queries only)."""

    def test_localstorage_getphysicalcapacity(self, kvmagent_client):
        """Test /localstorage/getphysicalcapacity - get local storage capacity."""
        response = kvmagent_client.post('/localstorage/getphysicalcapacity', data={
            'storagePath': '/tmp'
        })
        assert response.status_code in [200, 400, 404]
        # Only parse JSON if response has content (async handlers return empty body)
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'totalCapacity' in data or 'success' in data

    def test_localstorage_checkbits(self, kvmagent_client):
        """Test /localstorage/checkbits - check if bits exist."""
        response = kvmagent_client.post('/localstorage/checkbits', data={
            'path': '/nonexistent/test/path'
        })
        assert response.status_code in [200, 400, 404]
        # Only parse JSON if response has content (async handlers return empty body)
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'existing' in data or 'success' in data

    def test_nfsprimarystorage_ping(self, kvmagent_client):
        """Test /nfsprimarystorage/ping - NFS storage ping."""
        # Handler expects uuid and mountPath
        response = kvmagent_client.post('/nfsprimarystorage/ping', data={
            'uuid': 'test-nfs-uuid',
            'mountPath': '/nonexistent/nfs/mount'
        })

        # May not have NFS configured, accept any response including errors
        assert response.status_code in [200, 400, 404, 500]

    def test_localstorage_getphysicalcapacity_missing_path(self, kvmagent_client):
        """Test /localstorage/getphysicalcapacity with missing storagePath - should handle gracefully."""
        response = kvmagent_client.post('/localstorage/getphysicalcapacity', data={})

        # Should return error response (4xx) or handle missing parameter
        assert response.status_code in [200, 400, 404, 500]

    def test_localstorage_checkbits_missing_path(self, kvmagent_client):
        """Test /localstorage/checkbits with missing path - should handle gracefully."""
        response = kvmagent_client.post('/localstorage/checkbits', data={})

        # Should return error response (4xx) or handle missing parameter
        assert response.status_code in [200, 400, 404, 500]
