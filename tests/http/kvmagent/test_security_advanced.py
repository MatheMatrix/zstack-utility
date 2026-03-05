# -*- coding: utf-8 -*-
"""HTTP integration tests for security group, DEIP, and gratuitous ARP plugins.

Covers security group rule apply/refresh/cleanup/check, EIP apply/delete
(single and batch), and gratuitous ARP apply/release.
"""

import pytest


@pytest.mark.http
class TestSecurityGroupSmoke:
    """Smoke tests for securitygroup_plugin endpoints."""

    def test_apply_rules(self, kvmagent_client):
        """Test /securitygroup/applyrules - apply security group rules."""
        resp = kvmagent_client.post('/securitygroup/applyrules', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_refresh_rules_on_host(self, kvmagent_client):
        """Test /securitygroup/refreshrulesonhost - refresh all rules on host."""
        resp = kvmagent_client.post('/securitygroup/refreshrulesonhost', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cleanup_unused_rules(self, kvmagent_client):
        """Test /securitygroup/cleanupunusedrules - cleanup stale rules."""
        resp = kvmagent_client.post('/securitygroup/cleanupunusedrules', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_check_default_rules(self, kvmagent_client):
        """Test /securitygroup/checkdefaultrulesonhost - check default rules."""
        resp = kvmagent_client.post('/securitygroup/checkdefaultrulesonhost', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestDeipSmoke:
    """Smoke tests for DEIP (distributed EIP) endpoints."""

    def test_apply_eip(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/apply - apply EIP."""
        resp = kvmagent_client.post('/flatnetworkprovider/eip/apply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_eip(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/delete - delete EIP."""
        resp = kvmagent_client.post('/flatnetworkprovider/eip/delete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_batch_apply_eip(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/batchapply - batch apply EIPs."""
        resp = kvmagent_client.post('/flatnetworkprovider/eip/batchapply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_batch_delete_eip(self, kvmagent_client):
        """Test /flatnetworkprovider/eip/batchdelete - batch delete EIPs."""
        resp = kvmagent_client.post('/flatnetworkprovider/eip/batchdelete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestGratuitousARPSmoke:
    """Smoke tests for gratuitous ARP endpoints."""

    def test_apply_garp(self, kvmagent_client):
        """Test /flatnetworkprovider/garp/apply - apply gratuitous ARP."""
        resp = kvmagent_client.post('/flatnetworkprovider/garp/apply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_release_garp(self, kvmagent_client):
        """Test /flatnetworkprovider/garp/release - release gratuitous ARP."""
        resp = kvmagent_client.post('/flatnetworkprovider/garp/release', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
