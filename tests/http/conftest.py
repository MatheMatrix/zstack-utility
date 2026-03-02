# -*- coding: utf-8 -*-
"""
HTTP Integration Tests Configuration - SSH Tunnel Infrastructure.

This module provides fixtures for HTTP integration tests that connect to remote
agent HTTP APIs via SSH port forwarding. It creates a session-scoped SSH tunnel
that forwards local ports to agent services running on a remote host.

Architecture:
    Local HTTP Client → SSH Tunnel → Agent Services on Remote Host
    
    localhost:7070   → kvmagent:7070
    localhost:7272   → virtualrouter:7272
    localhost:7759   → appliancevm:7759
    localhost:7761   → cephbackup:7761
    localhost:7762   → cephprimary:7762

Agent Port Mapping:
    kvmagent:      7070 (KVM hypervisor agent)
    virtualrouter: 7272 (Virtual network router agent)
    appliancevm:   7759 (Appliance VM agent)
    cephbackup:    7761 (Ceph backup storage agent)
    cephprimary:   7762 (Ceph primary storage agent)

Usage:
    @pytest.mark.http
    def test_kvmagent_api(ssh_tunnel):
        # Test makes HTTP requests to http://localhost:7070/api/...
        pass
    
    Run with: pytest tests/http/ --ssh-host=user:pass@192.168.1.100
"""

import os
import select
import socket
import threading
import time
from typing import Dict, Optional

import paramiko
import pytest

# Import SSH utilities from ssh_plugin
from tests.plugins.ssh_plugin import _build_ssh_client, parse_ssh_host

# Import HTTP test fixtures so pytest can discover them
from tests.http.fixtures.agent_client import (  # noqa: F401
    kvmagent_client,
    virtualrouter_client,
    appliancevm_client,
    cephbackup_client,
    cephprimary_client,
)
from tests.http.fixtures.async_helper import async_callback  # noqa: F401


# ============================================================================
# Agent Port Mapping - Defines which local ports forward to which agents
# ============================================================================
AGENT_PORTS = {
    "kvmagent": 7070,
    "virtualrouter": 7272,
    "appliancevm": 7759,
    "cephbackup": 7761,
    "cephprimary": 7762,
}


class SSHTunnelManager:
    """
    Manages SSH port forwarding for agent HTTP connections.
    
    This class creates a set of bidirectional SSH port forwardings using
    paramiko's direct-tcpip channel type. Each agent gets a dedicated
    forwarding thread that:
    
    1. Listens on localhost:<port>
    2. Opens SSH channel to remote host via Transport.open_channel()
    3. Bidirectionally forwards TCP data between client and remote agent
    
    Port forwarding is implemented using raw socket I/O and select-based
    multiplexing for efficient simultaneous connections across all ports.
    
    Thread Safety:
        - Uses threading.Event for coordinated shutdown
        - All forwarding threads are daemon threads
        - Supports multiple simultaneous client connections per port
    """
    
    def __init__(self, ssh_client: paramiko.SSHClient, ports: Dict[str, int]):
        """
        Initialize tunnel manager.
        
        Args:
            ssh_client: Connected paramiko.SSHClient instance
            ports: Dict mapping agent names to port numbers
                   e.g. {"kvmagent": 7070, "virtualrouter": 7272}
        """
        self.ssh_client = ssh_client
        self.ports = ports
        self.transport = ssh_client.get_transport()
        self.threads = []
        self.stop_event = threading.Event()
    
    def _forward_port(self, agent_name: str, local_port: int, remote_port: int):
        """
        Forward a single port using SSH direct-tcpip channel.
        
        This method:
        1. Creates a listening socket on localhost:<local_port>
        2. Accepts incoming TCP connections
        3. For each connection:
           - Opens SSH channel to remote host via Transport.open_channel()
           - Spawns bidirectional forwarding threads
           - Handles concurrent connections
        
        The forwarding continues until stop_event is set.
        
        Args:
            agent_name: Name of agent (for logging/naming)
            local_port: Local port to listen on (127.0.0.1)
            remote_port: Remote port to forward to (on remote host)
        """
        import socket
        
        # Create local server socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server.bind(("127.0.0.1", local_port))
        except OSError as e:
            raise RuntimeError(
                f"Failed to bind {agent_name} tunnel to 127.0.0.1:{local_port}: {e}"
            )
        
        server.listen(5)
        server.settimeout(1.0)
        
        while not self.stop_event.is_set():
            try:
                # Use select to check for incoming connections with timeout
                readable, _, _ = select.select([server], [], [], 1.0)
                
                if not readable:
                    continue
                
                # Accept incoming connection from local client
                try:
                    client_sock, addr = server.accept()
                except socket.timeout:
                    continue
                
                # Open SSH channel to remote agent
                try:
                    channel = self.transport.open_channel(
                        "direct-tcpip",
                        ("127.0.0.1", remote_port),
                        ("127.0.0.1", 0),
                    )
                except Exception as e:
                    client_sock.close()
                    continue
                
                # Create bidirectional forwarding threads
                def forward_data(src, dst, direction):
                    """Forward data from src to dst until connection closes."""
                    try:
                        while True:
                            data = src.recv(4096)
                            if not data:
                                break
                            dst.sendall(data)
                    except Exception:
                        pass
                    finally:
                        try:
                            src.close()
                        except Exception:
                            pass
                        try:
                            dst.close()
                        except Exception:
                            pass
                
                # Spawn threads for bidirectional forwarding
                client_to_remote = threading.Thread(
                    target=forward_data,
                    args=(client_sock, channel, "client->remote"),
                    daemon=True,
                )
                remote_to_client = threading.Thread(
                    target=forward_data,
                    args=(channel, client_sock, "remote->client"),
                    daemon=True,
                )
                
                client_to_remote.start()
                remote_to_client.start()
            
            except socket.timeout:
                continue
            except Exception:
                break
        
        try:
            server.close()
        except Exception:
            pass
    
    def start(self):
        """
        Start all port forwarding threads.
        
        Creates and starts a daemon thread for each agent port. Each thread
        will listen on its local port and forward connections to the remote
        agent via SSH.
        """
        for agent_name, port in self.ports.items():
            thread = threading.Thread(
                target=self._forward_port,
                args=(agent_name, port, port),
                name=f"tunnel-{agent_name}-{port}",
                daemon=True,
            )
            thread.start()
            self.threads.append(thread)
    
    def stop(self):
        """
        Stop all port forwarding threads.
        
        Signals the stop_event and waits for all forwarding threads to
        terminate gracefully. Uses a 2-second timeout per thread.
        """
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=2.0)


