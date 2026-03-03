"""Three-phase atomic write, read with recovery, and repair operations.

Implements §5 (write), §6 (read + recovery), §7 (repair) of
vm-metadata-04-sblk.md.

Dependency graph (no cycles):
    rw  -->  codec, aligned_io, lv_manager, constants
"""
from __future__ import absolute_import

import os
import json
import struct
import logging

from .constants import (
    ALIGNMENT, HEADER_BLOCK_SIZE,
    PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE,
    SLOT_A, SLOT_B,
    SLOT_HEADER_STRUCT_SIZE, SLOT_HEADER_FORMAT,
    CHECKSUM_SIZE, SLOT_OVERHEAD,
    OPTIMISTIC_READ_SIZE, BRUTE_FORCE_CHUNK_SIZE,
    SLOT_MAGIC_BYTES,
    MAX_LV_SIZE,
    SlotLayout, ReadStatus, ReadResult,
    MetadataIOError, MetadataCapacityError,
)
from .aligned_io import (
    AlignedBuffer, aligned_pwrite, aligned_pread, open_lv, align_up,
)
from .codec import (
    build_header, parse_header, parse_header_raw_hints,
    build_slot, parse_slot, current_epoch_ms,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Public API – write
# ===================================================================

def write_metadata(lv_path, payload, lv_size_getter, lv_extend_func,
                   schema_version=0):
    """Three-phase atomic write of metadata to an sblk LV.

    Args:
        lv_path:         ``/dev/{vg}/{vm}_vmmeta``
        payload:         bytes | str – metadata JSON payload
        lv_size_getter:  ``() -> int`` returns current LV size in bytes
        lv_extend_func:  ``(new_size_bytes) -> None`` extends the LV
        schema_version:  uint32 schema version stamped into Header

    Raises:
        MetadataCapacityError – payload exceeds 64 MB limit
        MetadataIOError       – O_DIRECT I/O failure
    """
    payload_bytes = _ensure_bytes(payload)
    lv_size = lv_size_getter()

    # ---- Step 0: read current state (read-only fd) --------------------
    fd = open_lv(lv_path, readonly=True)
    try:
        header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
        header = parse_header(header_bytes)
        if header.valid:
            op_type = _determine_op_type(fd, header, payload_bytes)
        else:
            header = None
            op_type = PENDING_STORAGE_CHANGE       # conservative
    finally:
        os.close(fd)

    # ---- Fresh write (no valid header) --------------------------------
    if header is None:
        _write_fresh(lv_path, payload_bytes, lv_size,
                     lv_size_getter, lv_extend_func, schema_version)
        return

    # ---- Prepare three-phase write ------------------------------------
    target_slot = 1 - header.active_slot
    new_seq = header.write_sequence + 1

    current_layout = SlotLayout(
        slot_a_offset=header.slot_a_offset,
        slot_a_capacity=header.slot_a_capacity,
        slot_b_offset=header.slot_b_offset,
        slot_b_capacity=header.slot_b_capacity,
    )

    # Capacity check
    required = SLOT_OVERHEAD + len(payload_bytes)
    target_cap = (current_layout.slot_a_capacity if target_slot == SLOT_A
                  else current_layout.slot_b_capacity)

    if required > target_cap:
        new_layout, lv_size = _extend_for_payload(
            lv_path, lv_size, len(payload_bytes),
            lv_size_getter, lv_extend_func)
    else:
        new_layout = current_layout

    # Target slot offset/capacity from the (possibly new) layout
    if target_slot == SLOT_A:
        tgt_offset = new_layout.slot_a_offset
        tgt_capacity = new_layout.slot_a_capacity
    else:
        tgt_offset = new_layout.slot_b_offset
        tgt_capacity = new_layout.slot_b_capacity

    # ---- Phase 1 → 2 → 3 with a fresh R/W fd -------------------------
    fd = open_lv(lv_path)
    try:
        # Phase 1 — Mark Intent  (512 B atomic write)
        #   ActiveSlot = old,  PendingOp = op_type,  Layout = OLD
        phase1 = build_header(
            active_slot=header.active_slot,
            pending_op=op_type,
            write_sequence=new_seq,
            slot_a_offset=current_layout.slot_a_offset,
            slot_a_capacity=current_layout.slot_a_capacity,
            slot_b_offset=current_layout.slot_b_offset,
            slot_b_capacity=current_layout.slot_b_capacity,
            last_update_time=header.last_update_time,
            schema_version=header.schema_version,
        )
        aligned_pwrite(fd, phase1, 0)

        # Phase 2 — Write Payload to inactive slot
        slot_data = build_slot(
            seq_num=new_seq,
            slot_offset=tgt_offset,
            slot_capacity=tgt_capacity,
            payload=payload_bytes,
        )
        aligned_pwrite(fd, slot_data, tgt_offset)

        # Phase 3 — Commit  (512 B atomic write)
        #   ActiveSlot = target,  PendingOp = 0,  Layout = NEW
        phase3 = build_header(
            active_slot=target_slot,
            pending_op=PENDING_NONE,
            write_sequence=new_seq,
            slot_a_offset=new_layout.slot_a_offset,
            slot_a_capacity=new_layout.slot_a_capacity,
            slot_b_offset=new_layout.slot_b_offset,
            slot_b_capacity=new_layout.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=schema_version,
        )
        aligned_pwrite(fd, phase3, 0)
    finally:
        os.close(fd)


# ===================================================================
# Public API – read
# ===================================================================

def read_metadata(lv_path, lv_size):
    """Read metadata from an sblk LV with full recovery support.

    Args:
        lv_path: ``/dev/{vg}/{vm}_vmmeta``
        lv_size: current LV size in bytes

    Returns:
        ReadResult – see ReadStatus for possible states.
    """
    fd = open_lv(lv_path, readonly=True)
    try:
        return _read_metadata_fd(fd, lv_size)
    finally:
        os.close(fd)


# ===================================================================
# Public API – repair
# ===================================================================

def repair_pending_op(lv_path, lv_size):
    """Attempt to repair a pending (interrupted) write operation.

    Returns:
        ``(repaired: bool, message: str)``
    """
    fd = open_lv(lv_path)
    try:
        header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
        header = parse_header(header_bytes)
        if not header.valid:
            return False, "Header corrupted, cannot repair"

        if header.pending_op == PENDING_NONE:
            return True, "No pending operation"

        target = _read_slot_at(fd, header, 1 - header.active_slot)

        if header.pending_op == PENDING_CONFIG_UPDATE:
            return _repair_config_update(fd, header, target)
        elif header.pending_op == PENDING_STORAGE_CHANGE:
            return _repair_storage_change(fd, header, target)
        else:
            return False, "Unknown PendingOp: %d" % header.pending_op
    finally:
        os.close(fd)


# ===================================================================
# Internal – read dispatcher & flows
# ===================================================================

def _read_metadata_fd(fd, lv_size):
    header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
    header = parse_header(header_bytes)

    if header.valid:
        if header.pending_op == PENDING_NONE:
            return _read_flow_a(fd, header, lv_size)
        elif header.pending_op == PENDING_CONFIG_UPDATE:
            return _read_flow_b(fd, header, lv_size)
        elif header.pending_op == PENDING_STORAGE_CHANGE:
            return _read_flow_c(fd, header, lv_size)
        else:
            return ReadResult(
                status=ReadStatus.CORRUPTED,
                error="Unknown PendingOp value: %d" % header.pending_op)
    else:
        return _recover_from_corrupted_header(fd, header_bytes, lv_size)


# ---- Flow A  (PendingOp == 0, normal) --------------------------------

def _read_flow_a(fd, header, lv_size):
    active = _read_active_slot(fd, header)
    if active.valid:
        return ReadResult(status=ReadStatus.OK,
                          payload=active.payload, header=header)

    # Active corrupted – try inactive for diagnostics
    inactive = _read_inactive_slot(fd, header)
    if inactive.valid:
        return ReadResult(
            status=ReadStatus.CORRUPTED, header=header,
            error=("Active slot corrupted; inactive valid "
                   "(SeqNum=%d) but may be stale" % inactive.seq_num),
            repair_action="switch_active_or_full_refresh")

    return ReadResult(status=ReadStatus.CORRUPTED, header=header,
                      error="Both slots corrupted",
                      repair_action="full_refresh")


# ---- Flow B  (PendingOp == 1, CONFIG_UPDATE interrupted) --------------

def _read_flow_b(fd, header, lv_size):
    target = _read_slot_at(fd, header, 1 - header.active_slot)

    if target.valid and target.seq_num == header.write_sequence:
        # Phase 2 done, Phase 3 not → use newer data
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=target.payload, header=header,
            repair_action="complete_phase3")

    # Fallback to active (old but safe)
    active = _read_active_slot(fd, header)
    if active.valid:
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=active.payload, header=header,
            repair_action="clear_pending_op")

    return ReadResult(status=ReadStatus.CORRUPTED, header=header,
                      error="CONFIG_UPDATE pending, both slots unreadable",
                      repair_action="full_refresh")


