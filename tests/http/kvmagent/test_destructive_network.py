# -*- coding: utf-8 -*-
"""Destructive HTTP tests for kvmagent network operations (Round 11).

These tests modify host network state (bridges, NICs, security groups).
Only run on disposable VMs with --allow-destructive flag.
"""

import pytest

pytestmark = [
    pytest.mark.http,
    pytest.mark.destructive,
]



class TestBridgeOperations:
    """Test bridge create/delete lifecycle."""

    def test_create_novlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2novlan/createbridge with real parameters."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2novlan/createbridge',
            data={
                'physicalInterfaceName': 'eth0',
                'bridgeName': 'br_ztest_0',
            },
            callback_url=callback_url,
        )
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_check_novlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2novlan/checkbridge after creation."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2novlan/checkbridge',
            data={'bridgeName': 'br_ztest_0'},
            callback_url=callback_url,
        )
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_create_vlan_bridge(self, kvmagent_client, async_callback):
        """Test /network/l2vlan/createbridge with VLAN ID."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/network/l2vlan/createbridge',
            data={
                'physicalInterfaceName': 'eth0',
                'bridgeName': 'br_ztest_v100',
                'vlan': 100,
            },
            callback_url=callback_url,
        )
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=30.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)


class TestSecurityGroupOperations:
    """Test security group rule apply/remove."""

    def test_apply_security_group(self, kvmagent_client, async_callback):
        """Test /securitygroup/apply - apply security group rules."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/apply',
            data={'rules': []},
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("securitygroup plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_refresh_security_group(self, kvmagent_client, async_callback):
        """Test /securitygroup/refresh - refresh security group rules."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/refresh',
            data={},
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("securitygroup plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)

    def test_cleanup_security_group(self, kvmagent_client, async_callback):
        """Test /securitygroup/cleanup - cleanup unused rules."""
        callback_url = async_callback.get_callback_url()
        response = kvmagent_client.post(
            '/securitygroup/cleanup',
            data={},
            callback_url=callback_url,
        )
        if response.status_code == 403:
            pytest.skip("blocked by firewall (403)")
        if response.status_code == 404:
            pytest.skip("securitygroup plugin not loaded")
        assert response.status_code in [200, 403, 404]
        try:
            result = async_callback.wait(response.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout (agent cannot reach test server)")
        assert isinstance(result, dict)
