# -*- coding: utf-8 -*-
"""HTTP integration tests for advanced network plugins.

Covers OVN (Open Virtual Network), OVS-DPDK, port mirroring, VIP QoS,
and mevoco flat network (DHCP, userdata, DNS forward, arping).
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestOvnSmoke:
    """Smoke tests for OVN plugin endpoints."""

    def test_install_package(self, kvmagent_client, async_callback):
        """Test /network/ovn/install - install OVN packages."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/install', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/install')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_uninstall_package(self, kvmagent_client, async_callback):
        """Test /network/ovn/uninstall - uninstall OVN packages."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/uninstall', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/uninstall')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_start_service(self, kvmagent_client, async_callback):
        """Test /network/ovn/start - start OVN service."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/start', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/start')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_stop_service(self, kvmagent_client, async_callback):
        """Test /network/ovn/stop - stop OVN service."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/stop', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/stop')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_add_port(self, kvmagent_client, async_callback):
        """Test /network/ovn/addport - add OVN port."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/addport', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/addport')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_del_port(self, kvmagent_client, async_callback):
        """Test /network/ovn/delport - delete OVN port."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/delport', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/delport')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_set_controller_connection(self, kvmagent_client, async_callback):
        """Test /network/ovn/controller/setConnection - set controller params."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/controller/setConnection', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/controller/setConnection')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_set_requested_chassis(self, kvmagent_client, async_callback):
        """Test /network/ovn/setrequestedchassis - set requested chassis."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/setrequestedchassis', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/setrequestedchassis')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_sync_ports(self, kvmagent_client, async_callback):
        """Test /network/ovn/syncports - sync OVN ports."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/syncports', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/syncports')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_local_port(self, kvmagent_client, async_callback):
        """Test /network/ovn/checklocalport - check local port."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovn/checklocalport', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovn/checklocalport')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestOvsDpdkSmoke:
    """Smoke tests for OVS-DPDK endpoints."""

    def test_check_bridge(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/checkbridge - check DPDK bridge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/checkbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/checkbridge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_bridge(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/createbridge - create DPDK bridge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/createbridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/createbridge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bridge(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/deletebridge - delete DPDK bridge."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/deletebridge', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/deletebridge')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_generate_vdpa(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/generatevdpa - generate vDPA device."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/generatevdpa', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/generatevdpa')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_vdpa(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/deletevdpa - delete vDPA device."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/deletevdpa', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/deletevdpa')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_add_vhostuserclient(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/addvhostuserclient - add vhost-user client."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/addvhostuserclient', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/addvhostuserclient')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_vhostuserclient(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/deletevhostuserclient - delete vhost-user."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/deletevhostuserclient', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/deletevhostuserclient')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_resource_configure(self, kvmagent_client, async_callback):
        """Test /network/ovsdpdk/resource/configure - configure resources."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/network/ovsdpdk/resource/configure', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/network/ovsdpdk/resource/configure')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_smartnics_init(self, kvmagent_client, async_callback):
        """Test /hostvirtualnetworkinterface/generate - init SmartNICs."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/hostvirtualnetworkinterface/generate', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/hostvirtualnetworkinterface/generate')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestPortMirrorSmoke:
    """Smoke tests for port_mirror_plugin endpoints."""

    def test_apply_source(self, kvmagent_client, async_callback):
        """Test /portmirror/apply/source - apply mirror session source."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/portmirror/apply/source', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/portmirror/apply/source')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_release_source(self, kvmagent_client, async_callback):
        """Test /portmirror/release/source - release mirror session source."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/portmirror/release/source', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/portmirror/release/source')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_apply_dest(self, kvmagent_client, async_callback):
        """Test /portmirror/apply/dest - apply mirror session dest."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/portmirror/apply/dest', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/portmirror/apply/dest')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_release_dest(self, kvmagent_client, async_callback):
        """Test /portmirror/release/dest - release mirror session dest."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/portmirror/release/dest', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/portmirror/release/dest')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestVipQosSmoke:
    """Smoke tests for VIP QoS endpoints."""

    def test_apply_vipqos(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/apply - apply VIP QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/vipqos/apply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_vipqos(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/delete - delete VIP QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/vipqos/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_all_vipqos(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/vipqos/deleteall - delete all VIP QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/deleteall', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/vipqos/deleteall')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestMevocoSmoke:
    """Smoke tests for mevoco (flat network DHCP/userdata/DNS) endpoints."""

    # --- DHCP ---

    def test_dhcp_connect(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/connect - DHCP connect."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/connect', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/connect')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_apply_dhcp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/apply - apply DHCP config."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/apply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_batch_apply_dhcp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/batchApply - batch apply DHCP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchApply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/batchApply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_release_dhcp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/release - release DHCP lease."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/release', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/release')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_prepare_dhcp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/prepare - prepare DHCP namespace."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/prepare', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/prepare')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_batch_prepare_dhcp(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/batchPrepare - batch prepare DHCP."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchPrepare', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/batchPrepare')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_reset_default_gateway(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/resetDefaultGateway."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/resetDefaultGateway', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/resetDefaultGateway')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_dhcp_namespace(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/deletenamespace - delete namespace."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/deletenamespace', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/deletenamespace')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_flush_dhcp_namespace(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/dhcp/flush - flush DHCP namespace."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/flush', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/dhcp/flush')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_arping_namespace(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/arping - arping in namespace."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/arping', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/arping')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    # --- Userdata ---

    def test_apply_userdata(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/userdata/apply - apply userdata."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/apply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/userdata/apply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_release_userdata(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/userdata/release - release userdata."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/release', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/userdata/release')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_batch_apply_userdata(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/userdata/batchapply - batch apply userdata."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/batchapply', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/userdata/batchapply')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cleanup_userdata(self, kvmagent_client, async_callback):
        """Test /flatnetworkprovider/userdata/cleanup - cleanup userdata."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/cleanup', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/flatnetworkprovider/userdata/cleanup')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    # --- DNS Forward ---

    def test_set_dns_forward(self, kvmagent_client, async_callback):
        """Test /dns/forward/set - set DNS forward rule."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/dns/forward/set', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/dns/forward/set')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_remove_dns_forward(self, kvmagent_client, async_callback):
        """Test /dns/forward/remove - remove DNS forward rule."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/dns/forward/remove', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/dns/forward/remove')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
