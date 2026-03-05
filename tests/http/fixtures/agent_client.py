# -*- coding: utf-8 -*-
"""HTTP client fixtures for agent API testing."""

from __future__ import annotations

import uuid
from typing import Optional

import pytest
import requests


# Agent port mapping (must match conftest.py AGENT_PORTS)
AGENT_PORTS = {
    'kvmagent': 7070,
    'virtualrouter': 7272,
    'appliancevm': 7759,
    'cephbackup': 7761,
    'cephprimary': 7762,
}


class AgentClient:
    """
    HTTP client for agent API requests.
    
    Uses requests.Session for connection pooling and persistence.
    Connects via SSH tunnel (localhost) or directly to remote host.
    """
    
    def __init__(self, base_url: str):
        """
        Initialize agent client.
        
        Args:
            base_url: Base URL for agent (e.g., http://127.0.0.1:7070)
        """
        self.base_url = base_url
        self.session = requests.Session()
    
    def post(
        self,
        path: str,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: float = 10.0,
        callback_url: Optional[str] = None,
    ) -> requests.Response:
        """
        Send POST request to agent endpoint.

        Args:
            path: API path (e.g., /host/ping)
            data: JSON request body
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
            callback_url: Optional async callback URL (sent via callbackurl header)

        Returns:
            requests.Response object
        """
        url = f"{self.base_url}{path}"
        task_uuid = str(uuid.uuid4())
        merged_headers = dict(headers or {})
        if callback_url:
            # Async endpoints require both callbackurl and taskUuid
            merged_headers['callbackurl'] = callback_url
            merged_headers['taskUuid'] = task_uuid
        resp = self.session.post(
            url,
            json=data or {},
            headers=merged_headers,
            timeout=timeout
        )
        # Attach taskUuid so callers can wait for async callbacks
        resp.task_uuid = task_uuid
        return resp
    
    def is_reachable(self, timeout=2.0):
        """Check if the agent is reachable by sending a quick request."""
        import socket
        try:
            # Parse host:port from base_url
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            host = parsed.hostname or '127.0.0.1'
            port = parsed.port or 80
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def close(self):
        """Close the HTTP session."""
        self.session.close()


# Agent client fixtures (one per agent)

@pytest.fixture
def kvmagent_client(ssh_tunnel, agent_host):
    """
    HTTP client for kvmagent.
    
    Depends on ssh_tunnel (for tunnel mode) and agent_host (for URL routing).
    In direct mode, agent_host is the remote IP; in tunnel mode, it's 127.0.0.1.
    """
    client = AgentClient(f"http://{agent_host}:{AGENT_PORTS['kvmagent']}")
    yield client
    client.close()


@pytest.fixture
def virtualrouter_client(ssh_tunnel, agent_host):
    """HTTP client for virtualrouter agent. Skips if agent not reachable."""
    client = AgentClient(f"http://{agent_host}:{AGENT_PORTS['virtualrouter']}")
    if not client.is_reachable():
        client.close()
        pytest.skip("virtualrouter agent not reachable on port %d" % AGENT_PORTS['virtualrouter'])
    yield client
    client.close()


@pytest.fixture
def appliancevm_client(ssh_tunnel, agent_host):
    """HTTP client for appliancevm agent. Skips if agent not reachable."""
    client = AgentClient(f"http://{agent_host}:{AGENT_PORTS['appliancevm']}")
    if not client.is_reachable():
        client.close()
        pytest.skip("appliancevm agent not reachable on port %d" % AGENT_PORTS['appliancevm'])
    yield client
    client.close()


@pytest.fixture
def cephbackup_client(ssh_tunnel, agent_host):
    """HTTP client for ceph backup storage agent. Skips if agent not reachable."""
    client = AgentClient(f"http://{agent_host}:{AGENT_PORTS['cephbackup']}")
    if not client.is_reachable():
        client.close()
        pytest.skip("cephbackup agent not reachable on port %d" % AGENT_PORTS['cephbackup'])
    yield client
    client.close()


@pytest.fixture
def cephprimary_client(ssh_tunnel, agent_host):
    """HTTP client for ceph primary storage agent. Skips if agent not reachable."""
    client = AgentClient(f"http://{agent_host}:{AGENT_PORTS['cephprimary']}")
    if not client.is_reachable():
        client.close()
        pytest.skip("cephprimary agent not reachable on port %d" % AGENT_PORTS['cephprimary'])
    yield client
    client.close()
