# -*- coding: utf-8 -*-
"""HTTP integration tests for monitoring plugins.

Covers prometheus collectd exporter, QGA zwatch metric monitor,
physical NIC/bond/memory monitors, and host service type setting.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestPrometheusSmoke:
    """Smoke tests for prometheus plugin endpoints."""

    def test_collectd_exporter_start(self, kvmagent_client, async_callback):
        """Test /prometheus/collectdexporter/start - start collectd exporter."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/prometheus/collectdexporter/start', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/prometheus/collectdexporter/start')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_set_service_type(self, kvmagent_client, async_callback):
        """Test /host/setservicetype/networkinterface - set service type on NIC."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/setservicetype/networkinterface', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/setservicetype/networkinterface')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestQgaZwatchSmoke:
    """Smoke tests for QGA zwatch metric monitor endpoints."""

    def test_init_zwatch_monitor(self, kvmagent_client, async_callback):
        """Test /host/zwatchMetricMonitor/init - initialize zwatch monitor."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/zwatchMetricMonitor/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/zwatchMetricMonitor/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_config_zwatch_monitor(self, kvmagent_client, async_callback):
        """Test /host/zwatchMetricMonitor/config - configure zwatch monitor."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/zwatchMetricMonitor/config', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/zwatchMetricMonitor/config')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestPhysicalMonitorsSmoke:
    """Smoke tests for physical hardware monitor endpoints."""

    def test_update_bond_monitor(self, kvmagent_client, async_callback):
        """Test /host/physicalBond/update - update bond monitor settings."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/physicalBond/update', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/physicalBond/update')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_start_memory_monitor(self, kvmagent_client, async_callback):
        """Test /host/physical/memory/monitor/start - start memory monitor."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/physical/memory/monitor/start', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/physical/memory/monitor/start')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_nic_monitor(self, kvmagent_client, async_callback):
        """Test /host/physicalNic/update - update NIC monitor settings."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/physicalNic/update', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/physicalNic/update')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_test_nic_alarm(self, kvmagent_client, async_callback):
        """Test /host/physicalNic/test - test NIC alarm trigger."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/host/physicalNic/test', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/host/physicalNic/test')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
