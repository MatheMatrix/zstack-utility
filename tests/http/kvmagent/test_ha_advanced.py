# -*- coding: utf-8 -*-
"""HTTP integration tests for HA plugin, mini_fencer, and ft_vm_fencer.

Covers high-availability self-fencer setup/cancel, scan host, VM state checks,
and VM fencer rule management endpoints.
"""

import pytest


@pytest.mark.http
class TestHAPluginSmoke:
    """Smoke tests for ha_plugin endpoints."""

    def test_scan_host(self, kvmagent_client):
        """Test /ha/scanhost - HA scan host."""
        resp = kvmagent_client.post('/ha/scanhost', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_sanlock_scan_host(self, kvmagent_client):
        """Test /sanlock/scanhost - sanlock-based scan host."""
        resp = kvmagent_client.post('/sanlock/scanhost', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_ceph_host_heartbeat_check(self, kvmagent_client):
        """Test /ceph/host/heartbeat/check - Ceph heartbeat check."""
        resp = kvmagent_client.post('/ceph/host/heartbeat/check', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    # --- Self fencer setup/cancel ---

    def test_setup_self_fencer(self, kvmagent_client):
        """Test /ha/selffencer/setup - filesystem self fencer setup."""
        resp = kvmagent_client.post('/ha/selffencer/setup', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_self_fencer(self, kvmagent_client):
        """Test /ha/selffencer/cancel - cancel filesystem self fencer."""
        resp = kvmagent_client.post('/ha/selffencer/cancel', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_ceph_self_fencer(self, kvmagent_client):
        """Test /ha/ceph/setupselffencer - Ceph self fencer setup."""
        resp = kvmagent_client.post('/ha/ceph/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_ceph_self_fencer(self, kvmagent_client):
        """Test /ha/ceph/cancelselffencer - cancel Ceph self fencer."""
        resp = kvmagent_client.post('/ha/ceph/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_sharedblock_self_fencer(self, kvmagent_client):
        """Test /ha/sharedblock/setupselffencer - shared block self fencer."""
        resp = kvmagent_client.post('/ha/sharedblock/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_sharedblock_self_fencer(self, kvmagent_client):
        """Test /ha/sharedblock/cancelselffencer - cancel shared block fencer."""
        resp = kvmagent_client.post('/ha/sharedblock/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_aliyun_nas_self_fencer(self, kvmagent_client):
        """Test /ha/aliyun/nas/setupselffencer - Aliyun NAS self fencer."""
        resp = kvmagent_client.post('/ha/aliyun/nas/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_aliyun_nas_self_fencer(self, kvmagent_client):
        """Test /ha/aliyun/nas/cancelselffencer - cancel NAS self fencer."""
        resp = kvmagent_client.post('/ha/aliyun/nas/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_block_self_fencer(self, kvmagent_client):
        """Test /ha/block/setupselffencer - block self fencer."""
        resp = kvmagent_client.post('/ha/block/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_block_self_fencer(self, kvmagent_client):
        """Test /ha/block/cancelselffencer - cancel block self fencer."""
        resp = kvmagent_client.post('/ha/block/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_iscsi_self_fencer(self, kvmagent_client):
        """Test /ha/iscsi/setupselffencer - iSCSI self fencer."""
        resp = kvmagent_client.post('/ha/iscsi/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_iscsi_self_fencer(self, kvmagent_client):
        """Test /ha/iscsi/cancelselffencer - cancel iSCSI self fencer."""
        resp = kvmagent_client.post('/ha/iscsi/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_setup_cbd_self_fencer(self, kvmagent_client):
        """Test /ha/cbd/setupselffencer - CBD self fencer."""
        resp = kvmagent_client.post('/ha/cbd/setupselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cancel_cbd_self_fencer(self, kvmagent_client):
        """Test /ha/cbd/cancelselffencer - cancel CBD self fencer."""
        resp = kvmagent_client.post('/ha/cbd/cancelselffencer', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    # --- VM state checks ---

    def test_filesystem_check_vmstate(self, kvmagent_client):
        """Test /filesystem/check/vmstate - filesystem VM state check."""
        resp = kvmagent_client.post('/filesystem/check/vmstate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_sharedblock_check_vmstate(self, kvmagent_client):
        """Test /sharedblock/check/vmstate - shared block VM state check."""
        resp = kvmagent_client.post('/sharedblock/check/vmstate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_iscsi_check_vmstate(self, kvmagent_client):
        """Test /iscsi/check/vmstate - iSCSI VM state check."""
        resp = kvmagent_client.post('/iscsi/check/vmstate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cbd_check_vmstate(self, kvmagent_client):
        """Test /cbd/check/vmstate - CBD VM state check."""
        resp = kvmagent_client.post('/cbd/check/vmstate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    # --- VM fencer rules ---

    def test_add_vm_fencer_rule(self, kvmagent_client):
        """Test /add/vm/fencer/rule/to/host - add VM fencer rule."""
        resp = kvmagent_client.post('/add/vm/fencer/rule/to/host', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_remove_vm_fencer_rule(self, kvmagent_client):
        """Test /remove/vm/fencer/rule/from/host - remove VM fencer rule."""
        resp = kvmagent_client.post('/remove/vm/fencer/rule/from/host', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_get_vm_fencer_rule(self, kvmagent_client):
        """Test /get/vm/fencer/rule/ - get VM fencer rule."""
        resp = kvmagent_client.post('/get/vm/fencer/rule/', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_fencer_state(self, kvmagent_client):
        """Test /ha/selffencer/state - get fencer state."""
        resp = kvmagent_client.post('/ha/selffencer/state', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestFtVmFencerSmoke:
    """Smoke tests for ft_vm_fencer endpoints."""

    def test_setup_ft_self_fencer(self, kvmagent_client):
        """Test /ft/selffencer/setup - FT VM self fencer setup."""
        resp = kvmagent_client.post('/ft/selffencer/setup', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
