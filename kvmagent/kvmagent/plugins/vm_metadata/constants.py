"""VM Metadata Binary Protocol Constants for sblk (Shared Block Storage).

Implements the AB Dual Slot protocol defined in vm-metadata-04a-sblk-overview.md
and vm-metadata-04b-sblk-binary-layout.md.  Python 2/3 compatible.
"""
from __future__ import absolute_import

import struct
import collections

# ---------------------------------------------------------------------------
# Magic Numbers
# ---------------------------------------------------------------------------
HEADER_MAGIC = 0x5A534D54          # ASCII "ZSMT" (ZStack Metadata)
SLOT_MAGIC   = 0x5A534454          # ASCII "ZSDT" (ZStack Data)

HEADER_MAGIC_BYTES = struct.pack('>I', HEADER_MAGIC)   # b'ZSMT'
SLOT_MAGIC_BYTES   = struct.pack('>I', SLOT_MAGIC)     # b'ZSDT'

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
CURRENT_HEADER_VERSION  = 1
MAX_KNOWN_HEADER_VERSION = 1

# ---------------------------------------------------------------------------
# PendingOp values
# ---------------------------------------------------------------------------
PENDING_NONE            = 0
PENDING_CONFIG_UPDATE   = 1
PENDING_STORAGE_CHANGE  = 2

# ---------------------------------------------------------------------------
# Slot Index
# ---------------------------------------------------------------------------
SLOT_A = 0
SLOT_B = 1

# ---------------------------------------------------------------------------
# Alignment & LV Size
# ---------------------------------------------------------------------------
ALIGNMENT        = 4096                  # O_DIRECT page alignment (4 KB)
INITIAL_LV_SIZE  = 4  * 1024 * 1024     # 4 MB
MAX_LV_SIZE      = 64 * 1024 * 1024     # 64 MB

# ---------------------------------------------------------------------------
# Slot Structure Sizes
# ---------------------------------------------------------------------------
SLOT_HEADER_SIZE = 36       # Magic(4) + SeqNum(8) + Offset(8) + Cap(8) + PayloadLen(8)
CHECKSUM_SIZE    = 32       # SHA-256 binary digest
SLOT_OVERHEAD    = SLOT_HEADER_SIZE + CHECKSUM_SIZE   # 68 bytes

# ---------------------------------------------------------------------------
# Read Tuning
# ---------------------------------------------------------------------------
OPTIMISTIC_READ_SIZE    = 1 * 1024 * 1024   # 1 MB – covers most payloads in one read
BRUTE_FORCE_CHUNK_SIZE  = 1 * 1024 * 1024   # 1 MB per scan chunk
BRUTE_FORCE_TIMEOUT_SEC = 30                # Global timeout for brute-force scan (§4.1)

# ---------------------------------------------------------------------------
# Known LV Sizes for Layer 2 multi-layout recovery (§3.3)
# ---------------------------------------------------------------------------
_MB = 1024 * 1024
KNOWN_LV_SIZES = [
    4  * _MB,  6  * _MB,  8  * _MB,
    12 * _MB,  16 * _MB,  24 * _MB,
    32 * _MB,  48 * _MB,  64 * _MB,
]

# ---------------------------------------------------------------------------
# Struct Formats  (Big Endian, Standard Size – NO implicit padding)
# ---------------------------------------------------------------------------
# Control Area [0:64]:
#   Magic(I=4) HeaderVer(H=2) ActiveSlot(B=1) PendingOp(B=1)
#   WriteSeq(Q=8) SlotAOff(Q=8) SlotACap(Q=8) SlotBOff(Q=8) SlotBCap(Q=8)
#   LastUpdate(Q=8) SchemaVersion(Q=8)
#   Total = 4+2+1+1 + 8*7 = 64
HEADER_FIELDS_FORMAT = '>IHBBQQQQQQQ'
HEADER_FIELDS_SIZE   = struct.calcsize(HEADER_FIELDS_FORMAT)    # 64
assert HEADER_FIELDS_SIZE == 64, "Header fields must be exactly 64 bytes"

# ControlChecksum [64:96]:  SHA-256 of [0:64]
CONTROL_CHECKSUM_OFFSET = HEADER_FIELDS_SIZE                    # 64
CONTROL_CHECKSUM_SIZE   = CHECKSUM_SIZE                         # 32

