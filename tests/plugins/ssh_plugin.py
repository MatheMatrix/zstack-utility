from __future__ import annotations

import os
from typing import Callable, Optional, Tuple

import paramiko
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--ssh-host",
        action="store",
        default=None,
        help=(
            "SSH host connection info. Format: user:password@host[:port] or "
            "user@host[:port] (for SSH key auth)."
        ),
    )
    parser.addoption(
        "--ssh-password",
        action="store",
        default=None,
        help="SSH password override (used when --ssh-host omits password).",
    )
    parser.addoption(
        "--ssh-key",
        action="store",
        default=None,
        help="SSH private key path for key-based authentication.",
    )


def parse_ssh_host(host_string: str) -> Tuple[str, Optional[str], str, int]:
    if not host_string or "@" not in host_string:
        raise ValueError("Invalid ssh host string: missing user@host")

    userinfo, hostinfo = host_string.split("@", 1)
    if ":" in userinfo:
        user, password = userinfo.split(":", 1)
    else:
        user, password = userinfo, None

    if not user:
        raise ValueError("Invalid ssh host string: empty user")

    if not hostinfo:
        raise ValueError("Invalid ssh host string: empty host")

    if ":" in hostinfo:
        host, port_str = hostinfo.split(":", 1)
        if not port_str:
            raise ValueError("Invalid ssh host string: empty port")
        port = int(port_str)
    else:
        host = hostinfo
        port = 22

    if not host:
        raise ValueError("Invalid ssh host string: empty host")

    return user, password, host, port


def _build_ssh_client(
    host: str,
    port: int,
    user: str,
    password: Optional[str],
    key_path: Optional[str],
) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": host,
        "port": port,
        "username": user,
        "timeout": 15,
    }

    if key_path:
        connect_kwargs["key_filename"] = os.path.expanduser(key_path)
        connect_kwargs["allow_agent"] = True
        connect_kwargs["look_for_keys"] = True
        if password:
            connect_kwargs["password"] = password
    else:
        connect_kwargs["password"] = password

    client.connect(**connect_kwargs)
    return client


@pytest.fixture(scope="session")
def ssh_client(request) -> Optional[paramiko.SSHClient]:
    ssh_host = request.config.getoption("--ssh-host", default=None)
    if not ssh_host:
        return None

    ssh_password = request.config.getoption("--ssh-password", default=None)
    ssh_key = request.config.getoption("--ssh-key", default=None)

    user, parsed_password, host, port = parse_ssh_host(ssh_host)
    password = ssh_password or parsed_password

    if not password and not ssh_key:
        raise ValueError("SSH password or --ssh-key is required")

    client = _build_ssh_client(host, port, user, password, ssh_key)
    yield client
    client.close()


@pytest.fixture(scope="session")
def ssh_run(ssh_client) -> Callable[[str], Tuple[int, str, str]]:

    def _run(command: str) -> Tuple[int, str, str]:
        if ssh_client is None:
            raise RuntimeError("ssh_client is not initialized")

        stdin, stdout, stderr = ssh_client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        stdout_text = stdout.read().decode("utf-8", errors="ignore")
        stderr_text = stderr.read().decode("utf-8", errors="ignore")
        return exit_code, stdout_text, stderr_text

    return _run


@pytest.fixture(scope="session")
def scp_file(ssh_client) -> Callable[[str, str], None]:

    def _scp(local_path: str, remote_path: str) -> None:
        if ssh_client is None:
            raise RuntimeError("ssh_client is not initialized")
        sftp = ssh_client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

    return _scp
