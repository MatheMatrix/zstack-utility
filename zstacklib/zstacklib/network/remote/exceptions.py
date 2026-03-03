from __future__ import annotations


class RemoteError(Exception):
    """Remoteerror."""
    pass


class SSHConnectionError(RemoteError):
    """Sshconnectionerror."""
    def __init__(self, host: str, message: str):
        """Init."""
        self.host = host
        super().__init__(f"SSH connection to '{host}' failed: {message}")


class RemoteCommandError(RemoteError):
    """Remotecommanderror."""
    def __init__(self, host: str, command: str, returncode: int, stderr: str):
        """Init."""
        self.host = host
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Remote command on '{host}' failed (exit {returncode}): {stderr}")


class SCPError(RemoteError):
    """Scperror."""
    def __init__(self, source: str, dest: str, message: str):
        """Init."""
        self.source = source
        self.dest = dest
        super().__init__(f"SCP from '{source}' to '{dest}' failed: {message}")
