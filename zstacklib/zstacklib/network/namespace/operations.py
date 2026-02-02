from __future__ import annotations

import os
import subprocess
from typing import Any

from .exceptions import NamespaceError, NamespaceNotFoundError, NamespaceExistsError, NamespaceExecError
from .models import NamespaceInfo, VethPair


NETNS_RUN_DIR = "/var/run/netns"


def namespace_exists(name: str) -> bool:
    return os.path.exists(os.path.join(NETNS_RUN_DIR, name))


def list_namespaces() -> list[str]:
    result = subprocess.run(
        ["ip", "netns", "list"],
        capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return []
    
    namespaces = []
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split()
            if parts:
                namespaces.append(parts[0])
    return namespaces


def create_namespace(name: str) -> None:
    if namespace_exists(name):
        raise NamespaceExistsError(name)
    
    result = subprocess.run(
        ["ip", "netns", "add", name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise NamespaceError(f"Failed to create namespace '{name}': {result.stderr}")


def delete_namespace(name: str) -> None:
    if not namespace_exists(name):
        return
    
    result = subprocess.run(
        ["ip", "netns", "delete", name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise NamespaceError(f"Failed to delete namespace '{name}': {result.stderr}")


def exec_in_namespace(
    namespace: str,
    command: list[str] | str,
    timeout: int | None = None,
    check: bool = True
) -> subprocess.CompletedProcess:
    if not namespace_exists(namespace):
        raise NamespaceNotFoundError(namespace)
    
    if isinstance(command, str):
        cmd = ["ip", "netns", "exec", namespace, "sh", "-c", command]
    else:
        cmd = ["ip", "netns", "exec", namespace] + command
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        if check and result.returncode != 0:
            cmd_str = command if isinstance(command, str) else ' '.join(command)
            raise NamespaceExecError(namespace, cmd_str, result.stderr)
        return result
    except subprocess.TimeoutExpired as e:
        cmd_str = command if isinstance(command, str) else ' '.join(command)
        raise NamespaceExecError(namespace, cmd_str, f"Command timed out after {timeout}s")


def get_namespace_info(name: str) -> NamespaceInfo | None:
    if not namespace_exists(name):
        return None
    
    ns_id = 0
    result = subprocess.run(
        ["ip", "netns", "list-id"],
        capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 4 and parts[1] == name:
                try:
                    ns_id = int(parts[3])
                except ValueError:
                    pass
    
    interfaces = []
    result = exec_in_namespace(name, ["ip", "-o", "link", "show"], check=False)
    if result.returncode == 0:
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(':')
                if len(parts) >= 2:
                    iface = parts[1].strip().split('@')[0]
                    if iface:
                        interfaces.append(iface)
    
    return NamespaceInfo(name=name, id=ns_id, interfaces=interfaces)


def create_veth_pair(
    host_end: str,
    ns_end: str,
    namespace: str,
    host_ip: str | None = None,
    ns_ip: str | None = None
) -> VethPair:
    if not namespace_exists(namespace):
        raise NamespaceNotFoundError(namespace)
    
    result = subprocess.run(
        ["ip", "link", "add", host_end, "type", "veth", "peer", "name", ns_end],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise NamespaceError(f"Failed to create veth pair: {result.stderr}")
    
    result = subprocess.run(
        ["ip", "link", "set", ns_end, "netns", namespace],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        subprocess.run(["ip", "link", "delete", host_end], check=False)
        raise NamespaceError(f"Failed to move veth to namespace: {result.stderr}")
    
    subprocess.run(["ip", "link", "set", host_end, "up"], check=False)
    exec_in_namespace(namespace, ["ip", "link", "set", ns_end, "up"], check=False)
    
    if host_ip:
        subprocess.run(["ip", "addr", "add", host_ip, "dev", host_end], check=False)
    
    if ns_ip:
        exec_in_namespace(namespace, ["ip", "addr", "add", ns_ip, "dev", ns_end], check=False)
    
    return VethPair(
        host_end=host_end,
        ns_end=ns_end,
        namespace=namespace,
        host_ip=host_ip or "",
        ns_ip=ns_ip or ""
    )


def move_interface_to_namespace(interface: str, namespace: str) -> None:
    if not namespace_exists(namespace):
        raise NamespaceNotFoundError(namespace)
    
    result = subprocess.run(
        ["ip", "link", "set", interface, "netns", namespace],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise NamespaceError(f"Failed to move interface to namespace: {result.stderr}")


def set_namespace_loopback_up(namespace: str) -> None:
    if not namespace_exists(namespace):
        raise NamespaceNotFoundError(namespace)
    
    exec_in_namespace(namespace, ["ip", "link", "set", "lo", "up"], check=False)
