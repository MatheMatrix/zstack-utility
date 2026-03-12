"""LV Metadata Binary Protocol: constants, aligned I/O, and codec.

Consolidates lv_constants + lv_aligned_io + lv_codec.
Header V2 layout: Architecture field + SchemaVersion moved to VM Summary area.
Python 2 compatible.
"""
from __future__ import absolute_import

import collections
import ctypes
import errno as errno_mod
import hashlib
import os
import struct
import time

# ---- Magic Numbers ----
HEADER_MAGIC = 0x5A534D54          # "ZSMT"
SLOT_MAGIC   = 0x5A534454          # "ZSDT"

HEADER_MAGIC_BYTES = struct.pack('>I', HEADER_MAGIC)
SLOT_MAGIC_BYTES   = struct.pack('>I', SLOT_MAGIC)

# ---- Version ----
CURRENT_HEADER_VERSION   = 2
MAX_KNOWN_HEADER_VERSION = 2

# ---- PendingOp ----
PENDING_NONE            = 0
PENDING_CONFIG_UPDATE   = 1
PENDING_STORAGE_CHANGE  = 2

# ---- Slot Index ----
SLOT_A = 0
SLOT_B = 1

# ---- Alignment & LV Size ----
ALIGNMENT        = 4096
INITIAL_LV_SIZE  = 4  * 1024 * 1024     # 4 MB
MAX_LV_SIZE      = 64 * 1024 * 1024     # 64 MB

# ---- Slot Structure Sizes ----
SLOT_HEADER_SIZE = 36       # Magic(4)+SeqNum(8)+Offset(8)+Cap(8)+PayloadLen(8)
CHECKSUM_SIZE    = 32       # SHA-256 digest
SLOT_OVERHEAD    = SLOT_HEADER_SIZE + CHECKSUM_SIZE   # 68

# ---- Read Tuning ----
OPTIMISTIC_READ_SIZE    = 1 * 1024 * 1024
BRUTE_FORCE_CHUNK_SIZE  = 1 * 1024 * 1024
BRUTE_FORCE_TIMEOUT_SEC = 30

# ---- Known LV Sizes for Layer 2 multi-layout recovery ----
_MB = 1024 * 1024
KNOWN_LV_SIZES = [
    4  * _MB,  6  * _MB,  8  * _MB,
    12 * _MB,  16 * _MB,  24 * _MB,
    32 * _MB,  48 * _MB,  64 * _MB,
]

# ---- Control Area [0:64) ----
# Magic(I) HeaderVer(H) ActiveSlot(B) PendingOp(B)
# WriteSeq(Q) SlotAOff(Q) SlotACap(Q) SlotBOff(Q) SlotBCap(Q)
# LastUpdate(Q) ReservedQ(Q) = 64B
HEADER_FIELDS_FORMAT = '>IHBBQQQQQQQ'
HEADER_FIELDS_SIZE   = struct.calcsize(HEADER_FIELDS_FORMAT)
assert HEADER_FIELDS_SIZE == 64

# ---- ControlChecksum [64:96) ----
CONTROL_CHECKSUM_OFFSET = HEADER_FIELDS_SIZE
CONTROL_CHECKSUM_SIZE   = CHECKSUM_SIZE

# ---- V2 VM Summary [96:936) ----
# VmCategory(B) VmUuid(32s) Architecture(32s) SchemaVersion(Q)
# VmNameLen(H) VmName(765s) = 840B
VM_SUMMARY_OFFSET         = CONTROL_CHECKSUM_OFFSET + CONTROL_CHECKSUM_SIZE  # 96
VM_SUMMARY_DATA_FORMAT_V2 = '>B32s32sQH765s'
VM_SUMMARY_DATA_SIZE_V2   = 840
VM_SUMMARY_CHECKSUM_OFFSET_V2 = VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE_V2  # 936
VM_SUMMARY_END_V2         = VM_SUMMARY_CHECKSUM_OFFSET_V2 + CHECKSUM_SIZE    # 968

# ---- V1 VM Summary (legacy, read-only) [96:928) ----
VM_SUMMARY_DATA_FORMAT_V1 = '>B32sH765s'
VM_SUMMARY_DATA_SIZE_V1   = 800
VM_SUMMARY_CHECKSUM_OFFSET_V1 = VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE_V1  # 896
VM_SUMMARY_END_V1         = VM_SUMMARY_CHECKSUM_OFFSET_V1 + CHECKSUM_SIZE    # 928

