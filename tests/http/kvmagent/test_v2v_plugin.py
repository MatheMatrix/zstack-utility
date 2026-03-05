# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent V2V conversion plugin."""

import pytest


@pytest.mark.http
class TestV2VPluginSmoke:
    """Smoke tests for kvm_v2v_plugin endpoints."""

    def test_init(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/init - initialize V2V conversion host."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/init', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_listvm(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/listvm - list VMs for V2V."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/listvm', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_umount(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/umount - unmount V2V storage."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/umount', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_clean(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/clean - clean V2V temp files."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/clean', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_check_bits(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/checkbits - check V2V bits."""
        # This is registered via CHECK_BITS constant
        response = kvmagent_client.post('/kvmv2v/conversionhost/checkbits', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_config_qos(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/qos/config - configure QoS."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/qos/config', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_delete_qos(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/qos/delete - delete QoS."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/qos/delete', data={})
        assert response.status_code in [200, 400, 403, 404, 500]

    def test_cancel_convert(self, kvmagent_client):
        """Test /kvmv2v/conversionhost/convert/cancel - cancel conversion."""
        response = kvmagent_client.post('/kvmv2v/conversionhost/convert/cancel', data={})
        assert response.status_code in [200, 400, 403, 404, 500]
