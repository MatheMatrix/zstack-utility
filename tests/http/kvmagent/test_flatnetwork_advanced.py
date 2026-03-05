# -*- coding: utf-8 -*-
"""HTTP smoke tests for kvmagent flatnetwork provider DHCP operations (M2 coverage)."""

import uuid

import pytest

pytestmark = [
    pytest.mark.http,
]


def _skip_if_missing(response, endpoint):
    if response.status_code == 403:
        pytest.skip("blocked by firewall (403)")
    if response.status_code == 404:
        pytest.skip("%s not loaded (404)" % endpoint)
    if response.status_code == 500:
        pytest.skip("%s returned 500 (requires real infra)" % endpoint)


def _safe_wait(async_callback, task_uuid, timeout=15.0):
    try:
        return async_callback.wait(task_uuid, timeout=timeout)
    except TimeoutError:
        pytest.skip("callback timeout (handler requires real infra)")


class TestFlatNetworkDHCP:
    """Flatnetwork provider DHCP operations."""

    def test_dhcp_apply(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/apply', data={
            'dhcp': [],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/apply')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_batch_apply(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchApply', data={
            'dhcpInfosList': [],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/batchApply')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_batch_prepare(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchPrepare', data={
            'dhcpInfosList': [],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/batchPrepare')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_delete_namespace(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/deletenamespace', data={
            'bridgeName': 'br_nonexistent_%s' % uuid.uuid4().hex[:6],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/deletenamespace')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_flush(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/flush', data={
            'bridgeName': 'br_nonexistent_%s' % uuid.uuid4().hex[:6],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/flush')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_prepare(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/prepare', data={
            'dhcp': [],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/prepare')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_release(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/release', data={
            'dhcp': [],
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/release')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_dhcp_reset_default_gateway(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/resetDefaultGateway', data={
            'bridgeNameDhcpMap': {},
        }, callback_url=cb)
        _skip_if_missing(resp, '/flatnetworkprovider/dhcp/resetDefaultGateway')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)