# Current write format = V2
VM_SUMMARY_DATA_FORMAT = VM_SUMMARY_DATA_FORMAT_V2
VM_SUMMARY_DATA_SIZE   = VM_SUMMARY_DATA_SIZE_V2
VM_SUMMARY_CHECKSUM_OFFSET = VM_SUMMARY_CHECKSUM_OFFSET_V2
VM_SUMMARY_END         = VM_SUMMARY_END_V2

HEADER_BLOCK_SIZE = 4096

# ---- Slot header [0:36) ----
SLOT_HEADER_FORMAT      = '>IQQQQ'
SLOT_HEADER_STRUCT_SIZE = struct.calcsize(SLOT_HEADER_FORMAT)
assert SLOT_HEADER_STRUCT_SIZE == 36

# ---- I/O Sanity Check ----
IO_CHECK_PATTERN     = b'ZSMT_IO_CHECK'
IO_CHECK_PATTERN_LEN = len(IO_CHECK_PATTERN)

# ---- LV Naming ----
LV_METADATA_SUFFIX = '_vmmeta'
LV_METADATA_TAG    = 'zs::sharedblock::vmmeta'

# ---- Data Classes ----
SlotLayout = collections.namedtuple('SlotLayout', [
    'slot_a_offset',  'slot_a_capacity',
    'slot_b_offset',  'slot_b_capacity',
])

HeaderData = collections.namedtuple('HeaderData', [
    'magic', 'header_version', 'active_slot', 'pending_op',
    'write_sequence',
    'slot_a_offset', 'slot_a_capacity',
    'slot_b_offset', 'slot_b_capacity',
    'last_update_time', 'reserved_q',
    'checksum', 'valid',
    'vm_category', 'vm_uuid', 'architecture',
    'schema_version',
    'vm_name', 'summary_valid',
])

SlotData = collections.namedtuple('SlotData', [
    'magic', 'seq_num', 'slot_offset', 'slot_capacity',
    'payload_len', 'payload', 'checksum', 'valid',
])


class ReadStatus(object):
    OK                          = 'OK'
    NEED_REPAIR                 = 'NEED_REPAIR'
    RECOVERED                   = 'RECOVERED'
    DEGRADED                    = 'DEGRADED'
    STORAGE_CHANGE_INCOMPLETE   = 'STORAGE_CHANGE_INCOMPLETE'
    CORRUPTED                   = 'CORRUPTED'


class ReadResult(object):
    __slots__ = ('status', 'payload', 'header', 'repair_action', 'error')

    def __init__(self, status, payload=None, header=None,
                 repair_action=None, error=None):
        self.status        = status
        self.payload       = payload
        self.header        = header
        self.repair_action = repair_action
        self.error         = error

    def is_usable(self):
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


# ---- Exceptions ----
class MetadataError(Exception):
    pass

class MetadataIOError(MetadataError):
    pass

class MetadataVersionError(MetadataError):
    pass

class MetadataCapacityError(MetadataError):
    pass

class MetadataCorruptedError(MetadataError):
    pass


# ###################################################################
# Aligned I/O
# ###################################################################

_libc = None


def _get_libc():
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL('libc.so.6', use_errno=True)
    return _libc


