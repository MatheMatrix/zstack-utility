# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent network plugin."""

import pytest


@pytest.mark.http
class TestNetworkPluginSmoke:
    """Smoke tests for network_plugin endpoints."""

    def test_checkphysicalnetworkinterface(self, kvmagent_client):
        """Test /network/checkphysicalnetworkinterface - check physical NIC (sync)."""
        response = kvmagent_client.post('/network/checkphysicalnetworkinterface', data={})
        assert response.status_code in [200, 400, 500]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'success' in data

    def test_lldp_get(self, kvmagent_client):
        """Test /network/lldp/get - get LLDP information."""
        response = kvmagent_client.post('/network/lldp/get', data={})
        assert response.status_code in [200, 400, 500]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'success' in data


@pytest.mark.http
class TestSecurityGroupSmoke:
    """Smoke tests for securitygroup_plugin endpoints."""

    def test_checkdefaultrulesonhost(self, kvmagent_client):
        """Test /securitygroup/checkdefaultrulesonhost - check default rules."""
        response = kvmagent_client.post('/securitygroup/checkdefaultrulesonhost', data={})
        assert response.status_code in [200, 400, 500]

    def test_applyrules(self, kvmagent_client):
        """Test /securitygroup/applyrules - apply security group rules."""
        response = kvmagent_client.post('/securitygroup/applyrules', data={})
        assert response.status_code in [200, 400, 500]

    def test_cleanupunusedrules(self, kvmagent_client):
        """Test /securitygroup/cleanupunusedrules - cleanup unused rules."""
        response = kvmagent_client.post('/securitygroup/cleanupunusedrules', data={})
        assert response.status_code in [200, 400, 500]

    def test_refreshrulesonhost(self, kvmagent_client):
        """Test /securitygroup/refreshrulesonhost - refresh rules."""
        response = kvmagent_client.post('/securitygroup/refreshrulesonhost', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestDHCPSmoke:
    """Smoke tests for mevoco (flat network DHCP) endpoints."""

    def test_dhcp_connect(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/connect - DHCP connect."""
        response = kvmagent_client.post('/flatnetworkprovider/dhcp/connect', data={})
        assert response.status_code in [200, 400, 500]

    def test_arping(self, kvmagent_client):
        """Test /flatnetworkprovider/arping - ARP ping."""
        response = kvmagent_client.post('/flatnetworkprovider/arping', data={})
        assert response.status_code in [200, 400, 500]

    def test_dns_forward_set(self, kvmagent_client):
        """Test /dns/forward/set - set DNS forward."""
        response = kvmagent_client.post('/dns/forward/set', data={})
        assert response.status_code in [200, 400, 500]

    def test_dns_forward_remove(self, kvmagent_client):
        """Test /dns/forward/remove - remove DNS forward."""
        response = kvmagent_client.post('/dns/forward/remove', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestEIPSmoke:
    """Smoke tests for EIP/VIP QoS endpoints."""

    def test_eip_apply(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/apply - apply EIP."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/apply', data={})
        assert response.status_code in [200, 400, 500]

    def test_eip_delete(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/delete - delete EIP."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_vipqos_apply(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/apply - apply VIP QoS."""
        response = kvmagent_client.post('/flatnetworkprovider/vipqos/apply', data={})
        assert response.status_code in [200, 400, 500]

    def test_garp_apply(self, kvmagent_client):
        """Test /flatnetworkprovider/garp/apply - apply Gratuitous ARP."""
        response = kvmagent_client.post('/flatnetworkprovider/garp/apply', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestHAPluginSmoke:
    """Smoke tests for HA plugin endpoints."""

    def test_selffencer_state(self, kvmagent_client):
        """Test /ha/selffencer/state - get self-fencer state."""
        response = kvmagent_client.post('/ha/selffencer/state', data={})
        assert response.status_code in [200, 400, 500]

    def test_scanhost(self, kvmagent_client):
        """Test /ha/scanhost - scan host HA status."""
        response = kvmagent_client.post('/ha/scanhost', data={})
        assert response.status_code in [200, 400, 500]
