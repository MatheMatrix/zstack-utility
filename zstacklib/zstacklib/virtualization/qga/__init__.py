# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from zstacklib.virtualization.qga.exceptions import (
    QgaError,
    QgaNotRunningError,
    QgaCommandError,
    QgaCommandDisabledError,
    QgaCommandNotSupportedError,
    QgaTimeoutError,
    QgaReturnValueError,
)
from zstacklib.virtualization.qga.constants import (
    QgaState,
    GuestOS,
    QGA_EXEC_WAIT_INTERVAL,
    QGA_EXEC_WAIT_RETRY,
)
from zstacklib.virtualization.qga.utils import (
    get_qga_channel_state,
    is_qga_connected,
)
from zstacklib.virtualization.qga.client import VmQga

__all__ = [
    'QgaError',
    'QgaNotRunningError',
    'QgaCommandError',
    'QgaCommandDisabledError',
    'QgaCommandNotSupportedError',
    'QgaTimeoutError',
    'QgaReturnValueError',
    'QgaState',
    'GuestOS',
    'QGA_EXEC_WAIT_INTERVAL',
    'QGA_EXEC_WAIT_RETRY',
    'get_qga_channel_state',
    'is_qga_connected',
    'VmQga',
]
