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


@pytest.fixture(scope="session")
def ssh_tunnel(request) -> Optional[SSHTunnelManager]:
    """
    Create and manage SSH tunnel for HTTP integration tests.
    
    This fixture:
    1. Checks for --ssh-host option (required for HTTP tests)
    2. Parses SSH connection info using parse_ssh_host()
    3. Builds SSH client using _build_ssh_client()
    4. Creates SSHTunnelManager with all agent ports
    5. Starts port forwarding threads
    6. Yields tunnel manager for test use
    7. Cleans up and closes SSH connection on teardown
    
    The fixture has session scope, so it creates ONE tunnel for the entire
    test session. All HTTP tests in the session reuse the same tunnel.
    
    Behavior:
        - If --ssh-host is not provided: pytest.skip() the test
        - If SSH connection fails: raises RuntimeError
        - If port binding fails: raises RuntimeError
    
    Returns:
        SSHTunnelManager: Active tunnel manager with all ports forwarded
    
    Raises:
        pytest.skip.Exception: If --ssh-host not provided
        RuntimeError: If SSH connection or port binding fails
    
    Example:
        @pytest.mark.http
        def test_kvmagent_api(ssh_tunnel):
            # ssh_tunnel is active, ports are forwarded
            response = requests.get("http://localhost:7070/api/...")
            assert response.status_code == 200
    """
    
    # Check if --ssh-host option is provided
    ssh_host = request.config.getoption("--ssh-host", default=None)
    if not ssh_host:
        pytest.skip(
            "HTTP integration tests require --ssh-host option. "
            "Usage: pytest tests/http/ --ssh-host=user:pass@192.168.1.100"
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
    
    # Wait briefly for tunnels to initialize
    time.sleep(0.5)
    
    # Yield tunnel for test use
    yield tunnel
    
    # Cleanup: stop tunnel and close SSH connection
    tunnel.stop()
    client.close()


@pytest.fixture(scope="session")
def agent_base_urls() -> Dict[str, str]:
    """
    Provide base URLs for agent HTTP APIs.
    
    Returns a dictionary mapping agent names to their base URLs.
    These URLs assume ssh_tunnel fixture is active and forwarding ports.
    
    Returns:
        Dict mapping agent names to http://localhost:<port> URLs
    
    Example:
        def test_agent_api(agent_base_urls):
            kvmagent_url = agent_base_urls["kvmagent"]  # http://localhost:7070
            response = requests.get(f"{kvmagent_url}/api/...")
    """
    return {
        agent_name: f"http://localhost:{port}"
        for agent_name, port in AGENT_PORTS.items()
    }
