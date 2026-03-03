# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0


class SanlockError(Exception):
    """Sanlockerror."""
    pass


class SanlockParseError(SanlockError):
    """Sanlockparseerror."""
    pass


class SanlockHostNotFoundError(SanlockError):
    """Sanlockhostnotfounderror."""
    def __init__(self, host_id: int):
        """Init."""
        self.host_id = host_id
        super().__init__(f"Host {host_id} not found in sanlock status")


class SanlockLockspaceNotFoundError(SanlockError):
    """Sanlocklockspacenotfounderror."""
    def __init__(self, lockspace: str):
        """Init."""
        self.lockspace = lockspace
        super().__init__(f"Lockspace '{lockspace}' not found")
