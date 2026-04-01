# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent storage plugins."""

import pytest

pytestmark = [pytest.mark.http]


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


class TestLocalStorageSmoke:
    """Smoke tests for localstorage plugin endpoints."""

    def test_getphysicalcapacity_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/getphysicalcapacity - get capacity via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={'storagePath': '/'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/getphysicalcapacity')
        assert response.status_code in [200, 400, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_checkbits_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/checkbits - check if bits exist via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/checkbits',
            data={'path': '/tmp/nonexistent'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/checkbits')
        assert response.status_code in [200, 400, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getqcow2reference_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/getqcow2reference - get qcow2 reference via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/getqcow2reference',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/getqcow2reference')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_init_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/init - initialize local storage via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/init',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/init')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getbackingfile_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/volume/getbackingfile - get volume backing file via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/volume/getbackingfile',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/volume/getbackingfile')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getbaseimagepath_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/volume/getbaseimagepath - get base image path via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/volume/getbaseimagepath',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/volume/getbaseimagepath')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getbackingchain_callback(self, kvmagent_client, async_callback):
        """Test /localstorage/volume/getbackingchain - get backing chain via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/localstorage/volume/getbackingchain',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/localstorage/volume/getbackingchain')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestNFSStorageSmoke:
    """Smoke tests for NFS primary storage plugin endpoints."""

    def test_ping_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/ping - NFS storage ping via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/ping',
            data={'uuid': 'test-nfs-uuid', 'mountPath': '/nonexistent/nfs/mount'},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/ping')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getcapacity_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/getcapacity - NFS capacity via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/getcapacity',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/getcapacity')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_checkbits_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/checkbits - check bits on NFS via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/checkbits',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/checkbits')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getvolumesize_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/getvolumesize - get volume size via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/getvolumesize',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/getvolumesize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_batchgetvolumesize_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/batchgetvolumesize - batch get sizes via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/batchgetvolumesize',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/batchgetvolumesize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getvolumebaseimage_callback(self, kvmagent_client, async_callback):
        """Test /nfsprimarystorage/getvolumebaseimage - get base image via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/nfsprimarystorage/getvolumebaseimage',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/nfsprimarystorage/getvolumebaseimage')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestSharedBlockSmoke:
    """Smoke tests for shared block plugin endpoints."""

    def test_ping_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/ping - shared block ping via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/ping',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/ping')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_bits_check_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/bits/check - check bits via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/bits/check',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/bits/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_disks_check_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/disks/check - check disks via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/disks/check',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/disks/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_vgstate_check_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/vgstate/check - check VG state via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/vgstate/check',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/vgstate/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_blockdevices_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/blockdevices - list block devices via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/blockdevices',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/blockdevices')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_getsize_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/volume/getsize - get volume size via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/volume/getsize',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/volume/getsize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_batchgetsize_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/volume/batchgetsize - batch get sizes via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/volume/batchgetsize',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/volume/batchgetsize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_backingchain_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/volume/backingchain - get backing chain via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/volume/backingchain',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/volume/backingchain')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_estimatetemplatesize_callback(self, kvmagent_client, async_callback):
        """Test /sharedblock/estimatetemplatesize - estimate template size via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/sharedblock/estimatetemplatesize',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/sharedblock/estimatetemplatesize')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
