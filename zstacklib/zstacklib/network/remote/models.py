from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SSHConfig:
    """Sshconfig."""
    host: str
    user: str = "root"
    port: int = 22
    key_file: str | None = None
    password: str | None = None
    timeout: int = 30
    strict_host_key_checking: bool = False
    connect_timeout: int = 10


@dataclass
class RemoteResult:
    """Remoteresult."""
    returncode: int
    stdout: str
    stderr: str
    host: str
    command: str

    @property
    def success(self) -> bool:
        """Success."""
        return self.returncode == 0
