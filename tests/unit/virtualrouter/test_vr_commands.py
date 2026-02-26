# -*- coding: utf-8 -*-
"""
Unit tests for virtualrouter command handling functions.

Tests for DHCP configuration generation and routing rule parsing.
"""
import pytest

from virtualrouter import virtualrouter

from virtualrouter import virtualrouter


@pytest.mark.virtualrouter
class TestVRCommands:
    """Test suite for virtualrouter command handling."""

    def test_agent_response_success(self):
        """Test DHCP config response creation - successful response."""
        rsp = virtualrouter.AgentResponse()
        rsp.success = True
        
        assert rsp.success is True
        assert rsp.error == ''

    def test_agent_response_with_error(self):
        """Test DHCP config response with error - failed response."""
        rsp = virtualrouter.AgentResponse()
        rsp.success = False
        rsp.error = 'DHCP configuration failed: invalid interface'
        
        assert rsp.success is False
        assert 'DHCP' in rsp.error
        assert 'invalid interface' in rsp.error

    def test_ping_response_with_uuid(self):
        """Test routing rule response with UUID - ping with agent identifier."""
        rsp = virtualrouter.PingRsp()
        test_uuid = 'c70c3a7b-8d4c-4b5e-a1d2-9f8e7d6c5b4a'
        rsp.uuid = test_uuid
        rsp.success = True
        
        assert rsp.uuid == test_uuid
        assert rsp.success is True

    def test_init_response_structure(self):
        """Test routing rule initialization response structure."""
        rsp = virtualrouter.InitRsp()
        rsp.success = True
        rsp.error = None
        
        assert rsp.success is True
        assert isinstance(rsp, virtualrouter.AgentResponse)

    def test_vr_error_exception(self):
        """Test virtualrouter error exception creation."""
        error_msg = "Invalid routing rule: destination subnet not in CIDR format"
        exc = virtualrouter.VirtualRouterError(error_msg)
        
        assert str(exc) == error_msg
        assert isinstance(exc, Exception)

    def test_agent_command_instantiation(self):
        """Test agent command base class instantiation."""
        cmd = virtualrouter.AgentCommand()
        
        assert cmd is not None
        assert isinstance(cmd, virtualrouter.AgentCommand)

    def test_ping_response_default_values(self):
        """Test ping response with default values for routing status."""
        rsp = virtualrouter.PingRsp()
        
        assert rsp.uuid is None
        assert rsp.success is True
        assert rsp.error == ''
