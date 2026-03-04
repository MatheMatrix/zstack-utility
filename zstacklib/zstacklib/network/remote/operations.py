from __future__ import annotations

import subprocess
import shlex
from typing import Sequence

from .exceptions import RemoteError, SSHConnectionError, RemoteCommandError, SCPError
from .models import SSHConfig, RemoteResult


def _build_ssh_options(config: SSHConfig) -> list[str]:
    """Build ssh options."""
    options = [
        "-o", f"ConnectTimeout={config.connect_timeout}",
        "-o", f"StrictHostKeyChecking={'yes' if config.strict_host_key_checking else 'no'}",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "BatchMode=yes",
        "-p", str(config.port),
    ]
    
    if config.key_file:
        options.extend(["-i", config.key_file])
    
    return options


def remote_execute(
    config: SSHConfig,
    command: str | list[str],
    timeout: int | None = None,
    check: bool = True
) -> RemoteResult:
    """Remote execute."""
    ssh_options = _build_ssh_options(config)
    
    if isinstance(command, list):
        cmd_str = ' '.join(shlex.quote(c) for c in command)
    else:
        cmd_str = command
    
    cmd = ["ssh"] + ssh_options + [f"{config.user}@{config.host}", cmd_str]
    
    effective_timeout = config.timeout if timeout is None else timeout

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=effective_timeout
        )

        remote_result = RemoteResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            host=config.host,
            command=cmd_str
        )
        
        if check and result.returncode != 0:
            if "Connection refused" in result.stderr or "No route to host" in result.stderr:
                raise SSHConnectionError(config.host, result.stderr)
            raise RemoteCommandError(config.host, cmd_str, result.returncode, result.stderr)
        
        return remote_result
        
    except subprocess.TimeoutExpired:
        raise RemoteError(f"Command timed out after {effective_timeout}s on {config.host}")
    except FileNotFoundError:
        raise RemoteError("ssh command not found")


def remote_copy(
    config: SSHConfig,
    source: str,
    dest: str,
    to_remote: bool = True,
    recursive: bool = False,
    timeout: int | None = None
) -> None:
    """Remote copy."""
    scp_options = [
        "-o", f"ConnectTimeout={config.connect_timeout}",
        "-o", f"StrictHostKeyChecking={'yes' if config.strict_host_key_checking else 'no'}",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "BatchMode=yes",
        "-P", str(config.port),
    ]
    
    if config.key_file:
        scp_options.extend(["-i", config.key_file])
    
    if recursive:
        scp_options.append("-r")
    
    if to_remote:
        remote_path = f"{config.user}@{config.host}:{dest}"
        cmd = ["scp"] + scp_options + [source, remote_path]
    else:
        remote_path = f"{config.user}@{config.host}:{source}"
        cmd = ["scp"] + scp_options + [remote_path, dest]
    
    effective_timeout = config.timeout if timeout is None else timeout

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=effective_timeout
        )

        if result.returncode != 0:
            raise SCPError(source, dest, result.stderr)
            
    except subprocess.TimeoutExpired:
        raise SCPError(source, dest, f"Timed out after {effective_timeout}s")
    except FileNotFoundError:
        raise RemoteError("scp command not found")


def check_ssh_connectivity(config: SSHConfig) -> bool:
    """Check ssh connectivity."""
    try:
        result = remote_execute(config, "echo ok", timeout=config.connect_timeout, check=False)
        return result.returncode == 0 and "ok" in result.stdout
    except (RemoteError, SSHConnectionError):
        return False


def get_remote_file_content(config: SSHConfig, path: str) -> str:
    """Get remote file content."""
    result = remote_execute(config, f"cat {shlex.quote(path)}")
    return result.stdout


def remote_file_exists(config: SSHConfig, path: str) -> bool:
    """Remote file exists."""
    result = remote_execute(config, f"test -e {shlex.quote(path)}", check=False)
    return result.returncode == 0


def remote_mkdir(config: SSHConfig, path: str, parents: bool = True) -> None:
    """Remote mkdir."""
    flag = "-p" if parents else ""
    remote_execute(config, f"mkdir {flag} {shlex.quote(path)}")
