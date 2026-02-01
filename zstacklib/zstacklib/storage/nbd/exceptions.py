# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

"""NBD client exceptions."""


class NbdError(Exception):
    """Base exception for all NBD-related errors."""

    pass


class NbdConnectionError(NbdError):
    """Raised when connection to NBD server fails."""

    pass


class NbdNegotiationError(NbdError):
    """Raised when NBD protocol negotiation fails."""

    pass


class NbdReadError(NbdError):
    """Raised when read operation fails."""

    pass


class NbdProtocolError(NbdError):
    """Raised when NBD protocol violation is detected."""

    pass


class NbdExportError(NbdError):
    """Raised when export selection fails."""

    pass
