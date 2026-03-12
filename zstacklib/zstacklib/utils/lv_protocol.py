import collections
import ctypes
import errno as errno_mod
import hashlib
import json
import os
import struct
import time

# ---- Magic Numbers ----
HEADER_MAGIC = 0x5A534D54  # "ZSMT"
SLOT_MAGIC = 0x5A534454  # "ZSDT"

SLOT_MAGIC_BYTES = struct.pack('>I', SLOT_MAGIC)

# ---- Version ----
CURRENT_HEADER_VERSION = 1

# ---- PendingOp ----
PENDING_NONE = 0
PENDING_CONFIG_UPDATE = 1
PENDING_STORAGE_CHANGE = 2

# ---- Slot Index ----
SLOT_A = 0
SLOT_B = 1

# ---- Alignment & LV Size ----
ALIGNMENT = 4096
INITIAL_LV_SIZE = 4 * 1024 * 1024  # 4 MB
MAX_LV_SIZE = 64 * 1024 * 1024  # 64 MB

# ---- Slot Structure Sizes ----
SLOT_HEADER_SIZE = 36  # Magic(4)+SeqNum(8)+Offset(8)+Cap(8)+PayloadLen(8)
CHECKSUM_SIZE = 32  # SHA-256 digest
SLOT_OVERHEAD = SLOT_HEADER_SIZE + CHECKSUM_SIZE  # 68

# ---- Read Tuning ----
OPTIMISTIC_READ_SIZE = 1 * 1024 * 1024
BRUTE_FORCE_CHUNK_SIZE = 1 * 1024 * 1024
BRUTE_FORCE_TIMEOUT_SEC = 30

# ---- Known LV Sizes for Layer 2 multi-layout recovery ----
_MB = 1024 * 1024
KNOWN_LV_SIZES = [
    4 * _MB, 6 * _MB, 8 * _MB,
    12 * _MB, 16 * _MB, 24 * _MB,
    32 * _MB, 48 * _MB, 64 * _MB,
]

# ---- JSON Header Layout ----
# [0:4)      Magic         uint32 BE   0x5A534D54
# [4:6)      HeaderVersion uint16 BE   1
# [6:8)      JsonLen       uint16 BE   JSON byte length
# [8:8+N)    JSON Body     UTF-8       control fields + VM summary
# [8+N:4064) Zero Padding
# [4064:4096) Checksum     SHA-256(bytes[0:4064])
HEADER_BLOCK_SIZE = 4096
HEADER_JSON_OFFSET = 8
HEADER_CHECKSUM_OFFSET = 4064
HEADER_JSON_MAX_LEN = HEADER_CHECKSUM_OFFSET - HEADER_JSON_OFFSET  # 4056

# ---- Slot header [0:36) ----
SLOT_HEADER_FORMAT = '>IQQQQ'
SLOT_HEADER_STRUCT_SIZE = struct.calcsize(SLOT_HEADER_FORMAT)
assert SLOT_HEADER_STRUCT_SIZE == 36

# ---- I/O Sanity Check ----
# Prefix must NOT start with HEADER_MAGIC (b'ZSMT') -- otherwise
# parse_header_raw_hints would mistake residual check data for a valid
# header after a failed initialisation.
IO_CHECK_PATTERN = b'ZS_IOCHECK_OK'
IO_CHECK_PATTERN_LEN = len(IO_CHECK_PATTERN)

# ---- LV Naming ----
LV_METADATA_SUFFIX = '_vmmeta'
LV_METADATA_TAG = 'zs::sharedblock::vmmeta'

# ---- Data Classes ----
SlotLayout = collections.namedtuple('SlotLayout', [
    'slot_a_offset', 'slot_a_capacity',
    'slot_b_offset', 'slot_b_capacity',
])

HeaderData = collections.namedtuple('HeaderData', [
    'magic', 'header_version', 'active_slot', 'pending_op',
    'write_sequence',
    'slot_a_offset', 'slot_a_capacity',
    'slot_b_offset', 'slot_b_capacity',
    'last_update_time',
    'checksum', 'valid',
    'vm_category', 'vm_uuid', 'architecture',
    'schema_version', 'vm_name',
])

SlotData = collections.namedtuple('SlotData', [
    'magic', 'seq_num', 'slot_offset', 'slot_capacity',
    'payload_len', 'payload', 'checksum', 'valid',
])


class ReadStatus(object):
    OK = 'OK'
    NEED_REPAIR = 'NEED_REPAIR'
    RECOVERED = 'RECOVERED'
    DEGRADED = 'DEGRADED'
    STORAGE_CHANGE_INCOMPLETE = 'STORAGE_CHANGE_INCOMPLETE'
    CORRUPTED = 'CORRUPTED'


class ReadResult(object):
    __slots__ = ('status', 'payload', 'header', 'repair_action', 'error')

    def __init__(self, status, payload=None, header=None,
                 repair_action=None, error=None):
        self.status = status
        self.payload = payload
        self.header = header
        self.repair_action = repair_action
        self.error = error

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


