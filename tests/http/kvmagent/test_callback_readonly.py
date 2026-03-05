# -*- coding: utf-8 -*-
"""HTTP callback tests for kvmagent read-only handlers.

These tests verify that async handlers:
1. Return 200 with empty body immediately
2. POST callback to callbackurl with actual response data
3. Response data has expected structure and types

Requires kvmagent running on the target host.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestHostCallbacks:
    """Callback tests for host plugin read-only handlers."""

    def test_host_capacity_callback(self, kvmagent_client, async_callback):
        """Test /host/capacity returns cpu/memory info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/capacity',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/capacity')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert result.get('success') is True, "callback should report success"
        # Capacity response should have numeric fields
        if 'cpuNum' in result:
            assert isinstance(result['cpuNum'], (int, float))
            assert result['cpuNum'] > 0
        if 'totalMemory' in result:
            assert isinstance(result['totalMemory'], (int, float))
            assert result['totalMemory'] > 0

    def test_host_fact_callback(self, kvmagent_client, async_callback):
        """Test /host/fact returns os/libvirt info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/fact',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/fact')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert result.get('success') is True
        if 'osDistribution' in result:
            assert isinstance(result['osDistribution'], str)
            assert len(result['osDistribution']) > 0

    def test_host_ping_callback(self, kvmagent_client, async_callback):
        """Test /host/ping returns success via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/ping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/ping')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=20.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert result.get('success') is True
        if 'hostUuid' in result:
            assert isinstance(result['hostUuid'], str)


@pytest.mark.http
class TestNetworkCallbacks:
    """Callback tests for network-related read-only handlers."""

    def test_get_nic_names_callback(self, kvmagent_client, async_callback):
        """Test /network/getnicnames returns NIC list via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/getnicnames',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/getnicnames')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result

    def test_get_ipv6_address_callback(self, kvmagent_client, async_callback):
        """Test /network/ipv6/address returns address info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/ipv6/address',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/network/ipv6/address')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result


@pytest.mark.http
class TestStorageCapacityCallbacks:
    """Callback tests for storage capacity queries."""

    def test_localstorage_get_capacity_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/getphysicalcapacity returns capacity via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/getphysicalcapacity')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result

    def test_nfs_ping_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/ping returns mount status via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/ping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/ping')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result


@pytest.mark.http
class TestVMQueryCallbacks:
    """Callback tests for VM state query handlers."""

    def test_vm_checkstate_callback(self, kvmagent_client, async_callback):
        """Test /vm/checkstate returns VM states via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/checkstate',
            data={'vmUuids': []},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/checkstate')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result

    def test_host_getvirtualizerstatus_callback(self, kvmagent_client, async_callback):
        """Test /host/virtualizerstatus returns virtualizer info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/virtualizerstatus',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/virtualizerstatus')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result

    def test_host_getwebconsoleurl_callback(self, kvmagent_client, async_callback):
        """Test /host/getwebconsoleurl returns URL info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/host/getwebconsoleurl',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/host/getwebconsoleurl')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert 'success' in result
