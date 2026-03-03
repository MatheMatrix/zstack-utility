"""Header & Slot binary encode / decode for the AB Dual Slot protocol.

Covers vm-metadata-04b-sblk-binary-layout.md:
  - Header Block (4096 B) – build & parse
  - Slot structure (36 + N + 32 B) – build & parse
  - Layer-1 raw-hint extraction for corrupted headers

All multi-byte integers are Big Endian (network byte order).
Checksums are SHA-256 binary (32 bytes, not hex).
"""
from __future__ import absolute_import

import struct
import hashlib
import time

from .constants import (
    HEADER_MAGIC, SLOT_MAGIC,
    CURRENT_HEADER_VERSION, MAX_KNOWN_HEADER_VERSION,
    HEADER_FIELDS_FORMAT, HEADER_FIELDS_SIZE,
    HEADER_BLOCK_SIZE, CHECKSUM_SIZE,
    CONTROL_CHECKSUM_OFFSET, CONTROL_CHECKSUM_SIZE,
    VM_SUMMARY_OFFSET, VM_SUMMARY_DATA_SIZE, VM_SUMMARY_DATA_FORMAT,
    VM_SUMMARY_CHECKSUM_OFFSET, VM_SUMMARY_END,
    SLOT_HEADER_FORMAT, SLOT_HEADER_STRUCT_SIZE,
    SLOT_OVERHEAD,
    HeaderData, SlotData,
)


# ===================================================================
# Header Block  (4096 B)
# ===================================================================

def build_header(active_slot, pending_op, write_sequence,
                 slot_a_offset, slot_a_capacity,
                 slot_b_offset, slot_b_capacity,
                 last_update_time, schema_version,
                 vm_category=0, vm_uuid='', vm_name=''):
    """Serialise a Header Block (4096 bytes).

    Layout:
        [0:64)    Control Area fields
        [64:96)   ControlChecksum (SHA-256 of [0:64))
        [96:896)  VM Summary data (VmCategory + VmUuid + VmNameLen + VmName)
        [896:928) SummaryChecksum (SHA-256 of [96:896))
        [928:4096) Reserved (zero-padded)

    Returns:
        bytes(4096) ready for ``aligned_pwrite(fd, header, 0)``.
    """
    # -- Control Area [0:64) --
    fields = struct.pack(
        HEADER_FIELDS_FORMAT,
        HEADER_MAGIC, CURRENT_HEADER_VERSION,
        active_slot, pending_op,
        write_sequence,
        slot_a_offset, slot_a_capacity,
        slot_b_offset, slot_b_capacity,
        last_update_time, schema_version,
    )
    # -- ControlChecksum [64:96) --
    control_checksum = hashlib.sha256(fields).digest()

    # -- VM Summary [96:896) --
    vm_summary_data = _build_vm_summary(vm_category, vm_uuid, vm_name)
    # -- SummaryChecksum [896:928) --
    summary_checksum = hashlib.sha256(vm_summary_data).digest()

    # -- Assemble full 4096-byte block --
    block = bytearray(HEADER_BLOCK_SIZE)
    block[0:HEADER_FIELDS_SIZE] = fields
    block[CONTROL_CHECKSUM_OFFSET:CONTROL_CHECKSUM_OFFSET + CONTROL_CHECKSUM_SIZE] = control_checksum
    block[VM_SUMMARY_OFFSET:VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE] = vm_summary_data
    block[VM_SUMMARY_CHECKSUM_OFFSET:VM_SUMMARY_CHECKSUM_OFFSET + CHECKSUM_SIZE] = summary_checksum
    return bytes(block)


def _build_vm_summary(vm_category, vm_uuid, vm_name):
    """Build the 800-byte VM Summary data area [96:896).

    Format: VmCategory(B=1) + VmUuid(32s) + VmNameLen(H=2) + VmName(765s)
    """
    if isinstance(vm_uuid, bytes):
        uuid_bytes = vm_uuid
    else:
        uuid_bytes = vm_uuid.encode('utf-8') if vm_uuid else b''
    if isinstance(vm_name, bytes):
        name_bytes = vm_name
    else:
        name_bytes = vm_name.encode('utf-8') if vm_name else b''
    name_len = min(len(name_bytes), 765)
    name_bytes = name_bytes[:name_len]

    return struct.pack(VM_SUMMARY_DATA_FORMAT,
                       vm_category, uuid_bytes, name_len, name_bytes)


def _parse_vm_summary(block):
    """Parse the VM Summary area from a 4096-byte header block.

    Returns:
        (vm_category, vm_uuid, vm_name, summary_valid)
    """
    if len(block) < VM_SUMMARY_END:
        return 0, '', '', False

    summary_data = block[VM_SUMMARY_OFFSET:VM_SUMMARY_OFFSET + VM_SUMMARY_DATA_SIZE]
    stored_checksum = block[VM_SUMMARY_CHECKSUM_OFFSET:
                            VM_SUMMARY_CHECKSUM_OFFSET + CHECKSUM_SIZE]

    # Verify checksum
    computed = hashlib.sha256(summary_data).digest()
    if computed != stored_checksum:
        return 0, '', '', False

    try:
        vm_category, uuid_raw, name_len, name_raw = struct.unpack(
            VM_SUMMARY_DATA_FORMAT, summary_data)
    except struct.error:
        return 0, '', '', False

    vm_uuid = uuid_raw.rstrip(b'\x00').decode('utf-8', errors='replace')
    actual_name_len = min(name_len, 765)
    vm_name = name_raw[:actual_name_len].rstrip(b'\x00').decode('utf-8', errors='replace')

    return vm_category, vm_uuid, vm_name, True