class MetadataCapacityError(MetadataError):
    pass


# ###################################################################
# Aligned I/O
# ###################################################################

_libc = None


def _get_libc():
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL('libc.so.6', use_errno=True)
        _libc.pwrite.restype = ctypes.c_ssize_t
        _libc.pwrite.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                 ctypes.c_size_t, ctypes.c_longlong]
        _libc.pread.restype = ctypes.c_ssize_t
        _libc.pread.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                ctypes.c_size_t, ctypes.c_longlong]
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
            raise OSError(ret, "posix_memalign failed (size=%d, align=%d)" % (self._size, alignment))
        ctypes.memset(self._ptr, 0, self._size)

    @property
    def size(self):
        return self._size

    def fill(self, data, offset=0):
        n = len(data)
        if offset + n > self._size:
            raise ValueError("data (len=%d) at offset %d exceeds buffer size %d" % (n, offset, self._size))
        ctypes.memmove(self._ptr.value + offset, data, n)

    def read(self, length, offset=0):
        if offset + length > self._size:
            raise ValueError("read (len=%d) at offset %d exceeds buffer size %d" % (length, offset, self._size))
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
                raise OSError(err, "pwrite failed at offset %d: %s" % (file_offset + total_written, os.strerror(err)))
            if ret == 0:
                raise OSError(0, "pwrite returned 0 at offset %d" % (file_offset + total_written))
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
                raise OSError(err, "pread failed at offset %d: %s" % (file_offset + total_read, os.strerror(err)))
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
        read_len = buf.pread(fd, file_offset)
        return buf.read(min(size, read_len))


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
                 vm_category='', vm_uuid='', vm_name='',
                 architecture=''):
    """Serialise a 4096-byte Header Block (JSON layout).

    [0:4)      Magic         uint32 BE   0x5A534D54
    [4:6)      HeaderVersion uint16 BE   1
    [6:8)      JsonLen       uint16 BE   JSON byte length
    [8:8+N)    JSON Body     UTF-8       control fields + VM summary
    [8+N:4064) Zero Padding
    [4064:4096) Checksum     SHA-256(bytes[0:4064])
    """
    header_dict = {
        'activeSlot': active_slot,
        'pendingOp': pending_op,
        'writeSequence': write_sequence,
        'slotAOffset': slot_a_offset,
        'slotACapacity': slot_a_capacity,
        'slotBOffset': slot_b_offset,
        'slotBCapacity': slot_b_capacity,
        'lastUpdateTime': last_update_time,
        'schemaVersion': str(schema_version) if not isinstance(schema_version, str) else schema_version,
    }
    if vm_category:
        header_dict['vmCategory'] = vm_category
    if vm_uuid:
        header_dict['vmUuid'] = vm_uuid
    if vm_name:
        header_dict['vmName'] = vm_name
    if architecture:
        header_dict['architecture'] = architecture

    json_str = json.dumps(header_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    json_bytes = json_str.encode('utf-8')
    json_len = len(json_bytes)

    if json_len > HEADER_JSON_MAX_LEN:
        raise ValueError("Header JSON too large: %d bytes (max %d)" % (json_len, HEADER_JSON_MAX_LEN))

    block = bytearray(HEADER_BLOCK_SIZE)
    struct.pack_into('>I', block, 0, HEADER_MAGIC)
    struct.pack_into('>H', block, 4, CURRENT_HEADER_VERSION)
    struct.pack_into('>H', block, 6, json_len)
    block[HEADER_JSON_OFFSET:HEADER_JSON_OFFSET + json_len] = json_bytes
    checksum = hashlib.sha256(bytes(block[:HEADER_CHECKSUM_OFFSET])).digest()
    block[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + CHECKSUM_SIZE] = checksum
    return bytes(block)


def parse_header(block):
    """Deserialise a 4096-byte Header Block."""
    if len(block) < HEADER_BLOCK_SIZE:
        return _invalid_header()

    magic = struct.unpack_from('>I', block, 0)[0]
    if magic != HEADER_MAGIC:
        return _invalid_header()

    header_version = struct.unpack_from('>H', block, 4)[0]
    if header_version > CURRENT_HEADER_VERSION:
        return _invalid_header()

    json_len = struct.unpack_from('>H', block, 6)[0]
    if json_len == 0 or json_len > HEADER_JSON_MAX_LEN:
        return _invalid_header()

    # Checksum verification
    stored_checksum = bytes(block[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + CHECKSUM_SIZE])
    computed = hashlib.sha256(block[:HEADER_CHECKSUM_OFFSET]).digest()
    if computed != stored_checksum:
        return _invalid_header()

    # JSON parsing
    try:
        json_str = block[HEADER_JSON_OFFSET:HEADER_JSON_OFFSET + json_len].decode('utf-8')
        d = json.loads(json_str)
    except (ValueError, UnicodeDecodeError):
        return _invalid_header()

    if not isinstance(d, dict):
        return _invalid_header()

    # Semantic validation: reject checksum-correct but logically invalid headers
    active_slot = d.get('activeSlot', 0)
    if active_slot not in (SLOT_A, SLOT_B):
        return _invalid_header()

    pending_op = d.get('pendingOp', 0)
    if pending_op not in (PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE):
        return _invalid_header()

    write_sequence = d.get('writeSequence', 0)
    if not isinstance(write_sequence, int) or write_sequence < 0:
        return _invalid_header()

    slot_a_offset = d.get('slotAOffset', 0)
    slot_a_capacity = d.get('slotACapacity', 0)
    slot_b_offset = d.get('slotBOffset', 0)
    slot_b_capacity = d.get('slotBCapacity', 0)
    for val in (slot_a_offset, slot_a_capacity, slot_b_offset, slot_b_capacity):
        if not isinstance(val, int) or val < 0:
            return _invalid_header()

    if slot_a_offset < ALIGNMENT:              # must be after header block
        return _invalid_header()
    if slot_b_offset <= slot_a_offset:          # B must follow A
        return _invalid_header()

    last_update_time = d.get('lastUpdateTime', 0)
    if not isinstance(last_update_time, (int, float)) or last_update_time < 0:
        return _invalid_header()

    return HeaderData(
        magic=magic,
        header_version=header_version,
        active_slot=active_slot,
        pending_op=pending_op,
        write_sequence=write_sequence,
        slot_a_offset=slot_a_offset,
        slot_a_capacity=slot_a_capacity,
        slot_b_offset=slot_b_offset,
        slot_b_capacity=slot_b_capacity,
        last_update_time=last_update_time,
        checksum=stored_checksum,
        valid=True,
        vm_category=d.get('vmCategory', ''),
        vm_uuid=d.get('vmUuid', ''),
        architecture=d.get('architecture', ''),
        schema_version=d.get('schemaVersion', '0'),
        vm_name=d.get('vmName', ''),
    )


def parse_header_raw_hints(block, lv_size):
    """Extract raw field hints from a corrupted Header (Layer 1 recovery).

    Best-effort JSON extraction -- checksum is NOT verified so that
    partially-corrupted headers can still provide slot layout hints.
    """
    if len(block) < HEADER_JSON_OFFSET + 2:
        return {}

    magic = struct.unpack_from('>I', block, 0)[0]
    if magic != HEADER_MAGIC:
        return {}

    json_len = struct.unpack_from('>H', block, 6)[0]
    if json_len == 0 or json_len > HEADER_JSON_MAX_LEN:
        return {}
    if len(block) < HEADER_JSON_OFFSET + json_len:
        return {}

    try:
        json_str = block[HEADER_JSON_OFFSET:HEADER_JSON_OFFSET + json_len].decode('utf-8')
        d = json.loads(json_str)
    except (ValueError, UnicodeDecodeError):
        return {}

    if not isinstance(d, dict):
        return {}

    hints = {}
    active_slot = d.get('activeSlot')
    if active_slot in (0, 1):
        hints['active_slot'] = active_slot

    slot_a_offset = d.get('slotAOffset', 0)
    slot_a_valid = False
    if 0 < slot_a_offset < lv_size:
        hints['slot_a_offset'] = slot_a_offset
        slot_a_valid = True

    slot_a_capacity = d.get('slotACapacity', 0)
    if slot_a_capacity > 0:
        if slot_a_valid and slot_a_offset + slot_a_capacity > lv_size:
            slot_a_valid = False
            hints.pop('slot_a_offset', None)
        else:
            hints['slot_a_capacity'] = slot_a_capacity

    slot_b_offset = d.get('slotBOffset', 0)
    slot_b_valid = False
    if 0 < slot_b_offset < lv_size and (
            not slot_a_valid or slot_b_offset > slot_a_offset):
        hints['slot_b_offset'] = slot_b_offset
        slot_b_valid = True

    slot_b_capacity = d.get('slotBCapacity', 0)
    if slot_b_capacity > 0:
        if slot_b_valid and slot_b_offset + slot_b_capacity > lv_size:
            slot_b_valid = False
            hints.pop('slot_b_offset', None)
        else:
            hints['slot_b_capacity'] = slot_b_capacity

    return hints


def _invalid_header():
    return HeaderData(
        magic=0, header_version=0, active_slot=0, pending_op=0,
        write_sequence=0,
        slot_a_offset=0, slot_a_capacity=0,
        slot_b_offset=0, slot_b_capacity=0,
        last_update_time=0,
        checksum=b'', valid=False,
        vm_category='', vm_uuid='', architecture='',
        schema_version='',
        vm_name='',
    )


def build_slot(seq_num, slot_offset, slot_capacity, payload):
    if not payload:
        raise ValueError("payload must not be empty")
    payload_len = len(payload)
    total_len = SLOT_HEADER_STRUCT_SIZE + payload_len + CHECKSUM_SIZE  # header + payload + SHA-256
    if total_len > slot_capacity:
        raise ValueError("payload too large: total %d bytes exceeds slot capacity %d" % (total_len, slot_capacity))
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
