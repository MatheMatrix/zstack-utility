# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Unit tests for apibinding model serialization and deserialization.

Tests for API request building and response parsing.
"""
import pytest

from apibinding import api


@pytest.mark.apibinding
class TestApiModels:
    """Test suite for API binding model serialization/deserialization."""

    def test_error_code_to_string_none(self):
        """Test response parsing with None error - successful API call."""
        result = api.error_code_to_string(None)
        
        assert result == ''
        assert isinstance(result, str)

    def test_error_code_to_string_with_error(self):
        """Test response parsing with error object - failed API response."""
        # Create a mock error object
        class MockError:
            code = 'OPERATION_FAILED'
            description = 'Operation not supported'
            details = 'The requested operation is not available in this configuration'
        
        error = MockError()
        result = api.error_code_to_string(error)
        
        assert 'OPERATION_FAILED' in result
        assert 'Operation not supported' in result
        assert 'requested operation' in result

    def test_api_initialization(self):
        """Test API request building with default initialization."""
        api_instance = api.Api()
        
        assert api_instance is not None
        assert 'localhost' in api_instance.api_url or '127.0.0.1' in api_instance.api_url
        assert '8080' in api_instance.api_url
        assert '/zstack/api' in api_instance.api_url

    def test_api_custom_host_port(self):
        """Test API request building with custom host and port."""
        custom_host = '192.168.1.100'
        custom_port = 9999
        api_instance = api.Api(host=custom_host, port=custom_port)
        
        assert api_instance is not None
        assert custom_host in api_instance.api_url
        assert str(custom_port) in api_instance.api_url

    def test_api_error_exception(self):
        """Test response parsing error exception."""
        error_msg = "Invalid API response: unexpected JSON format"
        exc = api.ApiError(error_msg)
        
        assert str(exc) == error_msg
        assert isinstance(exc, Exception)

    def test_api_custom_paths(self):
        """Test API request building with custom API paths."""
        custom_api_path = '/custom/api/path'
        custom_result_path = '/custom/result/path'
        
        api_instance = api.Api(
            host='localhost',
            port=8080,
            api_path=custom_api_path,
            result_path=custom_result_path
        )
        
        assert custom_api_path in api_instance.api_url
        assert custom_result_path in api_instance.api_result_url

    def test_error_code_to_string_missing_fields(self):
        """Test response parsing with missing error fields - graceful handling."""
        class MinimalError:
            pass
        
        error = MinimalError()
        result = api.error_code_to_string(error)
        
        # Should use defaults for missing attributes
        assert 'UNKNOWN' in result
        assert 'No description' in result
        assert 'No details' in result

    def test_api_curl_flag(self):
        """Test API request building with curl debugging enabled."""
        api_instance = api.Api(host='localhost', port=8080, curl=True)
        
        assert api_instance.curl is True
        assert api_instance is not None
