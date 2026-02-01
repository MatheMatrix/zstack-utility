# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0


class QgaError(Exception):
    pass


class QgaNotRunningError(QgaError):
    pass


class QgaCommandError(QgaError):
    def __init__(self, command: str, message: str):
        self.command = command
        super().__init__(f"QGA command '{command}' failed: {message}")


class QgaCommandDisabledError(QgaError):
    def __init__(self, command: str):
        self.command = command
        super().__init__(f"QGA command '{command}' is disabled")


class QgaCommandNotSupportedError(QgaError):
    def __init__(self, command: str, version: str | None = None):
        self.command = command
        self.version = version
        msg = f"QGA command '{command}' not supported"
        if version:
            msg += f" (qga version: {version})"
        super().__init__(msg)


class QgaTimeoutError(QgaError):
    def __init__(self, command: str, timeout: int):
        self.command = command
        self.timeout = timeout
        super().__init__(f"QGA command '{command}' timed out after {timeout}s")


class QgaReturnValueError(QgaError):
    pass
