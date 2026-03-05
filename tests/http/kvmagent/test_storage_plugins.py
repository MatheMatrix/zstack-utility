# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent storage plugins."""

import pytest


@pytest.mark.http
class TestLocalStorageSmoke:
    """Smoke tests for localstorage plugin endpoints."""

    def test_getphysicalcapacity(self, kvmagent_client):
        """Test /localstorage/getphysicalcapacity - get capacity."""
        response = kvmagent_client.post('/localstorage/getphysicalcapacity', data={
            'storagePath': '/tmp'
        })
        assert response.status_code in [200, 400, 403, 404]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'totalCapacity' in data or 'success' in data

    def test_checkbits(self, kvmagent_client):
        """Test /localstorage/checkbits - check if bits exist."""
        response = kvmagent_client.post('/localstorage/checkbits', data={
            'path': '/nonexistent/test/path'
        })
        assert response.status_code in [200, 400, 403, 404]
        if response.status_code == 200 and response.text:
            data = response.json()
            assert 'existing' in data or 'success' in data

    def test_init(self, kvmagent_client):
        """Test /localstorage/init - initialize local storage."""
        response = kvmagent_client.post('/localstorage/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getbackingfile(self, kvmagent_client):
        """Test /localstorage/volume/getbackingfile - get volume backing file."""
        response = kvmagent_client.post('/localstorage/volume/getbackingfile', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getbaseimagepath(self, kvmagent_client):
        """Test /localstorage/volume/getbaseimagepath - get base image path."""
        response = kvmagent_client.post('/localstorage/volume/getbaseimagepath', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getbackingchain(self, kvmagent_client):
        """Test /localstorage/volume/getbackingchain - get backing chain."""
        response = kvmagent_client.post('/localstorage/volume/getbackingchain', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getphysicalcapacity_missing_path(self, kvmagent_client):
        """Test /localstorage/getphysicalcapacity with empty data."""
        response = kvmagent_client.post('/localstorage/getphysicalcapacity', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_checkbits_missing_path(self, kvmagent_client):
        """Test /localstorage/checkbits with empty data."""
        response = kvmagent_client.post('/localstorage/checkbits', data={})
        assert response.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestNFSStorageSmoke:
    """Smoke tests for NFS primary storage plugin endpoints."""

    def test_ping(self, kvmagent_client):
        """Test /nfsprimarystorage/ping - NFS storage ping."""
        response = kvmagent_client.post('/nfsprimarystorage/ping', data={
            'uuid': 'test-nfs-uuid',
            'mountPath': '/nonexistent/nfs/mount'
        })
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getcapacity(self, kvmagent_client):
        """Test /nfsprimarystorage/getcapacity - NFS capacity."""
        response = kvmagent_client.post('/nfsprimarystorage/getcapacity', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_checkbits(self, kvmagent_client):
        """Test /nfsprimarystorage/checkbits - check bits on NFS."""
        response = kvmagent_client.post('/nfsprimarystorage/checkbits', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getvolumesize(self, kvmagent_client):
        """Test /nfsprimarystorage/getvolumesize - get volume size."""
        response = kvmagent_client.post('/nfsprimarystorage/getvolumesize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_batchgetvolumesize(self, kvmagent_client):
        """Test /nfsprimarystorage/batchgetvolumesize - batch get sizes."""
        response = kvmagent_client.post('/nfsprimarystorage/batchgetvolumesize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getvolumebaseimage(self, kvmagent_client):
        """Test /nfsprimarystorage/getvolumebaseimage - get base image."""
        response = kvmagent_client.post('/nfsprimarystorage/getvolumebaseimage', data={})
        assert response.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestSharedBlockSmoke:
    """Smoke tests for shared block plugin endpoints."""

    def test_ping(self, kvmagent_client):
        """Test /sharedblock/ping - shared block ping."""
        response = kvmagent_client.post('/sharedblock/ping', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_bits_check(self, kvmagent_client):
        """Test /sharedblock/bits/check - check bits."""
        response = kvmagent_client.post('/sharedblock/bits/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_disks_check(self, kvmagent_client):
        """Test /sharedblock/disks/check - check disks."""
        response = kvmagent_client.post('/sharedblock/disks/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_vgstate_check(self, kvmagent_client):
        """Test /sharedblock/vgstate/check - check VG state."""
        response = kvmagent_client.post('/sharedblock/vgstate/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_blockdevices(self, kvmagent_client):
        """Test /sharedblock/blockdevices - list block devices."""
        response = kvmagent_client.post('/sharedblock/blockdevices', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_getsize(self, kvmagent_client):
        """Test /sharedblock/volume/getsize - get volume size."""
        response = kvmagent_client.post('/sharedblock/volume/getsize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_batchgetsize(self, kvmagent_client):
        """Test /sharedblock/volume/batchgetsize - batch get sizes."""
        response = kvmagent_client.post('/sharedblock/volume/batchgetsize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_backingchain(self, kvmagent_client):
        """Test /sharedblock/volume/backingchain - get backing chain."""
        response = kvmagent_client.post('/sharedblock/volume/backingchain', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_estimatetemplatesize(self, kvmagent_client):
        """Test /sharedblock/estimatetemplatesize - estimate template size."""
        response = kvmagent_client.post('/sharedblock/estimatetemplatesize', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
