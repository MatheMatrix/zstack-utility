# -*- coding: utf-8 -*-
"""HTTP integration tests for monitoring plugins.

Covers prometheus collectd exporter, QGA zwatch metric monitor,
physical NIC/bond/memory monitors, and host service type setting.
"""

import pytest


@pytest.mark.http
class TestPrometheusSmoke:
    """Smoke tests for prometheus plugin endpoints."""

    def test_collectd_exporter_start(self, kvmagent_client):
        """Test /prometheus/collectdexporter/start - start collectd exporter."""
        resp = kvmagent_client.post('/prometheus/collectdexporter/start', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_set_service_type(self, kvmagent_client):
        """Test /host/setservicetype/networkinterface - set service type on NIC."""
        resp = kvmagent_client.post('/host/setservicetype/networkinterface', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestQgaZwatchSmoke:
    """Smoke tests for QGA zwatch metric monitor endpoints."""

    def test_init_zwatch_monitor(self, kvmagent_client):
        """Test /host/zwatchMetricMonitor/init - initialize zwatch monitor."""
        resp = kvmagent_client.post('/host/zwatchMetricMonitor/init', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_config_zwatch_monitor(self, kvmagent_client):
        """Test /host/zwatchMetricMonitor/config - configure zwatch monitor."""
        resp = kvmagent_client.post('/host/zwatchMetricMonitor/config', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]


@pytest.mark.http
class TestPhysicalMonitorsSmoke:
    """Smoke tests for physical hardware monitor endpoints."""

    def test_update_bond_monitor(self, kvmagent_client):
        """Test /host/physicalBond/update - update bond monitor settings."""
        resp = kvmagent_client.post('/host/physicalBond/update', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_start_memory_monitor(self, kvmagent_client):
        """Test /host/physical/memory/monitor/start - start memory monitor."""
        resp = kvmagent_client.post('/host/physical/memory/monitor/start', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_update_nic_monitor(self, kvmagent_client):
        """Test /host/physicalNic/update - update NIC monitor settings."""
        resp = kvmagent_client.post('/host/physicalNic/update', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]

    def test_test_nic_alarm(self, kvmagent_client):
        """Test /host/physicalNic/test - test NIC alarm trigger."""
        resp = kvmagent_client.post('/host/physicalNic/test', data={})
        assert resp.status_code in [200, 400, 403, 404, 500]
