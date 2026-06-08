# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

"""
NBD protocol constants.

This module defines all the magic numbers, flags, and constants used
in the NBD (Network Block Device) protocol.

Reference: https://github.com/NetworkBlockDevice/nbd/blob/master/doc/proto.md
"""

# =============================================================================
# NBD Commands
# =============================================================================

NBD_CMD_READ = 0
NBD_CMD_WRITE = 1
NBD_CMD_DISC = 2  # Disconnect
NBD_CMD_FLUSH = 3
NBD_CMD_TRIM = 4
NBD_CMD_WRITE_ZEROES = 6
NBD_CMD_BLOCK_STATUS = 7
NBD_CMD_RESIZE = 8


# =============================================================================
# Protocol Magic Numbers
# =============================================================================

NBD_INIT_PASSWD = b'NBDMAGIC'
NBD_OPTS_MAGIC = 0x49484156454F5054  # "IHAVEOPT" in ASCII
NBD_SERVER_REPLY_MAGIC = 0x3E889045565A9
NBD_CLISERV_MAGIC = 0x420281861253  # Old-style magic
NBD_REQUEST_MAGIC = 0x25609513
NBD_REPLY_MAGIC = 0x67446698


# =============================================================================
# Option Types (New-style negotiation)
# =============================================================================

# Client wants to select an export name
NBD_OPT_EXPORT_NAME = 1
# Abort negotiation and terminate session
NBD_OPT_ABORT = 2
# Return a list of exports
NBD_OPT_LIST = 3
# Not in use
NBD_OPT_PEEK_EXPORT = 4
# Client wants to initiate TLS
NBD_OPT_STARTTLS = 5
# Get more detailed info about an export
NBD_OPT_INFO = 6
# Client wishes to terminate handshake and move to transmission
NBD_OPT_GO = 7


# =============================================================================
# Option Reply Types
# =============================================================================

# Server accepts the option, no further data
NBD_REP_ACK = 1
# A description of an export
NBD_REP_SERVER = 2
# Detailed description of an aspect of an export
NBD_REP_INFO = 3


# =============================================================================
# Error Reply Types (bit 31 set indicates error)
# =============================================================================

NBD_REP_ERR_UNSUP = 0x80000001  # Unsupported option
NBD_REP_ERR_POLICY = 0x80000002  # Policy forbids
NBD_REP_ERR_INVALID = 0x80000003  # Invalid request
NBD_REP_ERR_PLATFORM = 0x80000004  # Platform error
NBD_REP_ERR_TLS_REQD = 0x80000005  # TLS required
NBD_REP_ERR_UNKNOWN = 0x80000006  # Unknown export
NBD_REP_ERR_SHUTDOWN = 0x80000007  # Server shutting down
NBD_REP_ERR_BLOCK_SIZE_REQD = 0x80000008  # Block size required


# =============================================================================
# Error Values (Linux errno)
# =============================================================================

EPERM = 1
EIO = 5
ENOMEM = 12
EINVAL = 22
ENOSPC = 28
EOVERFLOW = 75
ESHUTDOWN = 108


# =============================================================================
# Transmission Flags
# =============================================================================

NBD_FLAG_HAS_FLAGS = 1 << 0
NBD_FLAG_READ_ONLY = 1 << 1
NBD_FLAG_SEND_FLUSH = 1 << 2
NBD_FLAG_SEND_FUA = 1 << 3  # Force Unit Access
NBD_FLAG_ROTATIONAL = 1 << 4
NBD_FLAG_SEND_TRIM = 1 << 5
NBD_FLAG_SEND_WRITE_ZEROES = 1 << 6
NBD_FLAG_SEND_DF = 1 << 7  # Don't Fragment
NBD_FLAG_CAN_MULTI_CONN = 1 << 8
NBD_FLAG_SEND_BLOCK_STATUS = 1 << 9
NBD_FLAG_SEND_RESIZE = 1 << 10


# =============================================================================
# Client Flags (handshake)
# =============================================================================

# New style server that supports extending
NBD_FLAG_C_FIXED_NEWSTYLE = 1 << 0
# Do not send the 128 bytes of empty zeroes
NBD_FLAG_NO_ZEROES = 1 << 1


# =============================================================================
# Default Values
# =============================================================================

DEFAULT_NBD_PORT = 10809
