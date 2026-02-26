# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent VM plugin."""

import pytest


@pytest.mark.http
class TestVMPlugin:
    """Test kvmagent VM plugin HTTP handlers (non-destructive queries only)."""
    
    def test_checkstate(self, kvmagent_client):
        """Test /vm/checkstate handler - check VM state.
        
        Tests the endpoint that verifies VM states. The handler requires
        vmUuids parameter. Since we may not have VMs in the test environment,
        we test with an empty UUID list which should still return a valid
        response structure.
        """
        # Test with empty UUID list - handler should accept and return empty states
        test_data = {'vmUuids': []}
        response = kvmagent_client.post('/vm/checkstate', data=test_data)
        
        # Handler should respond (200 OK) with valid response structure
        assert response.status_code == 200
        data = response.json()
        assert 'success' in data
        # Empty vmUuids should return empty states dict
        assert 'states' in data
    
    def test_getvncport(self, kvmagent_client):
        """Test /vm/getvncport handler - get VNC port for VM.
        
        Tests the endpoint that retrieves console (VNC/SPICE) port information.
        Without a valid VM UUID, the handler will fail gracefully with an error
        response (success=False). We verify the handler responds correctly.
        """
        # Test with missing/invalid vmUuid - expect graceful failure
        test_data = {}
        response = kvmagent_client.post('/vm/getvncport', data=test_data)
        
        # Handler should respond, may fail due to missing VM but endpoint exists
        # Accept both success (if default behavior) or failure (missing UUID)
        assert response.status_code == 200
        data = response.json()
        # Response should have success field (may be False due to missing VM)
        assert 'success' in data
    
    def test_getdeviceaddress(self, kvmagent_client):
        """Test /vm/getdeviceaddress handler - get device address.
        
        Tests the endpoint that retrieves device addresses for VM resources.
        The handler requires uuid and deviceTOs parameters. Without valid data,
        it will fail gracefully. We verify the endpoint is accessible.
        """
        # Test with minimal/empty data - expect graceful handling
        test_data = {}
        response = kvmagent_client.post('/vm/getdeviceaddress', data=test_data)
        
        # Handler should respond (endpoint exists and is routed)
        # May return error due to missing parameters, which is acceptable
        assert response.status_code == 200
        data = response.json()
        # Response should be JSON with success field
        assert 'success' in data
