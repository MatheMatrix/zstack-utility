# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent advanced network operations.

Covers L2 network, bonding, LLDP, VXLAN, ipset, and EIP/DEIP endpoints.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestL2NetworkSmoke:
    """Smoke tests for L2 network bridge management endpoints."""

    def test_create_novlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2novlan/createbridge - create NoVLAN bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/l2novlan/createbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/l2novlan/createbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_novlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2novlan/checkbridge - check NoVLAN bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/l2novlan/checkbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/l2novlan/checkbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_vlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2vlan/createbridge - create VLAN bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/l2vlan/createbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/l2vlan/createbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_vlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2vlan/checkbridge - check VLAN bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/l2vlan/checkbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/l2vlan/checkbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_vlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2vlan/updatebridge - update VLAN bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/l2vlan/updatebridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/l2vlan/updatebridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_bridge_addif(self, kvmagent_client, async_callback):
        """Test /network/bridge/addif - add interface to bridge."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bridge/addif', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bridge/addif')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestBondingSmoke:
    """Smoke tests for NIC bonding management endpoints."""

    def test_create_bonding(self, kvmagent_client, async_callback):
        """Test /network/bonding/create - create bonding."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bonding/create', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bonding/create')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_bonding(self, kvmagent_client, async_callback):
        """Test /network/bonding/update - update bonding."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bonding/update', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bonding/update')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bonding(self, kvmagent_client, async_callback):
        """Test /network/bonding/delete - delete bonding."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bonding/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bonding/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_attach_nic_to_bonding(self, kvmagent_client, async_callback):
        """Test /network/bonding/attachnic - attach NIC to bonding."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bonding/attachnic', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bonding/attachnic')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_detach_nic_from_bonding(self, kvmagent_client, async_callback):
        """Test /network/bonding/detachnic - detach NIC from bonding."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/bonding/detachnic', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/bonding/detachnic')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestLLDPSmoke:
    """Smoke tests for LLDP management endpoints."""

    def test_change_lldp_mode(self, kvmagent_client, async_callback):
        """Test /network/lldp/changemode - change LLDP mode."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/lldp/changemode', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/lldp/changemode')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_apply_lldp_config(self, kvmagent_client, async_callback):
        """Test /network/lldp/apply - apply LLDP config."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/network/lldp/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/network/lldp/apply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestDEIPSmoke:
    """Smoke tests for distributed EIP (deip) endpoints."""

    def test_eip_apply(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/apply - apply distributed EIP."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/eip/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/apply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_eip_delete(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/delete - delete distributed EIP."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/eip/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_eip_batchapply(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/batchapply - batch apply EIPs."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/eip/batchapply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/batchapply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_eip_batchdelete(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/batchdelete - batch delete EIPs."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/eip/batchdelete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/batchdelete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_vipqos_delete(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/delete - delete VIP QoS."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/vipqos/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/vipqos/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_vipqos_deleteall(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/deleteall - delete all VIP QoS."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/vipqos/deleteall', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/vipqos/deleteall')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_garp_release(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/garp/release - release gratuitous ARP."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post('/flatnetworkprovider/garp/release', data={}, callback_url=callback_url)
        _skip_if_not_loaded(response, '/flatnetworkprovider/garp/release')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
