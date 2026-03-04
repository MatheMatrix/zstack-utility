# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Unit tests for appliancevm agent response models and class structure.

Tests for AgentResponse, RefreshFirewallRsp, and ApplianceVm path constants.
All zstacklib dependencies are mocked by root conftest.py.
"""
import pytest

from appliancevm.appliancevm import AgentResponse, RefreshFirewallRsp, ApplianceVm


@pytest.mark.appliancevm
class TestApplianceVmResponses:
    """Test suite for appliancevm AgentResponse model behavior."""

    def test_agent_response_default_success(self):
        """AgentResponse() defaults to success=True, error=''."""
        rsp = AgentResponse()

        assert rsp.success is True
        assert rsp.error == ''

    def test_agent_response_with_error(self):
        """AgentResponse stores error message when provided."""
        rsp = AgentResponse(success=False, error='firewall rule failed')

        assert rsp.success is False
        assert rsp.error == 'firewall rule failed'

    def test_agent_response_falsy_error_becomes_empty_string(self):
        """AgentResponse converts falsy error values to empty string."""
        rsp = AgentResponse(success=True, error=None)
        assert rsp.error == ''

        rsp2 = AgentResponse(success=True, error='')
        assert rsp2.error == ''

    def test_refresh_firewall_rsp_inherits_agent_response(self):
        """RefreshFirewallRsp inherits AgentResponse defaults."""
        rsp = RefreshFirewallRsp()

        assert isinstance(rsp, AgentResponse)
        assert rsp.success is True
        assert rsp.error == ''


@pytest.mark.appliancevm
class TestApplianceVmStructure:
    """Test suite for ApplianceVm class constants and structure."""

    def test_path_constants_defined(self):
        """ApplianceVm defines required HTTP path constants."""
        assert ApplianceVm.REFRESH_FIREWALL_PATH == '/appliancevm/refreshfirewall'
        assert ApplianceVm.ECHO_PATH == '/appliancevm/echo'
        assert ApplianceVm.INIT_PATH == '/appliancevm/init'

    def test_http_server_exists(self):
        """ApplianceVm has an http_server class attribute."""
        assert hasattr(ApplianceVm, 'http_server')

    def test_class_is_instantiable(self):
        """ApplianceVm can be instantiated."""
        vm = ApplianceVm()
        assert vm is not None
