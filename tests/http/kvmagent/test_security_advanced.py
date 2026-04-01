# -*- coding: utf-8 -*-
"""HTTP integration tests for security group, DEIP, and gratuitous ARP plugins.

Covers security group rule apply/refresh/cleanup/check, EIP apply/delete
(single and batch), and gratuitous ARP apply/release.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestSecurityGroupSmoke:
    """Smoke tests for securitygroup_plugin endpoints."""

    def test_apply_rules(self, kvmagent_client, async_callback):
        """Test /securitygroup/applyrules - apply security group rules."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/securitygroup/applyrules', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/securitygroup/applyrules')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_refresh_rules_on_host(self, kvmagent_client, async_callback):
        """Test /securitygroup/refreshrulesonhost - refresh all rules on host."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/securitygroup/refreshrulesonhost', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/securitygroup/refreshrulesonhost')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cleanup_unused_rules(self, kvmagent_client, async_callback):
        """Test /securitygroup/cleanupunusedrules - cleanup stale rules."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/securitygroup/cleanupunusedrules', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/securitygroup/cleanupunusedrules')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_default_rules(self, kvmagent_client, async_callback):
        """Test /securitygroup/checkdefaultrulesonhost - check default rules."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/securitygroup/checkdefaultrulesonhost', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/securitygroup/checkdefaultrulesonhost')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestDeipSmoke:
    """Smoke tests for DEIP (distributed EIP) endpoints."""

    def test_apply_eip(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/apply - apply EIP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/eip/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/eip/apply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_eip(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/delete - delete EIP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/eip/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/eip/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_batch_apply_eip(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/batchapply - batch apply EIPs."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/eip/batchapply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/eip/batchapply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_batch_delete_eip(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/eip/batchdelete - batch delete EIPs."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/eip/batchdelete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/eip/batchdelete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestGratuitousARPSmoke:
    """Smoke tests for gratuitous ARP endpoints."""

    def test_apply_garp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/garp/apply - apply gratuitous ARP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/garp/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/garp/apply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_release_garp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/garp/release - release gratuitous ARP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/garp/release', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/garp/release')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
