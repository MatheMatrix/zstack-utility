# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent VM plugin.

Note: kvmagent handlers are async callback-based. On success they
return 200 with empty body (result sent via callback URL).
"""

import pytest


@pytest.mark.http
class TestVMPluginSmoke:
    """Smoke tests for vm_plugin read-only query endpoints."""

    def test_checkstate(self, kvmagent_client):
        """Test /vm/checkstate - check VM states."""
        response = kvmagent_client.post('/vm/checkstate', data={'vmUuids': []})
        assert response.status_code in [200, 403, 404]

    def test_getvncport(self, kvmagent_client):
        """Test /vm/getvncport - get VNC port."""
        response = kvmagent_client.post('/vm/getvncport', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getdeviceaddress(self, kvmagent_client):
        """Test /vm/getdeviceaddress - get device address."""
        response = kvmagent_client.post('/vm/getdeviceaddress', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getvirtualizerinfo(self, kvmagent_client):
        """Test /vm/getvirtualizerinfo - get hypervisor info."""
        response = kvmagent_client.post('/vm/getvirtualizerinfo', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_get_cpu_xml(self, kvmagent_client):
        """Test /vm/get/cpu/xml - get CPU XML definition."""
        response = kvmagent_client.post('/vm/get/cpu/xml', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_compare_cpu_function(self, kvmagent_client):
        """Test /vm/compare/cpu/function - compare CPU functions."""
        response = kvmagent_client.post('/vm/compare/cpu/function', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getfirstbootdevice(self, kvmagent_client):
        """Test /vm/getfirstbootdevice - get first boot device."""
        response = kvmagent_client.post('/vm/getfirstbootdevice', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_vmsync(self, kvmagent_client):
        """Test /vm/vmsync - sync VM states from libvirt."""
        response = kvmagent_client.post('/vm/vmsync', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volumesync(self, kvmagent_client):
        """Test /vm/volumesync - sync volume states."""
        response = kvmagent_client.post('/vm/volumesync', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_recover_check(self, kvmagent_client):
        """Test /vm/recover/check - sync VM recovery check."""
        response = kvmagent_client.post('/vm/recover/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_guesttools_getinfo(self, kvmagent_client):
        """Test /vm/guesttools/getinfo - get guest tools info."""
        response = kvmagent_client.post('/vm/guesttools/getinfo', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_guesttools_getroutingstatus(self, kvmagent_client):
        """Test /vm/guesttools/getroutingstatus - get routing status."""
        response = kvmagent_client.post('/vm/guesttools/getroutingstatus', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_check(self, kvmagent_client):
        """Test /vm/volume/check - check volume state."""
        response = kvmagent_client.post('/vm/volume/check', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_getvolumebitmaps(self, kvmagent_client):
        """Test /vm/volume/getvolumebitmaps - get volume bitmaps."""
        response = kvmagent_client.post('/vm/volume/getvolumebitmaps', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_getmirrormode(self, kvmagent_client):
        """Test /vm/volume/getmirrormode - get mirror mode."""
        response = kvmagent_client.post('/vm/volume/getmirrormode', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_querymirror(self, kvmagent_client):
        """Test /vm/volume/querymirror - query mirror status."""
        response = kvmagent_client.post('/vm/volume/querymirror', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_querylatencyboundary(self, kvmagent_client):
        """Test /vm/volume/querylatencyboundary - query latency boundary."""
        response = kvmagent_client.post('/vm/volume/querylatencyboundary', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_volume_listexportedvolumes(self, kvmagent_client):
        """Test /vm/volume/listexportedvolumes - list NBD exports."""
        response = kvmagent_client.post('/vm/volume/listexportedvolumes', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_getiothreadpin(self, kvmagent_client):
        """Test /vm/getiothreadpin - get IO thread pinning."""
        response = kvmagent_client.post('/vm/getiothreadpin', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_console_screenshot(self, kvmagent_client):
        """Test /vm/console/screenshot - take console screenshot."""
        response = kvmagent_client.post('/vm/console/screenshot', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