# ---- Flow C  (PendingOp == 2, STORAGE_CHANGE interrupted) ------------

def _read_flow_c(fd, header, lv_size):
    target = _read_slot_at(fd, header, 1 - header.active_slot)

    if target.valid and target.seq_num == header.write_sequence:
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=target.payload, header=header,
            repair_action="complete_phase3")

    # Target invalid → stale data, DANGEROUS
    active = _read_active_slot(fd, header)
    return ReadResult(
        status=ReadStatus.STORAGE_CHANGE_INCOMPLETE,
        payload=active.payload if active.valid else None,
        header=header,
        error=("Storage topology changed but metadata not updated. "
               "Active slot has stale data. Must execute full-refresh."),
        repair_action="full_refresh_required")


# ===================================================================
# Internal – repair helpers
# ===================================================================

def _repair_config_update(fd, header, target):
    """Repair PendingOp=1 (CONFIG_UPDATE)."""
    if target.valid and target.seq_num == header.write_sequence:
        # Complete Phase 3
        h = build_header(
            active_slot=1 - header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=header.slot_a_offset,
            slot_a_capacity=header.slot_a_capacity,
            slot_b_offset=header.slot_b_offset,
            slot_b_capacity=header.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=header.schema_version)
        aligned_pwrite(fd, h, 0)
        return True, "Completed Phase 3 for config update"
    else:
        # Abort incomplete write → clear PendingOp
        h = build_header(
            active_slot=header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=header.slot_a_offset,
            slot_a_capacity=header.slot_a_capacity,
            slot_b_offset=header.slot_b_offset,
            slot_b_capacity=header.slot_b_capacity,
            last_update_time=header.last_update_time,
            schema_version=header.schema_version)
        aligned_pwrite(fd, h, 0)
        return True, "Aborted incomplete config update"


