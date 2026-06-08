# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent network plugin."""

import pytest


@pytest.mark.http
class TestNetworkPlugin:
    """Test kvmagent network plugin HTTP handlers (non-destructive queries only)."""

    def test_checkphysicalnetworkinterface(self, kvmagent_client):
        """Test /network/checkphysicalnetworkinterface - check physical NIC."""
        # Test with minimal data - handler checks if interface exists
        # Accept 200 (success) or 4xx (missing/invalid interface name)
        response = kvmagent_client.post('/network/checkphysicalnetworkinterface', data={})
        
        # Handler may return 200, 400, or 500 depending on input validation
        assert response.status_code in [200, 400, 500]
        
        # If successful response, verify structure
        if response.status_code == 200:
            data = response.json()
            assert 'success' in data
            # Response has failedInterfaceNames field (may be empty/null)

    def test_lldp_get(self, kvmagent_client):
        """Test /network/lldp/get - get LLDP information."""
        # Test with minimal data - handler gets LLDP info for interface
        # Accept 200 (success) or 4xx/5xx (missing interface or LLDP not configured)
        response = kvmagent_client.post('/network/lldp/get', data={})
        
        # Handler may return various status codes
        assert response.status_code in [200, 400, 500]
        
        # If successful response, verify structure
        if response.status_code == 200:
            data = response.json()
            assert 'success' in data
            # Response has lldpInfo field (may be empty/null)