# VM Summary Area [96:928]:
#   VmCategory(B=1) VmUuid(32s) VmNameLen(H=2) VmName(765s) = 800 bytes [96:896]
#   SummaryChecksum(32s) at [896:928]
VM_SUMMARY_OFFSET    = CONTROL_CHECKSUM_OFFSET + CONTROL_CHECKSUM_SIZE   # 96
VM_SUMMARY_DATA_SIZE = 800   # VmCategory(1) + VmUuid(32) + VmNameLen(2) + VmName(765)
VM_SUMMARY_DATA_FORMAT = '>B32sH765s'
VM_SUMMARY_CHECKSUM_OFFSET = VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE   # 896
VM_SUMMARY_END       = VM_SUMMARY_CHECKSUM_OFFSET + CHECKSUM_SIZE       # 928

HEADER_BLOCK_SIZE = 4096    # Full header block (control + checksum + VM summary + padding)

# Slot header [0:36]:
#   Magic(I=4) SeqNum(Q=8) SlotOffset(Q=8) SlotCapacity(Q=8) PayloadLen(Q=8)
#   Total = 4 + 8*4 = 36
SLOT_HEADER_FORMAT      = '>IQQQQ'
SLOT_HEADER_STRUCT_SIZE = struct.calcsize(SLOT_HEADER_FORMAT)   # 36
assert SLOT_HEADER_STRUCT_SIZE == 36, "Slot header must be exactly 36 bytes"

# ---------------------------------------------------------------------------
# I/O Sanity Check
# ---------------------------------------------------------------------------
IO_CHECK_PATTERN     = b'ZSMT_IO_CHECK'
IO_CHECK_PATTERN_LEN = len(IO_CHECK_PATTERN)   # 13

# ---------------------------------------------------------------------------
# LV Naming
# ---------------------------------------------------------------------------
LV_METADATA_SUFFIX = '_vmmeta'
LV_METADATA_TAG    = 'zs::sharedblock::vmmeta'

# ---------------------------------------------------------------------------
# Data Classes  (immutable namedtuples – cheap & Python 2 safe)
# ---------------------------------------------------------------------------
SlotLayout = collections.namedtuple('SlotLayout', [
    'slot_a_offset',  'slot_a_capacity',
    'slot_b_offset',  'slot_b_capacity',
])

HeaderData = collections.namedtuple('HeaderData', [
    'magic', 'header_version', 'active_slot', 'pending_op',
    'write_sequence',
    'slot_a_offset', 'slot_a_capacity',
    'slot_b_offset', 'slot_b_capacity',
    'last_update_time', 'schema_version',
    'checksum', 'valid',
    'vm_category', 'vm_uuid', 'vm_name', 'summary_valid',
])

SlotData = collections.namedtuple('SlotData', [
    'magic', 'seq_num', 'slot_offset', 'slot_capacity',
    'payload_len', 'payload', 'checksum', 'valid',
])


# ---------------------------------------------------------------------------
# Read Status
# ---------------------------------------------------------------------------
class ReadStatus(object):
    """Result status of a read_metadata() call – see §6.2.4 of the spec."""
    OK                          = 'OK'
    NEED_REPAIR                 = 'NEED_REPAIR'
    RECOVERED                   = 'RECOVERED'
    DEGRADED                    = 'DEGRADED'
    STORAGE_CHANGE_INCOMPLETE   = 'STORAGE_CHANGE_INCOMPLETE'
    CORRUPTED                   = 'CORRUPTED'


class ReadResult(object):
    """Container for read_metadata() outcome."""
    __slots__ = ('status', 'payload', 'header', 'repair_action', 'error')

    def __init__(self, status, payload=None, header=None,
                 repair_action=None, error=None):
        self.status        = status
        self.payload       = payload
        self.header        = header
        self.repair_action = repair_action
        self.error         = error

    def is_usable(self):
        """True if the payload can be safely used (may still need repair)."""
        return self.status in (ReadStatus.OK,
                               ReadStatus.NEED_REPAIR,
                               ReadStatus.RECOVERED,
                               ReadStatus.DEGRADED)

    def __repr__(self):
        return ("ReadResult(status=%s, payload_len=%s, repair=%s, error=%s)"
                % (self.status,
                   len(self.payload) if self.payload else 0,
                   self.repair_action,
                   self.error))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class MetadataError(Exception):
    """Base exception for all metadata operations."""


class MetadataIOError(MetadataError):
    """I/O error (O_DIRECT sanity check, pread/pwrite failure, etc.)."""


class MetadataVersionError(MetadataError):
    """Unsupported HeaderVersion or SchemaVersion."""


class MetadataCapacityError(MetadataError):
    """Payload exceeds the maximum LV capacity (64 MB)."""


class MetadataCorruptedError(MetadataError):
    """Both slots corrupted; full-refresh required."""