def _repair_storage_change(fd, header, target):
    """Repair PendingOp=2 (STORAGE_CHANGE)."""
    if target.valid and target.seq_num == header.write_sequence:
        # Complete Phase 3 – safe, new data reflects the change
        h = build_header(
            active_slot=1 - header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=header.slot_a_offset,
            slot_a_capacity=header.slot_a_capacity,
            slot_b_offset=header.slot_b_offset,
            slot_b_capacity=header.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=header.schema_version)
        aligned_pwrite(fd, h, 0)
        return True, "Completed Phase 3 for storage change"
    else:
        # MUST NOT clear PendingOp – data is stale and dangerous!
        return False, (
            "STORAGE_CHANGE pending, target data lost. "
            "Metadata is stale. Must execute full-refresh from database.")


# ===================================================================
# Internal – slot I/O helpers
# ===================================================================

def _read_active_slot(fd, header):
    return _read_slot_at(fd, header, header.active_slot)


def _read_inactive_slot(fd, header):
    return _read_slot_at(fd, header, 1 - header.active_slot)


def _read_slot_at(fd, header, slot_index):
    """Read & parse a single slot using layout info from header."""
    if slot_index == SLOT_A:
        offset = header.slot_a_offset
        capacity = header.slot_a_capacity
    else:
        offset = header.slot_b_offset
        capacity = header.slot_b_capacity
    return _read_and_parse_slot(fd, offset, capacity, strict=True)


def _read_and_parse_slot(fd, offset, capacity, strict=True):
    """Read slot data with optimistic 1-MB-first strategy (§6.4.1)."""
    read_size = min(capacity, OPTIMISTIC_READ_SIZE) if capacity > 0 \
        else OPTIMISTIC_READ_SIZE
    data = aligned_pread(fd, read_size, offset)

    slot = parse_slot(data, expected_offset=offset,
                      expected_capacity=capacity if strict else None,
                      strict=strict)

    if not slot.valid and read_size < capacity:
        # Payload might be larger than our first read – check the header
        if len(data) >= SLOT_HEADER_STRUCT_SIZE:
            try:
                _, _, _, _, payload_len = struct.unpack(
                    SLOT_HEADER_FORMAT, data[:SLOT_HEADER_STRUCT_SIZE])
                total_needed = (SLOT_HEADER_STRUCT_SIZE
                                + payload_len + CHECKSUM_SIZE)
                if read_size < total_needed <= capacity:
                    data = aligned_pread(fd, total_needed, offset)
                    slot = parse_slot(
                        data, expected_offset=offset,
                        expected_capacity=capacity if strict else None,
                        strict=strict)
            except struct.error:
                pass

    return slot


# ===================================================================
# Internal – op_type determination  (§5.2 前置步骤 + §7.4)
# ===================================================================

