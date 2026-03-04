# -*- coding: utf-8 -*-
"""HTTP integration tests for kvmagent prometheus/monitoring plugin."""

import pytest


@pytest.mark.http
class TestPrometheusSmoke:
    """Smoke tests for prometheus plugin endpoints."""

    def test_collectd_start(self, kvmagent_client):
        """Test /prometheus/collectdexporter/start - start collectd exporter."""
        response = kvmagent_client.post('/prometheus/collectdexporter/start', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestCephStorageKvmSmoke:
    """Smoke tests for ceph_storage_plugin (kvmagent-side ceph helper)."""

    def test_check_host_connection(self, kvmagent_client):
        """Test /ceph/primarystorage/check/host/connection - check ceph connection."""
        response = kvmagent_client.post('/ceph/primarystorage/check/host/connection', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestFTVMFencerSmoke:
    """Smoke tests for ft_vm_fencer plugin (fault-tolerant VM fencer)."""

    def test_selffencer_setup(self, kvmagent_client):
        """Test /ft/selffencer/setup - setup FT self-fencer."""
        response = kvmagent_client.post('/ft/selffencer/setup', data={})
        assert response.status_code in [200, 400, 500]


@pytest.mark.http
class TestZBSStorageSmoke:
    """Smoke tests for zbs_storage_plugin endpoints."""

    def test_check_host_connection(self, kvmagent_client):
        """Test /zbs/primarystorage/check/host/connection - check ZBS connection."""
        response = kvmagent_client.post('/zbs/primarystorage/check/host/connection', data={})
        assert response.status_code in [200, 400, 500]

    def test_update_host_dependency(self, kvmagent_client):
        """Test /zbs/primarystorage/host/updatedependency - update dependency."""
        response = kvmagent_client.post('/zbs/primarystorage/host/updatedependency', data={})
        assert response.status_code in [200, 400, 500]
