from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandResult:
    """Result of a shell command execution."""

    command: str
    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.return_code == 0

    @property
    def output(self) -> str:
        """Alias for stdout for convenience."""
        return self.stdout

    def raise_for_status(self) -> None:
        """Raise ShellError if command failed."""
        if not self.success:
            from .exceptions import ShellError
            raise ShellError(
                f"Command failed with code {self.return_code}: {self.stderr or self.stdout}",
                command=self.command,
                return_code=self.return_code,
            )


@dataclass
class ShellContext:
    """Context for shell command execution."""

    workdir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    shell: str = "/bin/bash"
    pipe_fail: bool = False

    def with_workdir(self, workdir: str) -> ShellContext:
        return ShellContext(
            workdir=workdir,
            env=self.env.copy(),
            timeout=self.timeout,
            shell=self.shell,
            pipe_fail=self.pipe_fail,
        )

    def with_env(self, **env: str) -> ShellContext:
        new_env = self.env.copy()
        new_env.update(env)
        return ShellContext(
            workdir=self.workdir,
            env=new_env,
            timeout=self.timeout,
            shell=self.shell,
            pipe_fail=self.pipe_fail,
        )
