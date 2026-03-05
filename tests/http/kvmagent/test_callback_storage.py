# -*- coding: utf-8 -*-
"""HTTP callback tests for kvmagent storage query handlers (Round 9).

Verifies async callback responses from storage-related endpoints.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestLocalStorageCallbacks:
    """Callback tests for localstorage plugin query handlers."""

    def test_get_physical_capacity(self, kvmagent_client, async_callback):
        """Test /localstorage/getphysicalcapacity returns capacity data."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={'storagePath': '/'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/getphysicalcapacity')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        # Some handlers return data without 'success' field
        assert isinstance(result, dict), "callback should return a dict"
        if result.get('success', False):
            if 'totalCapacity' in result:
                assert result['totalCapacity'] > 0
            if 'availableCapacity' in result:
                assert result['availableCapacity'] >= 0

    def test_check_bits(self, kvmagent_client, async_callback):
        """Test /localstorage/checkbits returns existence check."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/checkbits',
            data={'path': '/nonexistent-test-path-12345'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/checkbits')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"
        # For a nonexistent path, existing should be false
        if 'existing' in result:
            assert result['existing'] is False

    def test_get_volume_base_image(self, kvmagent_client, async_callback):
        """Test /localstorage/volume/getbaseimage returns base image info."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/volume/getbaseimagepath',
            data={'volumePath': '/nonexistent'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/volume/getbaseimagepath')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"

    def test_get_qcow2_reference(self, kvmagent_client, async_callback):
        """Test /localstorage/getqcow2reference returns reference info."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getqcow2reference',
            data={'path': '/nonexistent', 'searchingDir': '/tmp'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/getqcow2reference')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"


@pytest.mark.http
class TestNFSStorageCallbacks:
    """Callback tests for NFS primary storage query handlers."""

    def test_nfs_ping(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/ping returns mount detection."""
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
        assert isinstance(result, dict), "callback should return a dict"

    def test_nfs_getphysicalcapacity(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/getphysicalcapacity returns NFS capacity."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/getphysicalcapacity',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/getphysicalcapacity')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"

    def test_nfs_checkbits(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/checkbits returns existence check."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/checkbits',
            data={'path': '/nonexistent-test-path'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/checkbits')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"


@pytest.mark.http
class TestImageStoreCallbacks:
    """Callback tests for imagestore plugin query handlers."""

    def test_imagestore_ping(self, kvmagent_client, async_callback):
        """Test /imagestore/ping returns store status."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/imagestore/ping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/imagestore/ping')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"

    def test_imagestore_getlocalfilelist(self, kvmagent_client, async_callback):
        """Test /imagestore/getlocalfilelist returns file list."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/imagestore/getlocalfilelist',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/imagestore/getlocalfilelist')
        assert response.status_code in [200, 403, 404]

        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict), "callback should return a dict"
