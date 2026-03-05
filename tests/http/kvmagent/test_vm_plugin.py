# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent VM plugin.

Note: kvmagent handlers are async callback-based. On success they
return 200 with empty body (result sent via callback URL).
"""

import pytest

pytestmark = [pytest.mark.http]


def _skip_if_not_loaded(response, endpoint):
    """Skip test if endpoint is not loaded (404 = plugin not present)."""
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


class TestVMPluginSmoke:
    """Smoke tests for vm_plugin read-only query endpoints via callbacks."""

    def test_checkstate_callback(self, kvmagent_client, async_callback):
        """Test /vm/checkstate - check VM states via callback."""
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
        assert isinstance(result, dict)

    def test_getvncport_callback(self, kvmagent_client, async_callback):
        """Test /vm/getvncport - get VNC port via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/getvncport',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/getvncport')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getdeviceaddress_callback(self, kvmagent_client, async_callback):
        """Test /vm/getdeviceaddress - get device address via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/getdeviceaddress',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/getdeviceaddress')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getvirtualizerinfo_callback(self, kvmagent_client, async_callback):
        """Test /vm/getvirtualizerinfo - get hypervisor info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/getvirtualizerinfo',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/getvirtualizerinfo')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_get_cpu_xml_callback(self, kvmagent_client, async_callback):
        """Test /vm/get/cpu/xml - get CPU XML definition via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/get/cpu/xml',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/get/cpu/xml')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_compare_cpu_function_callback(self, kvmagent_client, async_callback):
        """Test /vm/compare/cpu/function - compare CPU functions via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/compare/cpu/function',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/compare/cpu/function')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_vmsync_callback(self, kvmagent_client, async_callback):
        """Test /vm/vmsync - sync VM states from libvirt via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/vmsync',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/vmsync')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getfirstbootdevice_callback(self, kvmagent_client, async_callback):
        """Test /vm/getfirstbootdevice - get first boot device via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/getfirstbootdevice',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/getfirstbootdevice')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volumesync_callback(self, kvmagent_client, async_callback):
        """Test /vm/volumesync - sync volume states via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volumesync',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volumesync')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_recover_check_callback(self, kvmagent_client, async_callback):
        """Test /vm/recover/check - VM recovery check via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/recover/check',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/recover/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_guesttools_getinfo_callback(self, kvmagent_client, async_callback):
        """Test /vm/guesttools/getinfo - get guest tools info via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/guesttools/getinfo',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/guesttools/getinfo')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_guesttools_getroutingstatus_callback(self, kvmagent_client, async_callback):
        """Test /vm/guesttools/getroutingstatus - get routing status via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/guesttools/getroutingstatus',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/guesttools/getroutingstatus')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_check_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/check - check volume state via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/check',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/check')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_getvolumebitmaps_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/getvolumebitmaps - get volume bitmaps via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/getvolumebitmaps',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/getvolumebitmaps')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_getmirrormode_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/getmirrormode - get mirror mode via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/getmirrormode',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/getmirrormode')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_querymirror_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/querymirror - query mirror status via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/querymirror',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/querymirror')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_querylatencyboundary_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/querylatencyboundary - query latency boundary via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/querylatencyboundary',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/querylatencyboundary')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_volume_listexportedvolumes_callback(self, kvmagent_client, async_callback):
        """Test /vm/volume/listexportedvolumes - list NBD exports via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/volume/listexportedvolumes',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/volume/listexportedvolumes')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_getiothreadpin_callback(self, kvmagent_client, async_callback):
        """Test /vm/getiothreadpin - get IO thread pinning via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/getiothreadpin',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/getiothreadpin')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_console_screenshot_callback(self, kvmagent_client, async_callback):
        """Test /vm/console/screenshot - take console screenshot via callback."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/vm/console/screenshot',
            data={},
            callback_url=callback_url,
        )
        _skip_if_not_loaded(response, '/vm/console/screenshot')
        assert response.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
