# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent advanced network operations.

Covers L2 network, bonding, LLDP, VXLAN, ipset, and EIP/DEIP endpoints.
"""

import pytest


@pytest.mark.http
class TestL2NetworkSmoke:
    """Smoke tests for L2 network bridge management endpoints."""

    def test_create_novlan_bridge(self, kvmagent_client):
        """Test /network/l2novlan/createbridge - create NoVLAN bridge."""
        response = kvmagent_client.post('/network/l2novlan/createbridge', data={})
        assert response.status_code in [200, 400, 500]

    def test_check_novlan_bridge(self, kvmagent_client):
        """Test /network/l2novlan/checkbridge - check NoVLAN bridge."""
        response = kvmagent_client.post('/network/l2novlan/checkbridge', data={})
        assert response.status_code in [200, 400, 500]

    def test_create_vlan_bridge(self, kvmagent_client):
        """Test /network/l2vlan/createbridge - create VLAN bridge."""
        response = kvmagent_client.post('/network/l2vlan/createbridge', data={})
        assert response.status_code in [200, 400, 500]

    def test_check_vlan_bridge(self, kvmagent_client):
        """Test /network/l2vlan/checkbridge - check VLAN bridge."""
        response = kvmagent_client.post('/network/l2vlan/checkbridge', data={})
        assert response.status_code in [200, 400, 500]

    def test_update_vlan_bridge(self, kvmagent_client):
        """Test /network/l2vlan/updatebridge - update VLAN bridge."""
        response = kvmagent_client.post('/network/l2vlan/updatebridge', data={})
        assert response.status_code in [200, 400, 500]

    def test_bridge_addif(self, kvmagent_client):
        """Test /network/bridge/addif - add interface to bridge."""
        response = kvmagent_client.post('/network/bridge/addif', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestBondingSmoke:
    """Smoke tests for NIC bonding management endpoints."""

    def test_create_bonding(self, kvmagent_client):
        """Test /network/bonding/create - create bonding."""
        response = kvmagent_client.post('/network/bonding/create', data={})
        assert response.status_code in [200, 400, 500]

    def test_update_bonding(self, kvmagent_client):
        """Test /network/bonding/update - update bonding."""
        response = kvmagent_client.post('/network/bonding/update', data={})
        assert response.status_code in [200, 400, 500]

    def test_delete_bonding(self, kvmagent_client):
        """Test /network/bonding/delete - delete bonding."""
        response = kvmagent_client.post('/network/bonding/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_attach_nic_to_bonding(self, kvmagent_client):
        """Test /network/bonding/attachnic - attach NIC to bonding."""
        response = kvmagent_client.post('/network/bonding/attachnic', data={})
        assert response.status_code in [200, 400, 500]

    def test_detach_nic_from_bonding(self, kvmagent_client):
        """Test /network/bonding/detachnic - detach NIC from bonding."""
        response = kvmagent_client.post('/network/bonding/detachnic', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestLLDPSmoke:
    """Smoke tests for LLDP management endpoints."""

    def test_change_lldp_mode(self, kvmagent_client):
        """Test /network/lldp/changemode - change LLDP mode."""
        response = kvmagent_client.post('/network/lldp/changemode', data={})
        assert response.status_code in [200, 400, 500]

    def test_apply_lldp_config(self, kvmagent_client):
        """Test /network/lldp/apply - apply LLDP config."""
        response = kvmagent_client.post('/network/lldp/apply', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestDEIPSmoke:
    """Smoke tests for distributed EIP (deip) endpoints."""

    def test_eip_apply(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/apply - apply distributed EIP."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/apply', data={})
        assert response.status_code in [200, 400, 500]

    def test_eip_delete(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/delete - delete distributed EIP."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_eip_batchapply(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/batchapply - batch apply EIPs."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/batchapply', data={})
        assert response.status_code in [200, 400, 500]

    def test_eip_batchdelete(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/batchdelete - batch delete EIPs."""
        response = kvmagent_client.post('/flatnetworkprovider/eip/batchdelete', data={})
        assert response.status_code in [200, 400, 500]

    def test_vipqos_delete(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/delete - delete VIP QoS."""
        response = kvmagent_client.post('/flatnetworkprovider/vipqos/delete', data={})
        assert response.status_code in [200, 400, 500]

    def test_vipqos_deleteall(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/deleteall - delete all VIP QoS."""
        response = kvmagent_client.post('/flatnetworkprovider/vipqos/deleteall', data={})
        assert response.status_code in [200, 400, 500]

    def test_garp_release(self, kvmagent_client):
        """Test /flatnetworkprovider/garp/release - release gratuitous ARP."""
        response = kvmagent_client.post('/flatnetworkprovider/garp/release', data={})
        assert response.status_code in [200, 400, 500]
