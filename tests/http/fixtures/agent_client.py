# -*- coding: utf-8 -*-
"""HTTP client fixtures for agent API testing."""

from __future__ import annotations

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
    All requests go through SSH tunnel (localhost forwarding).
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
        timeout: float = 10.0
    ) -> requests.Response:
        """
        Send POST request to agent endpoint.
        
        Args:
            path: API path (e.g., /host/ping)
            data: JSON request body
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
        
        Returns:
            requests.Response object
        """
        url = f"{self.base_url}{path}"
        return self.session.post(
            url,
            json=data or {},
            headers=headers or {},
            timeout=timeout
        )
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()


# Agent client fixtures (one per agent)

@pytest.fixture
def kvmagent_client(ssh_tunnel):
    """
    HTTP client for kvmagent.
    
    Requires ssh_tunnel fixture (ensures port forwarding is active).
    Connects to localhost:7070 which is forwarded to remote kvmagent:7070.
    """
    client = AgentClient(f"http://127.0.0.1:{AGENT_PORTS['kvmagent']}")
    yield client
    client.close()


@pytest.fixture
def virtualrouter_client(ssh_tunnel):
    """
    HTTP client for virtualrouter agent.
    
    Connects to localhost:7272 (forwarded to remote virtualrouter:7272).
    """
    client = AgentClient(f"http://127.0.0.1:{AGENT_PORTS['virtualrouter']}")
    yield client
    client.close()


@pytest.fixture
def appliancevm_client(ssh_tunnel):
    """
    HTTP client for appliancevm agent.
    
    Connects to localhost:7759 (forwarded to remote appliancevm:7759).
    """
    client = AgentClient(f"http://127.0.0.1:{AGENT_PORTS['appliancevm']}")
    yield client
    client.close()


@pytest.fixture
def cephbackup_client(ssh_tunnel):
    """
    HTTP client for ceph backup storage agent.
    
    Connects to localhost:7761 (forwarded to remote cephbackup:7761).
    """
    client = AgentClient(f"http://127.0.0.1:{AGENT_PORTS['cephbackup']}")
    yield client
    client.close()


@pytest.fixture
def cephprimary_client(ssh_tunnel):
    """
    HTTP client for ceph primary storage agent.
    
    Connects to localhost:7762 (forwarded to remote cephprimary:7762).
    """
    client = AgentClient(f"http://127.0.0.1:{AGENT_PORTS['cephprimary']}")
    yield client
    client.close()
