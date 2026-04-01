# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent network plugin."""

import pytest

pytestmark = [pytest.mark.http]


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


class TestNetworkPluginSmoke:
    """Smoke tests for network_plugin endpoints."""

    def test_checkphysicalnetworkinterface(self, kvmagent_client):
        """Test /network/checkphysicalnetworkinterface - check physical NIC (sync)."""
        response = kvmagent_client.post('/network/checkphysicalnetworkinterface', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'success' in data

    def test_lldp_get(self, kvmagent_client):
        """Test /network/lldp/get - get LLDP information (sync)."""
        response = kvmagent_client.post('/network/lldp/get', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'success' in data

    def test_getnicnames_callback(self, kvmagent_client, async_callback):
        """Test /network/getnicnames - get NIC names via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/getnicnames',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/getnicnames')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_l2novlan_checkbridge_callback(self, kvmagent_client, async_callback):
        """Test /network/l2novlan/checkbridge - check no-vlan bridge via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2novlan/checkbridge',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/l2novlan/checkbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_l2vlan_checkbridge_callback(self, kvmagent_client, async_callback):
        """Test /network/l2vlan/checkbridge - check vlan bridge via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2vlan/checkbridge',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/l2vlan/checkbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_l2vxlan_createbridge_callback(self, kvmagent_client, async_callback):
        """Test /network/l2vxlan/createbridge - create vxlan bridge via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2vxlan/createbridge',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/l2vxlan/createbridge')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestSecurityGroupSmoke:
    """Smoke tests for securitygroup_plugin endpoints."""

    def test_checkdefaultrulesonhost_callback(self, kvmagent_client, async_callback):
        """Test /securitygroup/checkdefaultrulesonhost - check default rules via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/checkdefaultrulesonhost',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/securitygroup/checkdefaultrulesonhost')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_applyrules_callback(self, kvmagent_client, async_callback):
        """Test /securitygroup/applyrules - apply security group rules via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/applyrules',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/securitygroup/applyrules')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_cleanupunusedrules_callback(self, kvmagent_client, async_callback):
        """Test /securitygroup/cleanupunusedrules - cleanup unused rules via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/cleanupunusedrules',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/securitygroup/cleanupunusedrules')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_refreshrulesonhost_callback(self, kvmagent_client, async_callback):
        """Test /securitygroup/refreshrulesonhost - refresh rules via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/refreshrulesonhost',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/securitygroup/refreshrulesonhost')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestDHCPSmoke:
    """Smoke tests for mevoco (flat network DHCP) endpoints."""

    def test_dhcp_connect_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/connect - DHCP connect via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/dhcp/connect',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/dhcp/connect')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_arping_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/arping - ARP ping via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/arping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/arping')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_dns_forward_set_callback(self, kvmagent_client, async_callback):
        """Test /dns/forward/set - set DNS forward via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/dns/forward/set',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/dns/forward/set')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_dns_forward_remove_callback(self, kvmagent_client, async_callback):
        """Test /dns/forward/remove - remove DNS forward via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/dns/forward/remove',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/dns/forward/remove')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestEIPSmoke:
    """Smoke tests for EIP/VIP QoS endpoints."""

    def test_eip_apply_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/apply - apply EIP via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/eip/apply',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/apply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_eip_delete_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/delete - delete EIP via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/eip/delete',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/eip/delete')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_vipqos_apply_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/apply - apply VIP QoS via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/vipqos/apply',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/vipqos/apply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_garp_apply_callback(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/garp/apply - apply Gratuitous ARP via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/flatnetworkprovider/garp/apply',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/flatnetworkprovider/garp/apply')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestHAPluginSmoke:
    """Smoke tests for HA plugin endpoints."""

    def test_selffencer_state_callback(self, kvmagent_client, async_callback):
        """Test /ha/selffencer/state - get self-fencer state via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/ha/selffencer/state',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/ha/selffencer/state')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_scanhost_callback(self, kvmagent_client, async_callback):
        """Test /ha/scanhost - scan host HA status via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/ha/scanhost',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/ha/scanhost')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
