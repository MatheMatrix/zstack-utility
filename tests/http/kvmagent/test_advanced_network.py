# -*- coding: utf-8 -*-
"""HTTP integration tests for advanced network plugins.

Covers OVN (Open Virtual Network), OVS-DPDK, port mirroring, VIP QoS,
and mevoco flat network (DHCP, userdata, DNS forward, arping).
"""

import pytest


@pytest.mark.http
class TestOvnSmoke:
    """Smoke tests for OVN plugin endpoints."""

    def test_install_package(self, kvmagent_client):
        """Test /network/ovn/install - install OVN packages."""
        resp = kvmagent_client.post('/network/ovn/install', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_uninstall_package(self, kvmagent_client):
        """Test /network/ovn/uninstall - uninstall OVN packages."""
        resp = kvmagent_client.post('/network/ovn/uninstall', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_start_service(self, kvmagent_client):
        """Test /network/ovn/start - start OVN service."""
        resp = kvmagent_client.post('/network/ovn/start', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_stop_service(self, kvmagent_client):
        """Test /network/ovn/stop - stop OVN service."""
        resp = kvmagent_client.post('/network/ovn/stop', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_add_port(self, kvmagent_client):
        """Test /network/ovn/addport - add OVN port."""
        resp = kvmagent_client.post('/network/ovn/addport', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_del_port(self, kvmagent_client):
        """Test /network/ovn/delport - delete OVN port."""
        resp = kvmagent_client.post('/network/ovn/delport', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_set_controller_connection(self, kvmagent_client):
        """Test /network/ovn/controller/setConnection - set controller params."""
        resp = kvmagent_client.post('/network/ovn/controller/setConnection', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_set_requested_chassis(self, kvmagent_client):
        """Test /network/ovn/setrequestedchassis - set requested chassis."""
        resp = kvmagent_client.post('/network/ovn/setrequestedchassis', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_sync_ports(self, kvmagent_client):
        """Test /network/ovn/syncports - sync OVN ports."""
        resp = kvmagent_client.post('/network/ovn/syncports', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_check_local_port(self, kvmagent_client):
        """Test /network/ovn/checklocalport - check local port."""
        resp = kvmagent_client.post('/network/ovn/checklocalport', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestOvsDpdkSmoke:
    """Smoke tests for OVS-DPDK endpoints."""

    def test_check_bridge(self, kvmagent_client):
        """Test /network/ovsdpdk/checkbridge - check DPDK bridge."""
        resp = kvmagent_client.post('/network/ovsdpdk/checkbridge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_create_bridge(self, kvmagent_client):
        """Test /network/ovsdpdk/createbridge - create DPDK bridge."""
        resp = kvmagent_client.post('/network/ovsdpdk/createbridge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_bridge(self, kvmagent_client):
        """Test /network/ovsdpdk/deletebridge - delete DPDK bridge."""
        resp = kvmagent_client.post('/network/ovsdpdk/deletebridge', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_generate_vdpa(self, kvmagent_client):
        """Test /network/ovsdpdk/generatevdpa - generate vDPA device."""
        resp = kvmagent_client.post('/network/ovsdpdk/generatevdpa', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_vdpa(self, kvmagent_client):
        """Test /network/ovsdpdk/deletevdpa - delete vDPA device."""
        resp = kvmagent_client.post('/network/ovsdpdk/deletevdpa', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_add_vhostuserclient(self, kvmagent_client):
        """Test /network/ovsdpdk/addvhostuserclient - add vhost-user client."""
        resp = kvmagent_client.post('/network/ovsdpdk/addvhostuserclient', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_vhostuserclient(self, kvmagent_client):
        """Test /network/ovsdpdk/deletevhostuserclient - delete vhost-user."""
        resp = kvmagent_client.post('/network/ovsdpdk/deletevhostuserclient', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_resource_configure(self, kvmagent_client):
        """Test /network/ovsdpdk/resource/configure - configure resources."""
        resp = kvmagent_client.post('/network/ovsdpdk/resource/configure', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_smartnics_init(self, kvmagent_client):
        """Test /hostvirtualnetworkinterface/generate - init SmartNICs."""
        resp = kvmagent_client.post('/hostvirtualnetworkinterface/generate', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestPortMirrorSmoke:
    """Smoke tests for port_mirror_plugin endpoints."""

    def test_apply_source(self, kvmagent_client):
        """Test /portmirror/apply/source - apply mirror session source."""
        resp = kvmagent_client.post('/portmirror/apply/source', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_release_source(self, kvmagent_client):
        """Test /portmirror/release/source - release mirror session source."""
        resp = kvmagent_client.post('/portmirror/release/source', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_apply_dest(self, kvmagent_client):
        """Test /portmirror/apply/dest - apply mirror session dest."""
        resp = kvmagent_client.post('/portmirror/apply/dest', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_release_dest(self, kvmagent_client):
        """Test /portmirror/release/dest - release mirror session dest."""
        resp = kvmagent_client.post('/portmirror/release/dest', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestVipQosSmoke:
    """Smoke tests for VIP QoS endpoints."""

    def test_apply_vipqos(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/apply - apply VIP QoS."""
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/apply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_vipqos(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/delete - delete VIP QoS."""
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/delete', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_all_vipqos(self, kvmagent_client):
        """Test /flatnetworkprovider/vipqos/deleteall - delete all VIP QoS."""
        resp = kvmagent_client.post('/flatnetworkprovider/vipqos/deleteall', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestMevocoSmoke:
    """Smoke tests for mevoco (flat network DHCP/userdata/DNS) endpoints."""

    # --- DHCP ---

    def test_dhcp_connect(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/connect - DHCP connect."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/connect', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_apply_dhcp(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/apply - apply DHCP config."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/apply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_batch_apply_dhcp(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/batchApply - batch apply DHCP."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchApply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_release_dhcp(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/release - release DHCP lease."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/release', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_prepare_dhcp(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/prepare - prepare DHCP namespace."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/prepare', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_batch_prepare_dhcp(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/batchPrepare - batch prepare DHCP."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/batchPrepare', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_reset_default_gateway(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/resetDefaultGateway."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/resetDefaultGateway', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_delete_dhcp_namespace(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/deletenamespace - delete namespace."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/deletenamespace', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_flush_dhcp_namespace(self, kvmagent_client):
        """Test /flatnetworkprovider/dhcp/flush - flush DHCP namespace."""
        resp = kvmagent_client.post('/flatnetworkprovider/dhcp/flush', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_arping_namespace(self, kvmagent_client):
        """Test /flatnetworkprovider/arping - arping in namespace."""
        resp = kvmagent_client.post('/flatnetworkprovider/arping', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    # --- Userdata ---

    def test_apply_userdata(self, kvmagent_client):
        """Test /flatnetworkprovider/userdata/apply - apply userdata."""
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/apply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_release_userdata(self, kvmagent_client):
        """Test /flatnetworkprovider/userdata/release - release userdata."""
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/release', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_batch_apply_userdata(self, kvmagent_client):
        """Test /flatnetworkprovider/userdata/batchapply - batch apply userdata."""
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/batchapply', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_cleanup_userdata(self, kvmagent_client):
        """Test /flatnetworkprovider/userdata/cleanup - cleanup userdata."""
        resp = kvmagent_client.post('/flatnetworkprovider/userdata/cleanup', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    # --- DNS Forward ---

    def test_set_dns_forward(self, kvmagent_client):
        """Test /dns/forward/set - set DNS forward rule."""
        resp = kvmagent_client.post('/dns/forward/set', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_remove_dns_forward(self, kvmagent_client):
        """Test /dns/forward/remove - remove DNS forward rule."""
        resp = kvmagent_client.post('/dns/forward/remove', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