def parse_header(block):
    """Deserialise a 4096-byte Header Block.

    Returns:
        HeaderData namedtuple.  ``header.valid == True`` iff magic,
        version, and control checksum all pass.
    """
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
     last_update_time, schema_version) = values

    valid = True
    if magic != HEADER_MAGIC:
        valid = False
    elif header_version > MAX_KNOWN_HEADER_VERSION:
        valid = False
    elif hashlib.sha256(fields_bytes).digest() != stored_checksum:
        valid = False

    # Parse VM Summary (independent of control area validity)
    vm_category, vm_uuid, vm_name, summary_valid = _parse_vm_summary(block)

    return HeaderData(
        magic=magic, header_version=header_version,
        active_slot=active_slot, pending_op=pending_op,
        write_sequence=write_sequence,
        slot_a_offset=slot_a_offset, slot_a_capacity=slot_a_capacity,
        slot_b_offset=slot_b_offset, slot_b_capacity=slot_b_capacity,
        last_update_time=last_update_time,
        schema_version=schema_version,
        checksum=stored_checksum, valid=valid,
        vm_category=vm_category, vm_uuid=vm_uuid,
        vm_name=vm_name, summary_valid=summary_valid,
    )


def parse_header_raw_hints(block, lv_size):
    """Extract raw field hints from a *corrupted* Header (Layer 1 recovery).

    Even when the checksum is bad, individual fields may still be readable
    (e.g. single-bit flip).  Returns a ``dict`` of trustworthy hints, or
    ``{}`` if nothing is usable.

    Keys that may be present:
        active_slot, slot_a_offset, slot_a_capacity,
        slot_b_offset, slot_b_capacity
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
     _lut, _sv) = values

    # Only trust hints when Magic is correct (likely partial corruption)
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
    """Return a HeaderData with ``valid=False`` and all fields zeroed."""
    return HeaderData(
        magic=0, header_version=0, active_slot=0, pending_op=0,
        write_sequence=0,
        slot_a_offset=0, slot_a_capacity=0,
        slot_b_offset=0, slot_b_capacity=0,
        last_update_time=0, schema_version=0,
        checksum=b'', valid=False,
        vm_category=0, vm_uuid='', vm_name='', summary_valid=False,
    )


# ===================================================================
# Slot  (36 + N + 32 bytes)
# ===================================================================

def build_slot(seq_num, slot_offset, slot_capacity, payload):
    """Serialise Slot data: SlotHeader(36) + Payload(N) + Checksum(32).

    Args:
        seq_num:       write sequence number (matches Header.WriteSequence)
        slot_offset:   this Slot's byte offset in the LV
        slot_capacity: this Slot's capacity in bytes
        payload:       bytes – metadata JSON payload

    Returns:
        bytes of length ``36 + len(payload) + 32``.
    """
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
    """Deserialise a Slot data blob.

    Args:
        data:              raw bytes starting at the Slot's offset in the LV
        expected_offset:   expected SlotOffset (validation, both modes)
        expected_capacity: expected SlotCapacity (validation, strict only)
        strict:            ``False`` → skip capacity check (recovery mode)

    Returns:
        SlotData namedtuple.  ``slot.valid == True`` iff all checks pass.
    """
    if len(data) < SLOT_HEADER_STRUCT_SIZE:
        return _invalid_slot()

    try:
        values = struct.unpack(SLOT_HEADER_FORMAT,
                               data[:SLOT_HEADER_STRUCT_SIZE])
    except struct.error:
        return _invalid_slot()

    magic, seq_num, slot_offset, slot_capacity, payload_len = values

    # 1. Magic
    if magic != SLOT_MAGIC:
        return _invalid_slot()

    # 2. SlotOffset must match (both strict & relaxed)
    if expected_offset is not None and slot_offset != expected_offset:
        return _invalid_slot()

    # 3. SlotCapacity must match in strict mode
    if strict and expected_capacity is not None \
            and slot_capacity != expected_capacity:
        return _invalid_slot()

    # 4. PayloadLen sanity
    if payload_len == 0:
        return _invalid_slot()
    if slot_capacity > SLOT_OVERHEAD:
        max_payload = slot_capacity - SLOT_OVERHEAD
    else:
        max_payload = len(data) - SLOT_OVERHEAD
    if payload_len > max_payload:
        return _invalid_slot()

    # 5. Enough data available
    total_needed = SLOT_HEADER_STRUCT_SIZE + payload_len + CHECKSUM_SIZE
    if len(data) < total_needed:
        return _invalid_slot()

    # Extract payload & checksum
    payload = data[SLOT_HEADER_STRUCT_SIZE:
                   SLOT_HEADER_STRUCT_SIZE + payload_len]
    cs_start = SLOT_HEADER_STRUCT_SIZE + payload_len
    stored_checksum = data[cs_start:cs_start + CHECKSUM_SIZE]

    # 6. SHA-256 checksum
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
    """Return a SlotData with ``valid=False`` and all fields zeroed."""
    return SlotData(
        magic=0, seq_num=0, slot_offset=0, slot_capacity=0,
        payload_len=0, payload=b'', checksum=b'', valid=False,
    )


# ===================================================================
# Utilities
# ===================================================================

def current_epoch_ms():
    """Current time as epoch milliseconds (uint64-safe)."""
    return int(time.time() * 1000)


def encode_schema_version(major, minor, patch=0):
    """Encode ``'A.B.C'`` → uint64.  E.g. (4, 10, 2) → (4 << 40) | (10 << 20) | 2."""
    return (major << 40) | (minor << 20) | patch


def decode_schema_version(value):
    """Decode uint64 → ``(major, minor, patch)`` tuple."""
    major = (value >> 40) & 0xFFFFF
    minor = (value >> 20) & 0xFFFFF
    patch = value & 0xFFFFF
    return (major, minor, patch)