def _wait_for_tunnels_ready(ports: Dict[str, int], timeout: float = 5.0):
    """
    Wait for all tunnel ports to be ready by attempting socket connections.
    
    Args:
        ports: Dict mapping agent names to port numbers
        timeout: Maximum time to wait in seconds
    
    Raises:
        RuntimeError: If tunnels are not ready within timeout
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        all_ready = True
        for agent_name, port in ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            try:
                result = sock.connect_ex(('127.0.0.1', port))
                if result != 0:
                    all_ready = False
            except Exception:
                all_ready = False
            finally:
                sock.close()
        
        if all_ready:
            return
        
        time.sleep(0.1)  # Brief pause between connection attempts
    
    raise RuntimeError(
        f"SSH tunnels not ready within {timeout}s. Check agent connectivity."
    )

@pytest.fixture(scope="session")
def ssh_tunnel(request) -> Optional[SSHTunnelManager]:
    """
    Create and manage SSH tunnel for HTTP integration tests.
    
    Supports two modes:
    1. SSH tunnel mode (--ssh-host): Creates SSH port forwarding to remote agents
    2. Direct mode (--direct-host): No tunnel needed, tests connect directly via VPN
    
    In direct mode, this fixture yields None (no tunnel) and agent clients
    connect to the remote host directly using the IP from --direct-host.
    
    Behavior:
        - If --direct-host is provided: yield None (no tunnel needed)
        - If --ssh-host is provided: create SSH tunnel
        - If neither is provided: pytest.skip() the test
    """
    
    # Direct host mode: no tunnel needed, VPN provides direct access
    direct_host = request.config.getoption("--direct-host", default=None)
    if direct_host:
        yield None
        return
    
    # SSH tunnel mode: requires --ssh-host
    ssh_host = request.config.getoption("--ssh-host", default=None)
    if not ssh_host:
        pytest.skip(
            "HTTP integration tests require --ssh-host or --direct-host option. "
            "Usage: pytest tests/http/ --ssh-host=user:pass@host "
            "or: pytest tests/http/ --direct-host=172.24.194.116"
        )
    
    # Get SSH authentication options
    ssh_password = request.config.getoption("--ssh-password", default=None)
    ssh_key = request.config.getoption("--ssh-key", default=None)
    
    # Parse SSH host string (user:password@host:port format)
    user, parsed_password, host, port = parse_ssh_host(ssh_host)
    password = ssh_password or parsed_password
    
    # Validate authentication credentials
    if not password and not ssh_key:
        raise ValueError(
            "SSH authentication required: provide password in --ssh-host, "
            "--ssh-password, or --ssh-key"
        )
    
    # Build and connect SSH client
    try:
        client = _build_ssh_client(host, port, user, password, ssh_key)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to SSH host {user}@{host}:{port}: {e}")
    
    # Create tunnel manager with all agent ports
    tunnel = SSHTunnelManager(client, AGENT_PORTS)
    
    # Start port forwarding threads
    try:
        tunnel.start()
    except RuntimeError as e:
        client.close()
        raise
    
    # Verify tunnels are ready by checking socket connectivity
    _wait_for_tunnels_ready(AGENT_PORTS, timeout=5.0)
    
    # Yield tunnel for test use
    yield tunnel
    
    # Cleanup: stop tunnel and close SSH connection
    tunnel.stop()
    client.close()


@pytest.fixture(scope="session")
def agent_host(request) -> str:
    """
    Return the target host for agent HTTP connections.
    
    In direct mode: returns the --direct-host IP (agents are accessed directly).
    In SSH tunnel mode: returns '127.0.0.1' (agents accessed via tunnel).
    """
    direct_host = request.config.getoption("--direct-host", default=None)
    if direct_host:
        return direct_host
    return "127.0.0.1"


@pytest.fixture(scope="session")
def agent_base_urls(agent_host) -> Dict[str, str]:
    """
    Provide base URLs for agent HTTP APIs.
    
    Uses agent_host fixture to determine target (localhost for tunnel,
    remote IP for direct mode).
    
    Returns:
        Dict mapping agent names to http://<host>:<port> URLs
    """
    return {
        agent_name: f"http://{agent_host}:{port}"
        for agent_name, port in AGENT_PORTS.items()
    }
