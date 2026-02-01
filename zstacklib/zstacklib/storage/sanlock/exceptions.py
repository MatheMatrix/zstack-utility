# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0


class SanlockError(Exception):
    pass


class SanlockParseError(SanlockError):
    pass


class SanlockHostNotFoundError(SanlockError):
    def __init__(self, host_id: int):
        self.host_id = host_id
        super().__init__(f"Host {host_id} not found in sanlock status")


class SanlockLockspaceNotFoundError(SanlockError):
    def __init__(self, lockspace: str):
        self.lockspace = lockspace
        super().__init__(f"Lockspace '{lockspace}' not found")
