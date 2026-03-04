# -*- coding: utf-8 -*-
"""Cross-plugin HTTP integration tests for kvmagent (Round 14).

These tests verify workflows that span multiple kvmagent plugins,
ensuring plugins work correctly together through the HTTP API layer.
"""

import uuid

import pytest

pytestmark = [
    pytest.mark.http,
]


class TestHostAndStorageIntegration:
    """Test host info + storage capacity queries together."""

    def test_host_capacity_and_localstorage_capacity(
        self, kvmagent_client, async_callback
    ):
        """Verify host capacity and localstorage capacity are both queryable."""
        cb1 = async_callback.get_callback_url()
        resp1 = kvmagent_client.post(
            '/host/capacity',
            data={},
            callback_url=cb1,
        )
        assert resp1.status_code == 200
        host_result = async_callback.wait(resp1.task_uuid, timeout=15.0)
        assert isinstance(host_result, dict)

        cb2 = async_callback.get_callback_url()
        resp2 = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={'storagePath': '/'},
            callback_url=cb2,
        )
        if resp2.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert resp2.status_code == 200
        storage_result = async_callback.wait(resp2.task_uuid, timeout=15.0)
        assert isinstance(storage_result, dict)

    def test_host_fact_and_network_nicnames(
        self, kvmagent_client, async_callback
    ):
        """Verify host facts and network NIC names are both queryable."""
        cb1 = async_callback.get_callback_url()
        resp1 = kvmagent_client.post(
            '/host/fact',
            data={},
            callback_url=cb1,
        )
        assert resp1.status_code == 200
        fact_result = async_callback.wait(resp1.task_uuid, timeout=15.0)
        assert isinstance(fact_result, dict)

        cb2 = async_callback.get_callback_url()
        resp2 = kvmagent_client.post(
            '/network/getnicnames',
            data={},
            callback_url=cb2,
        )
        if resp2.status_code == 404:
            pytest.skip("network nic plugin not loaded")
        assert resp2.status_code == 200
        nic_result = async_callback.wait(resp2.task_uuid, timeout=15.0)
        assert isinstance(nic_result, dict)


class TestStorageAndVMIntegration:
    """Test storage queries + VM state queries together."""

    def test_localstorage_capacity_and_vm_checkstate(
        self, kvmagent_client, async_callback
    ):
        """Query localstorage capacity then check VM state."""
        cb1 = async_callback.get_callback_url()
        resp1 = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={'storagePath': '/'},
            callback_url=cb1,
        )
        if resp1.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert resp1.status_code == 200
        storage_result = async_callback.wait(resp1.task_uuid, timeout=15.0)
        assert isinstance(storage_result, dict)

        cb2 = async_callback.get_callback_url()
        resp2 = kvmagent_client.post(
            '/vm/checkstate',
            data={'vmUuids': [uuid.uuid4().hex]},
            callback_url=cb2,
        )
        assert resp2.status_code == 200
        vm_result = async_callback.wait(resp2.task_uuid, timeout=15.0)
        assert isinstance(vm_result, dict)

    def test_checkbits_and_getqcow2reference(
        self, kvmagent_client, async_callback
    ):
        """Query checkbits then getqcow2reference on same path."""
        test_path = '/tmp/nonexistent-cross-plugin-test.qcow2'

        cb1 = async_callback.get_callback_url()
        resp1 = kvmagent_client.post(
            '/localstorage/checkbits',
            data={'path': test_path},
            callback_url=cb1,
        )
        if resp1.status_code == 404:
            pytest.skip("localstorage plugin not loaded")
        assert resp1.status_code == 200
        check_result = async_callback.wait(resp1.task_uuid, timeout=15.0)
        assert isinstance(check_result, dict)

        cb2 = async_callback.get_callback_url()
        resp2 = kvmagent_client.post(
            '/localstorage/getqcow2reference',
            data={'path': test_path, 'searchingDir': '/tmp'},
            callback_url=cb2,
        )
        if resp2.status_code == 404:
            pytest.skip("localstorage qcow2reference not loaded")
        assert resp2.status_code == 200
        ref_result = async_callback.wait(resp2.task_uuid, timeout=15.0)
        assert isinstance(ref_result, dict)


class TestMultipleCallbackConcurrency:
    """Test that multiple async callbacks can be received concurrently."""

    def test_parallel_host_queries(self, kvmagent_client, async_callback):
        """Fire multiple host queries and collect all callbacks."""
        endpoints = [
            ('/host/capacity', {}),
            ('/host/fact', {}),
            ('/vm/checkstate', {'vmUuids': []}),
        ]

        responses = []
        for path, data in endpoints:
            cb = async_callback.get_callback_url()
            resp = kvmagent_client.post(path, data=data, callback_url=cb)
            assert resp.status_code == 200
            responses.append(resp)

        # Collect all callbacks
        for resp in responses:
            result = async_callback.wait(resp.task_uuid, timeout=20.0)
            assert isinstance(result, dict)

    def test_parallel_storage_queries(self, kvmagent_client, async_callback):
        """Fire multiple storage queries and collect all callbacks."""
        cb1 = async_callback.get_callback_url()
        resp1 = kvmagent_client.post(
            '/localstorage/getphysicalcapacity',
            data={'storagePath': '/'},
            callback_url=cb1,
        )
        if resp1.status_code == 404:
            pytest.skip("localstorage plugin not loaded")

        cb2 = async_callback.get_callback_url()
        resp2 = kvmagent_client.post(
            '/localstorage/checkbits',
            data={'path': '/tmp/nonexistent'},
            callback_url=cb2,
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        r1 = async_callback.wait(resp1.task_uuid, timeout=15.0)
        r2 = async_callback.wait(resp2.task_uuid, timeout=15.0)
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)


class TestEndpointDiscovery:
    """Test that key endpoints are registered and respond."""

    CORE_ENDPOINTS = [
        '/host/capacity',
        '/host/fact',
        '/host/ping',
        '/vm/checkstate',
    ]

    OPTIONAL_ENDPOINTS = [
        '/localstorage/getphysicalcapacity',
        '/network/l2novlan/checkbridge',
        '/prometheus/query',
    ]

    def test_core_endpoints_respond(self, kvmagent_client):
        """All core endpoints must return 200 (not 404)."""
        for path in self.CORE_ENDPOINTS:
            resp = kvmagent_client.post(path, data={})
            assert resp.status_code == 200, (
                "Core endpoint %s returned %d" % (path, resp.status_code)
            )

    def test_optional_endpoints_graceful(self, kvmagent_client):
        """Optional endpoints return either 200 or 404 (never 500)."""
        for path in self.OPTIONAL_ENDPOINTS:
            resp = kvmagent_client.post(path, data={})
            assert resp.status_code in (200, 404), (
                "Endpoint %s returned unexpected %d" % (path, resp.status_code)
            )