def _determine_op_type(fd, header, new_payload):
    """Determine PENDING_CONFIG_UPDATE or PENDING_STORAGE_CHANGE."""
    try:
        active_slot = _read_active_slot(fd, header)
        if active_slot.valid and active_slot.payload:
            if _storage_topology_changed(active_slot.payload, new_payload):
                return PENDING_STORAGE_CHANGE
            else:
                return PENDING_CONFIG_UPDATE
    except Exception:
        pass
    return PENDING_STORAGE_CHANGE    # conservative


def _storage_topology_changed(old_payload, new_payload):
    """Compare storage topology between old and new metadata payloads.

    Compares volume UUIDs / installPaths and snapshot UUIDs /
    primaryStorageInstallPaths.  Any difference → True.
    """
    try:
        old_str = (old_payload.decode('utf-8')
                   if isinstance(old_payload, bytes) else old_payload)
        new_str = (new_payload.decode('utf-8')
                   if isinstance(new_payload, bytes) else new_payload)
        old = json.loads(old_str)
        new = json.loads(new_str)
    except (ValueError, TypeError):
        return True   # cannot parse → conservative

    def _extract_topology(d):
        vols = {}
        for rm in d.get('volumes', []):
            vo_str = rm.get('vo', '{}')
            try:
                vo = json.loads(vo_str) if isinstance(vo_str, str) else vo_str
                vols[vo.get('uuid', '')] = vo.get('installPath', '')
            except (ValueError, TypeError):
                pass
        snaps = {}
        for vol_uuid, snap_list in d.get('snapshots', {}).items():
            if isinstance(snap_list, list):
                for s_json in snap_list:
                    try:
                        s = (json.loads(s_json) if isinstance(s_json, str)
                             else s_json)
                        snaps[s.get('uuid', '')] = s.get(
                            'primaryStorageInstallPath', '')
                    except (ValueError, TypeError):
                        pass
        return vols, snaps

    old_vols, old_snaps = _extract_topology(old)
    new_vols, new_snaps = _extract_topology(new)
    return old_vols != new_vols or old_snaps != new_snaps


# ===================================================================
# Internal – Header recovery  (§6.3)
# ===================================================================

def _recover_from_corrupted_header(fd, header_bytes, lv_size):
    """4-layer recovery: raw hints → layout calc → SlotA chain → brute-force."""
    from .lv_manager import calculate_slot_layout

    hints = parse_header_raw_hints(header_bytes, lv_size)

    # Layer 1: Raw hints from corrupted header
    if hints:
        result = _try_recovery_with_hints(fd, hints, lv_size)
        if result:
            return result

    # Layer 2: Calculated layout
    layout = calculate_slot_layout(lv_size)
    result = _try_recovery_with_layout(fd, layout, lv_size,
                                       active_hint=hints.get('active_slot'))
    if result:
        return result

    # Layer 3: Slot A self-description → infer Slot B position
    slot_a = _read_and_parse_slot(
        fd, layout.slot_a_offset, layout.slot_a_capacity, strict=False)
    if slot_a.valid and slot_a.slot_offset > 0 and slot_a.slot_capacity > 0:
        inferred_b_offset = slot_a.slot_offset + slot_a.slot_capacity
        if inferred_b_offset < lv_size:
            inferred_b_cap = lv_size - inferred_b_offset
            slot_b = _read_and_parse_slot(
                fd, inferred_b_offset, inferred_b_cap, strict=False)
            result = _pick_best_slot(slot_a, slot_b,
                                     hints.get('active_slot'))
            if result:
                return result

    # Layer 4: Brute-force scan
    return _brute_force_recovery(fd, lv_size, hints.get('active_slot'))


def _try_recovery_with_hints(fd, hints, lv_size):
    slots = []
    if 'slot_a_offset' in hints:
        cap_a = hints.get('slot_a_capacity',
                          lv_size - hints['slot_a_offset'])
        sa = _read_and_parse_slot(fd, hints['slot_a_offset'], cap_a,
                                  strict=False)
        if sa.valid:
            slots.append(sa)

    if 'slot_b_offset' in hints:
        cap_b = hints.get('slot_b_capacity',
                          lv_size - hints['slot_b_offset'])
        sb = _read_and_parse_slot(fd, hints['slot_b_offset'], cap_b,
                                  strict=False)
        if sb.valid:
            slots.append(sb)

    if not slots:
        return None
    best = _select_best_slot(slots, hints.get('active_slot'))
    return ReadResult(status=ReadStatus.RECOVERED, payload=best.payload,
                      repair_action="rebuild_header")


