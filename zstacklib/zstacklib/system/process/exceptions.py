from __future__ import annotations


class ProcessError(Exception):
    pass


class PidFileError(ProcessError):
    pass


class ProcessNotFoundError(ProcessError):
    def __init__(self, pid: int):
        super().__init__(f"Process {pid} not found")
        self.pid = pid


class ProcessTimeoutError(ProcessError):
    pass
