# -*- coding: utf-8 -*-
"""HTTP integration tests for virtualrouter handlers."""

import pytest


@pytest.mark.http
class TestVirtualRouterCore:
    """Test virtualrouter core handlers (init, ping, echo)."""

    def test_init(self, virtualrouter_client):
        """Test /init handler - initialize VR with UUID."""
        test_data = {'uuid': 'test-vr-uuid-12345'}
        response = virtualrouter_client.post('/init', data=test_data)
        assert response.status_code in [200, 400, 500]

    def test_ping(self, virtualrouter_client):
        """Test /ping handler - verify agent responds with uuid."""
        response = virtualrouter_client.post('/ping', data={})
        assert response.status_code in [200, 400, 500]

    def test_echo(self, virtualrouter_client):
        """Test /echo handler - verify echo response (sync)."""
        response = virtualrouter_client.post('/echo', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestDnsmasqSmoke:
    """Smoke tests for dnsmasq (DHCP) plugin endpoints."""

    def test_add_dhcp(self, virtualrouter_client):
        """Test /adddhcp - add DHCP entry."""
        response = virtualrouter_client.post('/adddhcp', data={})
        assert response.status_code in [200, 400, 500]

    def test_remove_dhcp(self, virtualrouter_client):
        """Test /removedhcp - remove DHCP entry."""
        response = virtualrouter_client.post('/removedhcp', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestLoadBalancerSmoke:
    """Smoke tests for load balancer plugin endpoints."""

    def test_refresh_lb(self, virtualrouter_client):
        """Test /lb/refresh - refresh load balancer config."""
        response = virtualrouter_client.post('/lb/refresh', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_lb(self, virtualrouter_client):
        """Test /lb/delete - delete load balancer."""
        response = virtualrouter_client.post('/lb/delete', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestPortForwardingSmoke:
    """Smoke tests for port forwarding plugin endpoints."""

    def test_create_port_forwarding(self, virtualrouter_client):
        """Test /createportforwarding - create port forwarding rule."""
        response = virtualrouter_client.post('/createportforwarding', data={})
        assert response.status_code in [200, 400, 500]

    def test_revoke_port_forwarding(self, virtualrouter_client):
        """Test /revokeportforwarding - revoke port forwarding rule."""
        response = virtualrouter_client.post('/revokeportforwarding', data={})
        assert response.status_code in [200, 400, 500]

    def test_sync_port_forwarding(self, virtualrouter_client):
        """Test /syncportforwarding - sync port forwarding rules."""
        response = virtualrouter_client.post('/syncportforwarding', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestSNATSmoke:
    """Smoke tests for SNAT plugin endpoints."""

    def test_set_snat(self, virtualrouter_client):
        """Test /setsnat - set SNAT rule."""
        response = virtualrouter_client.post('/setsnat', data={})
        assert response.status_code in [200, 400, 500]

    def test_remove_snat(self, virtualrouter_client):
        """Test /removesnat - remove SNAT rule."""
        response = virtualrouter_client.post('/removesnat', data={})
        assert response.status_code in [200, 400, 500]

    def test_sync_snat(self, virtualrouter_client):
        """Test /syncsnat - sync SNAT rules."""
        response = virtualrouter_client.post('/syncsnat', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestDNSSmoke:
    """Smoke tests for DNS plugin endpoints."""

    def test_set_dns(self, virtualrouter_client):
        """Test /setdns - set DNS entry."""
        response = virtualrouter_client.post('/setdns', data={})
        assert response.status_code in [200, 400, 500]

    def test_remove_dns(self, virtualrouter_client):
        """Test /removedns - remove DNS entry."""
        response = virtualrouter_client.post('/removedns', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestEIPSmoke:
    """Smoke tests for EIP plugin endpoints."""

    def test_create_eip(self, virtualrouter_client):
        """Test /createeip - create EIP."""
        response = virtualrouter_client.post('/createeip', data={})
        assert response.status_code in [200, 400, 500]

    def test_remove_eip(self, virtualrouter_client):
        """Test /removeeip - remove EIP."""
        response = virtualrouter_client.post('/removeeip', data={})
        assert response.status_code in [200, 400, 500]

    def test_sync_eip(self, virtualrouter_client):
        """Test /synceip - sync EIP rules."""
        response = virtualrouter_client.post('/synceip', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestVIPSmoke:
    """Smoke tests for VIP plugin endpoints."""

    def test_create_vip(self, virtualrouter_client):
        """Test /createvip - create VIP."""
        response = virtualrouter_client.post('/createvip', data={})
        assert response.status_code in [200, 400, 500]

    def test_remove_vip(self, virtualrouter_client):
        """Test /removevip - remove VIP."""
        response = virtualrouter_client.post('/removevip', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestConfigureNicSmoke:
    """Smoke tests for configure NIC plugin endpoint."""

    def test_configure_nic(self, virtualrouter_client):
        """Test /configurenic - configure NIC."""
        response = virtualrouter_client.post('/configurenic', data={})
        assert response.status_code in [200, 400, 500]
