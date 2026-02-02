from __future__ import annotations


class RemoteError(Exception):
    pass


class SSHConnectionError(RemoteError):
    def __init__(self, host: str, message: str):
        self.host = host
        super().__init__(f"SSH connection to '{host}' failed: {message}")


class RemoteCommandError(RemoteError):
    def __init__(self, host: str, command: str, returncode: int, stderr: str):
        self.host = host
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Remote command on '{host}' failed (exit {returncode}): {stderr}")


class SCPError(RemoteError):
    def __init__(self, source: str, dest: str, message: str):
        self.source = source
        self.dest = dest
        super().__init__(f"SCP from '{source}' to '{dest}' failed: {message}")
