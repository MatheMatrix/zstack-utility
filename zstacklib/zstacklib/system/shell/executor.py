from __future__ import annotations

import os
import subprocess
import time
from typing import Sequence

from .exceptions import CommandTimeoutError, ShellError
from .models import CommandResult, ShellContext


class ShellExecutor:
    """Execute shell commands with proper error handling."""

    def __init__(self, context: ShellContext | None = None):
        self.context = context or ShellContext()

    def run(
        self,
        command: str,
        *,
        check: bool = False,
        timeout: float | None = None,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a shell command and return the result."""
        effective_timeout = timeout or self.context.timeout
        effective_workdir = workdir or self.context.workdir

        effective_env = os.environ.copy()
        effective_env.update(self.context.env)
        if env:
            effective_env.update(env)

        if self.context.pipe_fail:
            command = f"set -o pipefail; {command}"

        start_time = time.monotonic()

        try:
            process = subprocess.Popen(
                command,
                shell=True,
                executable=self.context.shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=effective_workdir,
                env=effective_env,
                close_fds=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise CommandTimeoutError(command, effective_timeout or 0)

            duration_ms = (time.monotonic() - start_time) * 1000

            result = CommandResult(
                command=command,
                return_code=process.returncode,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                duration_ms=duration_ms,
            )

            if check:
                result.raise_for_status()

            return result

        except CommandTimeoutError:
            raise
        except ShellError:
            raise
        except Exception as e:
            raise ShellError(f"Failed to execute command: {e}", command=command)

    def call(self, command: str, **kwargs) -> str:
        """Run command and return stdout. Raises on non-zero exit."""
        result = self.run(command, check=True, **kwargs)
        return result.stdout

    def check_run(self, command: str, **kwargs) -> int:
        """Run command and return exit code. Raises on non-zero exit."""
        result = self.run(command, check=True, **kwargs)
        return result.return_code

    def run_silent(self, command: str, **kwargs) -> int:
        """Run command and return exit code without raising."""
        result = self.run(command, check=False, **kwargs)
        return result.return_code


def call(command: str, check: bool = True, workdir: str | None = None) -> str:
    """Convenience function to run a command and return stdout."""
    executor = ShellExecutor()
    result = executor.run(command, check=check, workdir=workdir)
    return result.stdout


def run(command: str, workdir: str | None = None) -> int:
    """Convenience function to run a command and return exit code."""
    executor = ShellExecutor()
    result = executor.run(command, check=False, workdir=workdir)
    return result.return_code


def check_run(command: str, workdir: str | None = None) -> int:
    """Convenience function to run a command, raise on failure, return exit code."""
    executor = ShellExecutor()
    result = executor.run(command, check=True, workdir=workdir)
    return result.return_code
