# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
NBD (Network Block Device) client module.

This module provides a pure-Python NBD client implementation for connecting
to NBD servers and reading block device data over the network.

Key Features:
- Support for both old-style and new-style NBD negotiation
- TCP and Unix socket connections
- IPv4 and IPv6 support
- Export selection for new-style servers

Example:
    >>> from zstacklib.storage.nbd import NbdClient
    >>> client = NbdClient(host='192.168.1.100', port=10809, export_name='disk0')
    >>> client.connect()
    >>> data = client.read(offset=0, length=4096)
    >>> client.close()
"""

from zstacklib.storage.nbd.exceptions import (
    NbdError,
    NbdConnectionError,
    NbdNegotiationError,
    NbdReadError,
    NbdProtocolError,
)
from zstacklib.storage.nbd.constants import (
    # Commands
    NBD_CMD_READ,
    NBD_CMD_WRITE,
    NBD_CMD_DISC,
    NBD_CMD_FLUSH,
    NBD_CMD_TRIM,
    # Flags
    NBD_FLAG_HAS_FLAGS,
    NBD_FLAG_READ_ONLY,
    NBD_FLAG_SEND_FLUSH,
    # Option types
    NBD_OPT_EXPORT_NAME,
    NBD_OPT_ABORT,
    NBD_OPT_LIST,
    NBD_OPT_GO,
)
from zstacklib.storage.nbd.client import NbdClient

__all__ = [
    # Exceptions
    'NbdError',
    'NbdConnectionError',
    'NbdNegotiationError',
    'NbdReadError',
    'NbdProtocolError',
    # Constants
    'NBD_CMD_READ',
    'NBD_CMD_WRITE',
    'NBD_CMD_DISC',
    'NBD_CMD_FLUSH',
    'NBD_CMD_TRIM',
    'NBD_FLAG_HAS_FLAGS',
    'NBD_FLAG_READ_ONLY',
    'NBD_FLAG_SEND_FLUSH',
    'NBD_OPT_EXPORT_NAME',
    'NBD_OPT_ABORT',
    'NBD_OPT_LIST',
    'NBD_OPT_GO',
    # Client
    'NbdClient',
]
