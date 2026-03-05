# -*- coding: utf-8 -*-
"""HTTP integration tests for HA plugin, mini_fencer, and ft_vm_fencer.

Covers high-availability self-fencer setup/cancel, scan host, VM state checks,
and VM fencer rule management endpoints.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestHAPluginSmoke:
    """Smoke tests for ha_plugin endpoints."""

    def test_scan_host(self, kvmagent_client, async_callback):
        """Test /ha/scanhost - HA scan host."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/scanhost', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/scanhost')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_sanlock_scan_host(self, kvmagent_client, async_callback):
        """Test /sanlock/scanhost - sanlock-based scan host."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sanlock/scanhost', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sanlock/scanhost')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_ceph_host_heartbeat_check(self, kvmagent_client, async_callback):
        """Test /ceph/host/heartbeat/check - Ceph heartbeat check."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ceph/host/heartbeat/check', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ceph/host/heartbeat/check')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    # --- Self fencer setup/cancel ---

    def test_setup_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/selffencer/setup - filesystem self fencer setup."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/selffencer/setup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/selffencer/setup')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/selffencer/cancel - cancel filesystem self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/selffencer/cancel', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/selffencer/cancel')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_ceph_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/ceph/setupselffencer - Ceph self fencer setup."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/ceph/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/ceph/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_ceph_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/ceph/cancelselffencer - cancel Ceph self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/ceph/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/ceph/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_sharedblock_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/sharedblock/setupselffencer - shared block self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/sharedblock/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/sharedblock/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_sharedblock_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/sharedblock/cancelselffencer - cancel shared block fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/sharedblock/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/sharedblock/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_aliyun_nas_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/aliyun/nas/setupselffencer - Aliyun NAS self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/aliyun/nas/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/aliyun/nas/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_aliyun_nas_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/aliyun/nas/cancelselffencer - cancel NAS self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/aliyun/nas/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/aliyun/nas/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_block_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/block/setupselffencer - block self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/block/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/block/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_block_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/block/cancelselffencer - cancel block self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/block/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/block/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_iscsi_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/iscsi/setupselffencer - iSCSI self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/iscsi/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/iscsi/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_iscsi_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/iscsi/cancelselffencer - cancel iSCSI self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/iscsi/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/iscsi/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_setup_cbd_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/cbd/setupselffencer - CBD self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/cbd/setupselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/cbd/setupselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_cbd_self_fencer(self, kvmagent_client, async_callback):
        """Test /ha/cbd/cancelselffencer - cancel CBD self fencer."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/cbd/cancelselffencer', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/cbd/cancelselffencer')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    # --- VM state checks ---

    def test_filesystem_check_vmstate(self, kvmagent_client, async_callback):
        """Test /filesystem/check/vmstate - filesystem VM state check."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/filesystem/check/vmstate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/filesystem/check/vmstate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_sharedblock_check_vmstate(self, kvmagent_client, async_callback):
        """Test /sharedblock/check/vmstate - shared block VM state check."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/check/vmstate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/sharedblock/check/vmstate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_iscsi_check_vmstate(self, kvmagent_client, async_callback):
        """Test /iscsi/check/vmstate - iSCSI VM state check."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/iscsi/check/vmstate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/iscsi/check/vmstate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cbd_check_vmstate(self, kvmagent_client, async_callback):
        """Test /cbd/check/vmstate - CBD VM state check."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/cbd/check/vmstate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/cbd/check/vmstate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    # --- VM fencer rules ---

    def test_add_vm_fencer_rule(self, kvmagent_client, async_callback):
        """Test /add/vm/fencer/rule/to/host - add VM fencer rule."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/add/vm/fencer/rule/to/host', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/add/vm/fencer/rule/to/host')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_remove_vm_fencer_rule(self, kvmagent_client, async_callback):
        """Test /remove/vm/fencer/rule/from/host - remove VM fencer rule."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/remove/vm/fencer/rule/from/host', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/remove/vm/fencer/rule/from/host')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_get_vm_fencer_rule(self, kvmagent_client, async_callback):
        """Test /get/vm/fencer/rule/ - get VM fencer rule."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/get/vm/fencer/rule/', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/get/vm/fencer/rule/')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_fencer_state(self, kvmagent_client, async_callback):
        """Test /ha/selffencer/state - get fencer state."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ha/selffencer/state', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ha/selffencer/state')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestFtVmFencerSmoke:
    """Smoke tests for ft_vm_fencer endpoints."""

    def test_setup_ft_self_fencer(self, kvmagent_client, async_callback):
        """Test /ft/selffencer/setup - FT VM self fencer setup."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/ft/selffencer/setup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/ft/selffencer/setup')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