def align_up(value, alignment=ALIGNMENT):
    return ((value + alignment - 1) // alignment) * alignment


class AlignedBuffer(object):
    """Page-aligned buffer for O_DIRECT I/O.  Use as a context manager."""

    def __init__(self, size, alignment=ALIGNMENT):
        self._alignment = alignment
        self._size = align_up(size, alignment)
        self._ptr = ctypes.c_void_p()
        ret = _get_libc().posix_memalign(
            ctypes.byref(self._ptr), alignment, self._size)
        if ret != 0:
            raise OSError(ret, "posix_memalign failed (size=%d, align=%d)"
                          % (self._size, alignment))
        ctypes.memset(self._ptr, 0, self._size)

    @property
    def size(self):
        return self._size

    def fill(self, data, offset=0):
        n = len(data)
        if offset + n > self._size:
            raise ValueError(
                "data (len=%d) at offset %d exceeds buffer size %d"
                % (n, offset, self._size))
        ctypes.memmove(self._ptr.value + offset, data, n)

    def read(self, length, offset=0):
        if offset + length > self._size:
            raise ValueError(
                "read (len=%d) at offset %d exceeds buffer size %d"
                % (length, offset, self._size))
        return ctypes.string_at(self._ptr.value + offset, length)

    def pwrite(self, fd, file_offset):
        """Handles EINTR and short writes."""
        total_written = 0
        while total_written < self._size:
            ptr = ctypes.c_void_p(self._ptr.value + total_written)
            remaining = self._size - total_written
            ret = _get_libc().pwrite(
                fd, ptr, remaining,
                ctypes.c_longlong(file_offset + total_written))
            if ret < 0:
                err = ctypes.get_errno()
                if err == errno_mod.EINTR:
                    continue
                raise OSError(err,
                              "pwrite failed at offset %d: %s"
                              % (file_offset + total_written,
                                 os.strerror(err)))
            if ret == 0:
                raise OSError(0, "pwrite returned 0 at offset %d"
                              % (file_offset + total_written))
            total_written += ret
        return total_written

    def pread(self, fd, file_offset):
        """Handles EINTR and short reads."""
        total_read = 0
        while total_read < self._size:
            ptr = ctypes.c_void_p(self._ptr.value + total_read)
            remaining = self._size - total_read
            ret = _get_libc().pread(
                fd, ptr, remaining,
                ctypes.c_longlong(file_offset + total_read))
            if ret < 0:
                err = ctypes.get_errno()
                if err == errno_mod.EINTR:
                    continue
                raise OSError(err,
                              "pread failed at offset %d: %s"
                              % (file_offset + total_read,
                                 os.strerror(err)))
            if ret == 0:
                break
            total_read += ret
        return total_read

    def close(self):
        if self._ptr.value:
            _get_libc().free(self._ptr)
            self._ptr = ctypes.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()


def aligned_pwrite(fd, data, file_offset, alignment=ALIGNMENT):
    with AlignedBuffer(len(data), alignment) as buf:
        buf.fill(data)
        return buf.pwrite(fd, file_offset)


def aligned_pread(fd, size, file_offset, alignment=ALIGNMENT):
    with AlignedBuffer(size, alignment) as buf:
        buf.pread(fd, file_offset)
        return buf.read(buf.size)


def open_lv(lv_path, readonly=False):
    flags = os.O_RDONLY if readonly else os.O_RDWR
    flags |= os.O_DIRECT | os.O_SYNC
    return os.open(lv_path, flags)


# ###################################################################
# Codec
# ###################################################################

def build_header(active_slot, pending_op, write_sequence,
                 slot_a_offset, slot_a_capacity,
                 slot_b_offset, slot_b_capacity,
                 last_update_time, schema_version,
                 vm_category=0, vm_uuid='', vm_name='',
                 architecture=''):
    """Serialise a 4096-byte Header Block (V2 layout).

    [0:64)    Control Area (last Q = reserved, written as 0)
    [64:96)   ControlChecksum
    [96:936)  VM Summary (V2: +Architecture +SchemaVersion)
    [936:968) SummaryChecksum
    [968:4096) Reserved
    """
    # Control Area [0:64) -- last Q is reserved, always 0
    fields = struct.pack(
        HEADER_FIELDS_FORMAT,
        HEADER_MAGIC, CURRENT_HEADER_VERSION,
        active_slot, pending_op,
        write_sequence,
        slot_a_offset, slot_a_capacity,
        slot_b_offset, slot_b_capacity,
        last_update_time, 0,
    )
    control_checksum = hashlib.sha256(fields).digest()

    vm_summary_data = _build_vm_summary(vm_category, vm_uuid, vm_name,
                                        architecture, schema_version)
    summary_checksum = hashlib.sha256(vm_summary_data).digest()

    block = bytearray(HEADER_BLOCK_SIZE)
    block[0:HEADER_FIELDS_SIZE] = fields
    block[CONTROL_CHECKSUM_OFFSET:CONTROL_CHECKSUM_OFFSET + CONTROL_CHECKSUM_SIZE] = control_checksum
    block[VM_SUMMARY_OFFSET:VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE_V2] = vm_summary_data
    block[VM_SUMMARY_CHECKSUM_OFFSET_V2:VM_SUMMARY_CHECKSUM_OFFSET_V2 + CHECKSUM_SIZE] = summary_checksum
    return bytes(block)


def _build_vm_summary(vm_category, vm_uuid, vm_name,
                      architecture='', schema_version=0):
    """Build 840-byte V2 VM Summary data."""
    if isinstance(vm_uuid, bytes):
        uuid_bytes = vm_uuid
    else:
        uuid_bytes = vm_uuid.encode('utf-8') if vm_uuid else b''
    if isinstance(vm_name, bytes):
        name_bytes = vm_name
    else:
        name_bytes = vm_name.encode('utf-8') if vm_name else b''
    if isinstance(architecture, bytes):
        arch_bytes = architecture
    else:
        arch_bytes = architecture.encode('utf-8') if architecture else b''
    name_len = min(len(name_bytes), 765)
    name_bytes = name_bytes[:name_len]

    return struct.pack(VM_SUMMARY_DATA_FORMAT_V2,
                       vm_category, uuid_bytes, arch_bytes,
                       schema_version, name_len, name_bytes)


def _parse_vm_summary_v2(block):
    """Returns (vm_category, vm_uuid, architecture, schema_version, vm_name, summary_valid)."""
    if len(block) < VM_SUMMARY_END_V2:
        return 0, '', '', 0, '', False

    summary_data = block[VM_SUMMARY_OFFSET:VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE_V2]
    stored_checksum = block[VM_SUMMARY_CHECKSUM_OFFSET_V2:
                            VM_SUMMARY_CHECKSUM_OFFSET_V2 + CHECKSUM_SIZE]

    if hashlib.sha256(summary_data).digest() != stored_checksum:
        return 0, '', '', 0, '', False

    try:
        vm_category, uuid_raw, arch_raw, schema_ver, name_len, name_raw = struct.unpack(
            VM_SUMMARY_DATA_FORMAT_V2, summary_data)
    except struct.error:
        return 0, '', '', 0, '', False

    vm_uuid = uuid_raw.rstrip(b'\x00').decode('utf-8', 'replace')
    architecture = arch_raw.rstrip(b'\x00').decode('utf-8', 'replace')
    actual_name_len = min(name_len, 765)
    vm_name = name_raw[:actual_name_len].rstrip(b'\x00').decode('utf-8', 'replace')

    return vm_category, vm_uuid, architecture, schema_ver, vm_name, True


def _parse_vm_summary_v1(block):
    """V1 legacy parser. architecture='', schema_version from control area."""
    if len(block) < VM_SUMMARY_END_V1:
        return 0, '', '', 0, '', False

    summary_data = block[VM_SUMMARY_OFFSET:VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE_V1]
    stored_checksum = block[VM_SUMMARY_CHECKSUM_OFFSET_V1:
                            VM_SUMMARY_CHECKSUM_OFFSET_V1 + CHECKSUM_SIZE]

    if hashlib.sha256(summary_data).digest() != stored_checksum:
        return 0, '', '', 0, '', False

    try:
        vm_category, uuid_raw, name_len, name_raw = struct.unpack(
            VM_SUMMARY_DATA_FORMAT_V1, summary_data)
    except struct.error:
        return 0, '', '', 0, '', False

    vm_uuid = uuid_raw.rstrip(b'\x00').decode('utf-8', 'replace')
    actual_name_len = min(name_len, 765)
    vm_name = name_raw[:actual_name_len].rstrip(b'\x00').decode('utf-8', 'replace')

    return vm_category, vm_uuid, '', 0, vm_name, True


def parse_header(block):
    """Deserialise a 4096-byte Header Block (supports V1 and V2)."""
    if len(block) < HEADER_BLOCK_SIZE:
        return _invalid_header()

    fields_bytes = block[:HEADER_FIELDS_SIZE]
    stored_checksum = block[CONTROL_CHECKSUM_OFFSET:
                            CONTROL_CHECKSUM_OFFSET + CONTROL_CHECKSUM_SIZE]
    try:
        values = struct.unpack(HEADER_FIELDS_FORMAT, fields_bytes)
    except struct.error:
        return _invalid_header()

    (magic, header_version, active_slot, pending_op,
     write_sequence,
     slot_a_offset, slot_a_capacity,
     slot_b_offset, slot_b_capacity,
     last_update_time, reserved_q) = values

    valid = True
    if magic != HEADER_MAGIC:
        valid = False
    elif header_version > MAX_KNOWN_HEADER_VERSION:
        valid = False
    elif hashlib.sha256(fields_bytes).digest() != stored_checksum:
        valid = False

    # V2: summary has architecture + schema_version
    # V1: schema_version was in control area's last Q field (now reserved_q)
    if header_version >= 2:
        (vm_category, vm_uuid, architecture,
         schema_version, vm_name, summary_valid) = _parse_vm_summary_v2(block)
    else:
        (vm_category, vm_uuid, architecture,
         _sv_ignored, vm_name, summary_valid) = _parse_vm_summary_v1(block)
        schema_version = reserved_q

    return HeaderData(
        magic=magic, header_version=header_version,
        active_slot=active_slot, pending_op=pending_op,
        write_sequence=write_sequence,
        slot_a_offset=slot_a_offset, slot_a_capacity=slot_a_capacity,
        slot_b_offset=slot_b_offset, slot_b_capacity=slot_b_capacity,
        last_update_time=last_update_time,
        reserved_q=reserved_q,
        checksum=stored_checksum, valid=valid,
        vm_category=vm_category, vm_uuid=vm_uuid,
        architecture=architecture,
        schema_version=schema_version,
        vm_name=vm_name, summary_valid=summary_valid,
    )


def parse_header_raw_hints(block, lv_size):
    """Extract raw field hints from a corrupted Header (Layer 1 recovery).
    Only trusts hints when Magic is correct (likely partial corruption).
    """
    if len(block) < HEADER_FIELDS_SIZE:
        return {}
    try:
        values = struct.unpack(HEADER_FIELDS_FORMAT, block[:HEADER_FIELDS_SIZE])
    except struct.error:
        return {}

    (magic, _hv, active_slot, _pop,
     _wseq,
     slot_a_offset, slot_a_capacity,
     slot_b_offset, slot_b_capacity,
     _lut, _rq) = values

    if magic != HEADER_MAGIC:
        return {}

    hints = {}
    if active_slot in (0, 1):
        hints['active_slot'] = active_slot
    if 0 < slot_a_offset < lv_size:
        hints['slot_a_offset'] = slot_a_offset
    if slot_a_capacity > 0:
        hints['slot_a_capacity'] = slot_a_capacity
    if 0 < slot_b_offset < lv_size and slot_b_offset > slot_a_offset:
        hints['slot_b_offset'] = slot_b_offset
    if slot_b_capacity > 0:
        hints['slot_b_capacity'] = slot_b_capacity
    return hints


def _invalid_header():
    return HeaderData(
        magic=0, header_version=0, active_slot=0, pending_op=0,
        write_sequence=0,
        slot_a_offset=0, slot_a_capacity=0,
        slot_b_offset=0, slot_b_capacity=0,
        last_update_time=0, reserved_q=0,
        checksum=b'', valid=False,
        vm_category=0, vm_uuid='', architecture='',
        schema_version=0,
        vm_name='', summary_valid=False,
    )


def build_slot(seq_num, slot_offset, slot_capacity, payload):
    payload_len = len(payload)
    header_bytes = struct.pack(
        SLOT_HEADER_FORMAT,
        SLOT_MAGIC, seq_num, slot_offset, slot_capacity, payload_len,
    )
    data_without_checksum = header_bytes + payload
    checksum = hashlib.sha256(data_without_checksum).digest()
    return data_without_checksum + checksum


def parse_slot(data, expected_offset=None, expected_capacity=None,
               strict=True):
    if len(data) < SLOT_HEADER_STRUCT_SIZE:
        return _invalid_slot()

    try:
        values = struct.unpack(SLOT_HEADER_FORMAT,
                               data[:SLOT_HEADER_STRUCT_SIZE])
    except struct.error:
        return _invalid_slot()

    magic, seq_num, slot_offset, slot_capacity, payload_len = values

    if magic != SLOT_MAGIC:
        return _invalid_slot()
    if expected_offset is not None and slot_offset != expected_offset:
        return _invalid_slot()
    if strict and expected_capacity is not None \
            and slot_capacity != expected_capacity:
        return _invalid_slot()
    if payload_len == 0:
        return _invalid_slot()
    if slot_capacity > SLOT_OVERHEAD:
        max_payload = slot_capacity - SLOT_OVERHEAD
    else:
        max_payload = len(data) - SLOT_OVERHEAD
    if payload_len > max_payload:
        return _invalid_slot()

    total_needed = SLOT_HEADER_STRUCT_SIZE + payload_len + CHECKSUM_SIZE
    if len(data) < total_needed:
        return _invalid_slot()

    payload = data[SLOT_HEADER_STRUCT_SIZE:
                   SLOT_HEADER_STRUCT_SIZE + payload_len]
    cs_start = SLOT_HEADER_STRUCT_SIZE + payload_len
    stored_checksum = data[cs_start:cs_start + CHECKSUM_SIZE]

    computed = hashlib.sha256(
        data[:SLOT_HEADER_STRUCT_SIZE + payload_len]).digest()
    if computed != stored_checksum:
        return _invalid_slot()

    return SlotData(
        magic=magic, seq_num=seq_num,
        slot_offset=slot_offset, slot_capacity=slot_capacity,
        payload_len=payload_len, payload=payload,
        checksum=stored_checksum, valid=True,
    )


def _invalid_slot():
    return SlotData(
        magic=0, seq_num=0, slot_offset=0, slot_capacity=0,
        payload_len=0, payload=b'', checksum=b'', valid=False,
    )


def current_epoch_ms():
    return int(time.time() * 1000)


def encode_schema_version(major, minor, patch=0):
    return (major << 40) | (minor << 20) | patch


def decode_schema_version(value):
    major = (value >> 40) & 0xFFFFF
    minor = (value >> 20) & 0xFFFFF
    patch = value & 0xFFFFF
    return (major, minor, patch)
