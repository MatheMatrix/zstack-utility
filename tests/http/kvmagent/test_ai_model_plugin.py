# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent AI Model Mount Plugin.

ZSTAC-83157: Tests for VM model mount functionality using JuiceFS.
"""

import pytest


@pytest.mark.http
@pytest.mark.kvmagent
class TestAIModelPlugin:
    """Test kvmagent AI Model Mount Plugin HTTP handlers."""

    def test_attach_model_endpoint_exists(self, kvmagent_client):
        """Test /aimodel/attach handler - mount AI model to VM (read-only).

        Tests the endpoint that mounts an AI model (via JuiceFS) to a VM
        in read-only mode. The handler requires vmInstanceUuid, zdfsUrl,
        juicefsSubdir, mountPath. No cacheDir is needed for read-only mounts.

        Without a valid VM UUID and Qemu Guest Agent, the handler will fail
        gracefully with an error response (success=False). We verify the
        handler responds correctly and the endpoint is accessible.
        """
        # Test with minimal data - expect graceful failure due to missing VM/QGA
        # Read-only mount: no cacheDir needed
        test_data = {
            'vmInstanceUuid': 'test-vm-uuid-does-not-exist',
            'zdfsUrl': 'redis://:password@192.168.1.100:6379/1',
            'juicefsSubdir': 'models/Qwen/2.5b',
            'mountPath': '/mnt/models/qwen'
        }
        response = kvmagent_client.post('/aimodel/attach', data=test_data)

        # Handler should respond (200 OK) even if operation fails
        assert response.status_code == 200
        data = response.json()

        # Response should have success field
        assert 'success' in data

        # Since VM doesn't exist, operation should fail
        assert data['success'] is False
        assert 'error' in data
        # Error message should indicate VM not found
        assert 'VM not found' in data['error'] or 'not found' in data['error'].lower()

    def test_detach_model_endpoint_exists(self, kvmagent_client):
        """Test /aimodel/detach handler - unmount AI model from VM.

        Tests the endpoint that unmounts an AI model from a VM.
        The handler requires vmInstanceUuid and mountPath.

        Without a valid VM UUID, the handler will fail gracefully.
        We verify the endpoint is accessible and responds correctly.
        """
        # Test with minimal data - expect graceful failure due to missing VM
        test_data = {
            'vmInstanceUuid': 'test-vm-uuid-does-not-exist',
            'mountPath': '/mnt/models/qwen'
        }
        response = kvmagent_client.post('/aimodel/detach', data=test_data)

        # Handler should respond (200 OK) even if operation fails
        assert response.status_code == 200
        data = response.json()

        # Response should have success field
        assert 'success' in data

        # Since VM doesn't exist, operation should fail
        assert data['success'] is False
        assert 'error' in data
        # Error message should indicate VM not found
        assert 'VM not found' in data['error'] or 'not found' in data['error'].lower()

    def test_attach_model_missing_parameters(self, kvmagent_client):
        """Test /aimodel/attach with missing required parameters.

        Verifies that the handler gracefully handles requests with
        missing or incomplete parameters.
        """
        # Test with empty data
        test_data = {}
        response = kvmagent_client.post('/aimodel/attach', data=test_data)

        # Handler should respond
        assert response.status_code == 200
        data = response.json()
        assert 'success' in data

    def test_detach_model_missing_parameters(self, kvmagent_client):
        """Test /aimodel/detach with missing required parameters.

        Verifies that the handler gracefully handles requests with
        missing parameters.
        """
        # Test with empty data
        test_data = {}
        response = kvmagent_client.post('/aimodel/detach', data=test_data)

        # Handler should respond
        assert response.status_code == 200
        data = response.json()
        assert 'success' in data

    def test_attach_model_response_structure(self, kvmagent_client):
        """Test /aimodel/attach response structure (read-only mount).

        Verifies that the response contains expected fields regardless
        of success or failure. Read-only mounts don't require cacheDir.
        """
        test_data = {
            'vmInstanceUuid': 'test-vm-uuid',
            'zdfsUrl': 'redis://127.0.0.1:6379/1',
            'juicefsSubdir': 'models/test',
            'mountPath': '/mnt/test'
        }
        response = kvmagent_client.post('/aimodel/attach', data=test_data)

        assert response.status_code == 200
        data = response.json()

        # Response must have success field
        assert 'success' in data
        assert isinstance(data['success'], bool)

        # If failed, should have error message
        if not data['success']:
            assert 'error' in data
            assert isinstance(data['error'], str)

    def test_detach_model_response_structure(self, kvmagent_client):
        """Test /aimodel/detach response structure.

        Verifies that the response contains expected fields regardless
        of success or failure.
        """
        test_data = {
            'vmInstanceUuid': 'test-vm-uuid',
            'mountPath': '/mnt/test'
        }
        response = kvmagent_client.post('/aimodel/detach', data=test_data)

        assert response.status_code == 200
        data = response.json()

        # Response must have success field
        assert 'success' in data
        assert isinstance(data['success'], bool)

        # If failed, should have error message
        if not data['success']:
            assert 'error' in data
            assert isinstance(data['error'], str)