def _try_recovery_with_layout(fd, layout, lv_size, active_hint=None):
    slot_a = _read_and_parse_slot(
        fd, layout.slot_a_offset, layout.slot_a_capacity, strict=False)
    slot_b = _read_and_parse_slot(
        fd, layout.slot_b_offset, layout.slot_b_capacity, strict=False)
    return _pick_best_slot(slot_a, slot_b, active_hint)


def _pick_best_slot(slot_a, slot_b, active_hint=None):
    valid = [s for s in (slot_a, slot_b) if s.valid]
    if not valid:
        return None
    best = _select_best_slot(valid, active_hint)
    return ReadResult(status=ReadStatus.RECOVERED, payload=best.payload,
                      repair_action="rebuild_header")


def _select_best_slot(slots, active_hint=None):
    """Pick the 'best' slot: prefer highest SeqNum (most recent write)."""
    if len(slots) == 1:
        return slots[0]
    return max(slots, key=lambda s: s.seq_num)


def _brute_force_recovery(fd, lv_size, active_hint=None):
    """Layer 4: scan entire LV for ZSDT magic at ALIGNMENT boundaries."""
    found = []
    offset = ALIGNMENT                        # skip header area
    while offset < lv_size:
        chunk = min(BRUTE_FORCE_CHUNK_SIZE, lv_size - offset)
        if chunk < ALIGNMENT:
            break
        try:
            data = aligned_pread(fd, chunk, offset)
        except Exception:
            offset += chunk
            continue

        pos = 0
        while pos + SLOT_HEADER_STRUCT_SIZE <= len(data):
            if data[pos:pos + 4] == SLOT_MAGIC_BYTES:
                actual_offset = offset + pos
                slot = parse_slot(data[pos:],
                                  expected_offset=actual_offset,
                                  expected_capacity=None,
                                  strict=False)
                if slot.valid:
                    found.append(slot)
            pos += ALIGNMENT
        offset += chunk

    if not found:
        return ReadResult(status=ReadStatus.CORRUPTED,
                          error="Brute-force scan found no valid slots",
                          repair_action="full_refresh")

    best = _select_best_slot(found, active_hint)
    return ReadResult(status=ReadStatus.RECOVERED, payload=best.payload,
                      repair_action="rebuild_header")


# ===================================================================
# Internal – fresh write  (no valid header)
# ===================================================================

def _write_fresh(lv_path, payload_bytes, lv_size,
                 lv_size_getter, lv_extend_func, schema_version):
    """Write metadata to an LV that has no valid header."""
    from .lv_manager import calculate_slot_layout

    layout = calculate_slot_layout(lv_size)
    required = SLOT_OVERHEAD + len(payload_bytes)

    if required > layout.slot_a_capacity:
        layout, lv_size = _extend_for_payload(
            lv_path, lv_size, len(payload_bytes),
            lv_size_getter, lv_extend_func)

    fd = open_lv(lv_path)
    try:
        # Write Slot A first
        slot_data = build_slot(
            seq_num=1,
            slot_offset=layout.slot_a_offset,
            slot_capacity=layout.slot_a_capacity,
            payload=payload_bytes)
        aligned_pwrite(fd, slot_data, layout.slot_a_offset)

        # Then write Header
        h = build_header(
            active_slot=SLOT_A,
            pending_op=PENDING_NONE,
            write_sequence=1,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=schema_version)
        aligned_pwrite(fd, h, 0)
    finally:
        os.close(fd)


# ===================================================================
# Internal – LV extend helper
# ===================================================================

def _extend_for_payload(lv_path, current_lv_size, payload_len,
                        lv_size_getter, lv_extend_func):
    """Extend LV so that a slot can hold *payload_len* bytes.

    Returns:
        ``(new_layout: SlotLayout, new_lv_size: int)``
    """
    from .lv_manager import calculate_slot_layout, calculate_extend_size

    required = SLOT_OVERHEAD + payload_len
    min_lv = ALIGNMENT + 2 * align_up(required, ALIGNMENT)
    if min_lv > MAX_LV_SIZE:
        raise MetadataCapacityError(
            "Required LV size %d exceeds maximum %d "
            "(payload = %d bytes)" % (min_lv, MAX_LV_SIZE, payload_len))

    new_lv_target = calculate_extend_size(current_lv_size, min_lv)
    lv_extend_func(new_lv_target)
    actual_size = lv_size_getter()
    return calculate_slot_layout(actual_size), actual_size


# ===================================================================
# Utility
# ===================================================================

def _ensure_bytes(data):
    """Coerce *data* to bytes (Python 2 str / Python 3 bytes)."""
    if isinstance(data, bytes):
        return data
    return data.encode('utf-8')
