import json
import logging
import os
import re
import struct
import time

from .lv_protocol import (
    ALIGNMENT, HEADER_BLOCK_SIZE,
    PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE,
    SLOT_A, SLOT_HEADER_STRUCT_SIZE, SLOT_HEADER_FORMAT,
    CHECKSUM_SIZE, SLOT_OVERHEAD,
    OPTIMISTIC_READ_SIZE, BRUTE_FORCE_CHUNK_SIZE,
    BRUTE_FORCE_TIMEOUT_SEC, KNOWN_LV_SIZES,
    SLOT_MAGIC_BYTES,
    MAX_LV_SIZE, INITIAL_LV_SIZE,
    IO_CHECK_PATTERN, IO_CHECK_PATTERN_LEN,
    LV_METADATA_SUFFIX, LV_METADATA_TAG,
    SlotLayout, ReadStatus, ReadResult,
    MetadataCapacityError, MetadataIOError,
    AlignedBuffer, aligned_pwrite, aligned_pread, open_lv, align_up,
    build_header, parse_header, parse_header_raw_hints,
    build_slot, parse_slot, current_epoch_ms,
)
from .vm_metadata_handler import VmMetadataHandler, VmMetadataScanEntry

logger = logging.getLogger(__name__)


# ###################################################################
# LV Manager
# ###################################################################

def calculate_slot_layout(lv_size):
    """Compute SlotA/SlotB offset & capacity for a given LV size.
    All values 4 KB-aligned. slot_capacity = floor((lv_size - 4096) / 2 / 4096) * 4096.
    """
    header_reserved = ALIGNMENT
    available = lv_size - header_reserved
    slot_capacity = (available // 2 // ALIGNMENT) * ALIGNMENT

    return SlotLayout(
        slot_a_offset=header_reserved,
        slot_a_capacity=slot_capacity,
        slot_b_offset=header_reserved + slot_capacity,
        slot_b_capacity=slot_capacity,
    )


def calculate_extend_size(current_lv_size, min_required):
    """Stepped expansion: <8MB +2MB, <16MB +4MB, <32MB +8MB, else +16MB."""
    if min_required > MAX_LV_SIZE:
        raise MetadataCapacityError(
            "Required LV size %d exceeds maximum %d"
            % (min_required, MAX_LV_SIZE))

    MB = 1024 * 1024
    size = current_lv_size

    while size < min_required:
        if size < 8 * MB:
            step = 2 * MB
        elif size < 16 * MB:
            step = 4 * MB
        elif size < 32 * MB:
            step = 8 * MB
        else:
            step = 16 * MB

        size += step
        if size > MAX_LV_SIZE:
            size = MAX_LV_SIZE
            break

    return size


def initialize_metadata_lv(lv_path, lv_size):
    """Initialise a brand-new metadata LV: sanity check, empty Slot A, Header."""
    fd = open_lv(lv_path)
    try:
        _io_sanity_check(fd, lv_path)

        layout = calculate_slot_layout(lv_size)

        slot_a = build_slot(
            seq_num=1,
            slot_offset=layout.slot_a_offset,
            slot_capacity=layout.slot_a_capacity,
            payload=b'{}',
        )
        aligned_pwrite(fd, slot_a, layout.slot_a_offset)

        # Zero-fill Slot B to avoid residual data interfering with recovery
        slot_b_zero = b'\x00' * min(layout.slot_b_capacity, ALIGNMENT)
        aligned_pwrite(fd, slot_b_zero, layout.slot_b_offset)

        header = build_header(
            active_slot=SLOT_A,
            pending_op=0,
            write_sequence=1,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=0,
            schema_version='',
        )
        aligned_pwrite(fd, header, 0)

        logger.info("Initialized metadata LV %s (size=%d, slot_cap=%d)",
                    lv_path, lv_size, layout.slot_a_capacity)
    finally:
        os.close(fd)


def _io_sanity_check(fd, lv_path):
    """Write + read-back at offset 0 to verify O_DIRECT I/O path works."""
    test_data = IO_CHECK_PATTERN + b'\x00' * (512 - IO_CHECK_PATTERN_LEN)

    with AlignedBuffer(512) as buf:
        buf.fill(test_data)
        buf.pwrite(fd, 0)

    with AlignedBuffer(512) as buf:
        buf.pread(fd, 0)
        read_back = buf.read(IO_CHECK_PATTERN_LEN)
        if read_back != IO_CHECK_PATTERN:
            raise MetadataIOError(
                "O_DIRECT sanity check failed on %s "
                "(wrote %r, read %r)"
                % (lv_path, IO_CHECK_PATTERN, read_back))


def delete_metadata_lv(lv_path, lv_delete_func):
    lv_delete_func(lv_path)
    logger.info("Deleted metadata LV %s", lv_path)


def scan_metadata_lvs(vg_uuid, lv_list_func):
    """Scan VG for metadata LVs (names ending with '_vmmeta')."""
    result = []
    for lv_name, lv_path, lv_size in lv_list_func(vg_uuid):
        if lv_name.endswith(LV_METADATA_SUFFIX):
            vm_uuid = lv_name[:-len(LV_METADATA_SUFFIX)]
            result.append({
                'vm_uuid': vm_uuid,
                'lv_path': lv_path,
                'lv_size': lv_size,
            })
    return result


def get_metadata_status(lv_path, lv_size):
    """Read-only health check: parse Header and return status dict."""
    fd = open_lv(lv_path, readonly=True)
    try:
        header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
        header = parse_header(header_bytes)
        return {
            'valid': header.valid,
            'header_version': header.header_version,
            'active_slot': header.active_slot,
            'pending_op': header.pending_op,
            'write_sequence': header.write_sequence,
            'slot_a_offset': header.slot_a_offset,
            'slot_a_capacity': header.slot_a_capacity,
            'slot_b_offset': header.slot_b_offset,
            'slot_b_capacity': header.slot_b_capacity,
            'last_update_time': header.last_update_time,
            'schema_version': header.schema_version,
            'vm_category': header.vm_category,
            'vm_uuid': header.vm_uuid,
            'vm_name': header.vm_name,
            'architecture': header.architecture,
        }
    finally:
        os.close(fd)


def metadata_lv_path(vg_uuid, vm_uuid):
    return '/dev/%s/%s%s' % (vg_uuid, vm_uuid, LV_METADATA_SUFFIX)


# ###################################################################
# Read / Write / Recovery
# ###################################################################

def write_metadata(lv_path, payload, lv_size_getter, lv_extend_func,
                   schema_version='',
                   vm_category='', vm_uuid='', vm_name='',
                   architecture=''):
    """Three-phase atomic write of metadata to an sblk LV."""
    payload_bytes = _ensure_bytes(payload)
    lv_size = lv_size_getter()

    # Step 0: read current state
    fd = open_lv(lv_path, readonly=True)
    try:
        header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
        header = parse_header(header_bytes)
        if header.valid:
            op_type = _determine_op_type(fd, header, payload_bytes)
        else:
            header = None
            op_type = PENDING_STORAGE_CHANGE
    finally:
        os.close(fd)

    # Fresh write (no valid header)
    if header is None:
        _write_fresh(lv_path, payload_bytes, lv_size,
                     lv_size_getter, lv_extend_func, schema_version,
                     vm_category=vm_category, vm_uuid=vm_uuid,
                     vm_name=vm_name, architecture=architecture)
        return

    # Prepare three-phase write
    target_slot = 1 - header.active_slot
    new_seq = header.write_sequence + 1

    current_layout = SlotLayout(
        slot_a_offset=header.slot_a_offset,
        slot_a_capacity=header.slot_a_capacity,
        slot_b_offset=header.slot_b_offset,
        slot_b_capacity=header.slot_b_capacity,
    )

    required = SLOT_OVERHEAD + len(payload_bytes)
    target_cap = (current_layout.slot_a_capacity if target_slot == SLOT_A
                  else current_layout.slot_b_capacity)

    if required > target_cap:
        new_layout, lv_size = _extend_for_payload(
            lv_path, lv_size, len(payload_bytes),
            lv_size_getter, lv_extend_func)
    else:
        new_layout = current_layout

    if target_slot == SLOT_A:
        tgt_offset = new_layout.slot_a_offset
        tgt_capacity = new_layout.slot_a_capacity
    else:
        tgt_offset = new_layout.slot_b_offset
        tgt_capacity = new_layout.slot_b_capacity

    # Phase 1 -> 2 -> 3
    fd = open_lv(lv_path)
    try:
        # Phase 1: Mark Intent
        phase1 = build_header(
            active_slot=header.active_slot,
            pending_op=op_type,
            write_sequence=new_seq,
            slot_a_offset=current_layout.slot_a_offset,
            slot_a_capacity=current_layout.slot_a_capacity,
            slot_b_offset=current_layout.slot_b_offset,
            slot_b_capacity=current_layout.slot_b_capacity,
            last_update_time=header.last_update_time,
            schema_version=schema_version,
            vm_category=vm_category, vm_uuid=vm_uuid, vm_name=vm_name,
            architecture=architecture,
        )
        aligned_pwrite(fd, phase1, 0)

        # Phase 2: Write payload to inactive slot
        slot_data = build_slot(
            seq_num=new_seq,
            slot_offset=tgt_offset,
            slot_capacity=tgt_capacity,
            payload=payload_bytes,
        )
        aligned_pwrite(fd, slot_data, tgt_offset)

        # Phase 3: Commit
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
            vm_category=vm_category, vm_uuid=vm_uuid, vm_name=vm_name,
            architecture=architecture,
        )
        aligned_pwrite(fd, phase3, 0)
    finally:
        os.close(fd)


def read_metadata(lv_path, lv_size):
    """Read metadata with full recovery support. Returns ReadResult."""
    fd = open_lv(lv_path, readonly=True)
    try:
        return _read_metadata_fd(fd, lv_size)
    finally:
        os.close(fd)


def repair_pending_op(lv_path, lv_size):
    """Repair a pending (interrupted) write. Returns (repaired, message)."""
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
            return _repair_config_update(fd, header, target, lv_size)
        elif header.pending_op == PENDING_STORAGE_CHANGE:
            return _repair_storage_change(fd, header, target, lv_size)
        else:
            logger.warning("repair: unknown PendingOp %d, treating as "
                           "STORAGE_CHANGE", header.pending_op)
            return _repair_storage_change(fd, header, target, lv_size)
    finally:
        os.close(fd)


# ---- Read dispatcher ----

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
            logger.warning("Unknown PendingOp %d, treating as STORAGE_CHANGE",
                           header.pending_op)
            return _read_flow_c(fd, header, lv_size)
    else:
        return _recover_from_corrupted_header(fd, header_bytes, lv_size)


# ---- Flow A: PendingOp == 0, normal read ----

def _read_flow_a(fd, header, lv_size):
    active = _read_active_slot(fd, header)
    if active.valid:
        return ReadResult(status=ReadStatus.OK,
                          payload=active.payload, header=header)

    inactive = _read_inactive_slot(fd, header)
    if inactive.valid:
        return ReadResult(
            status=ReadStatus.DEGRADED, header=header,
            payload=inactive.payload,
            error=("Active slot corrupted; returning inactive payload "
                   "(SeqNum=%d) which may be stale" % inactive.seq_num),
            repair_action="switch_active_or_full_refresh")

    return ReadResult(status=ReadStatus.CORRUPTED, header=header,
                      error="Both slots corrupted",
                      repair_action="full_refresh")


# ---- Flow B: PendingOp == 1, CONFIG_UPDATE interrupted ----

def _read_flow_b(fd, header, lv_size):
    target = _read_slot_at(fd, header, 1 - header.active_slot)

    if target.valid and target.seq_num == header.write_sequence:
        # Phase 2 done, Phase 3 not
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=target.payload, header=header,
            repair_action="complete_phase3")

    active = _read_active_slot(fd, header)
    if active.valid:
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=active.payload, header=header,
            repair_action="clear_pending_op")

    return ReadResult(status=ReadStatus.CORRUPTED, header=header,
                      error="CONFIG_UPDATE pending, both slots unreadable",
                      repair_action="full_refresh")


# ---- Flow C: PendingOp == 2, STORAGE_CHANGE interrupted ----

def _read_flow_c(fd, header, lv_size):
    target = _read_slot_at(fd, header, 1 - header.active_slot)

    if target.valid and target.seq_num == header.write_sequence:
        return ReadResult(
            status=ReadStatus.NEED_REPAIR,
            payload=target.payload, header=header,
            repair_action="complete_phase3")

    # Target invalid -> stale data, DANGEROUS
    active = _read_active_slot(fd, header)
    return ReadResult(
        status=ReadStatus.STORAGE_CHANGE_INCOMPLETE,
        payload=active.payload if active.valid else None,
        header=header,
        error=("Storage topology changed but metadata not updated. "
               "Active slot has stale data. Must execute full-refresh."),
        repair_action="full_refresh_required")


# ---- Repair helpers ----

def _repair_config_update(fd, header, target, lv_size):
    """Tries old-layout then new-layout for target slot (dual-layout fallback).

    When completing Phase 3, always use the layout derived from the current
    ``lv_size`` (via ``calculate_slot_layout``).  If the LV was extended between
    Phase 1 and Phase 3, the Phase-1 header still records the *old* slot
    offsets/capacities.  Writing those stale values back would leave the header
    inconsistent with the actual LV geometry.  ``calculate_slot_layout(lv_size)``
    returns the correct layout regardless of whether an expansion occurred.
    """
    if not target.valid:
        target = _try_read_target_new_layout(fd, header, lv_size)

    # Current layout based on actual LV size (correct after possible expansion)
    layout = calculate_slot_layout(lv_size)

    if target.valid and target.seq_num == header.write_sequence:
        # Complete Phase 3
        h = build_header(
            active_slot=1 - header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=header.schema_version,
            vm_category=header.vm_category,
            vm_uuid=header.vm_uuid,
            vm_name=header.vm_name,
            architecture=header.architecture)
        aligned_pwrite(fd, h, 0)
        return True, "Completed Phase 3 for config update"
    else:
        # Abort incomplete write -> clear PendingOp.
        # Use header's original layout here because no expansion completed
        # successfully (the target slot was never written at new offsets).
        h = build_header(
            active_slot=header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=header.slot_a_offset,
            slot_a_capacity=header.slot_a_capacity,
            slot_b_offset=header.slot_b_offset,
            slot_b_capacity=header.slot_b_capacity,
            last_update_time=header.last_update_time,
            schema_version=header.schema_version,
            vm_category=header.vm_category,
            vm_uuid=header.vm_uuid,
            vm_name=header.vm_name,
            architecture=header.architecture)
        aligned_pwrite(fd, h, 0)
        return True, "Aborted incomplete config update"


def _repair_storage_change(fd, header, target, lv_size):
    """Tries old-layout then new-layout for target slot (dual-layout fallback).

    See ``_repair_config_update`` for the rationale on using
    ``calculate_slot_layout(lv_size)`` when completing Phase 3.
    """
    if not target.valid:
        target = _try_read_target_new_layout(fd, header, lv_size)

    # Current layout based on actual LV size (correct after possible expansion)
    layout = calculate_slot_layout(lv_size)

    if target.valid and target.seq_num == header.write_sequence:
        h = build_header(
            active_slot=1 - header.active_slot,
            pending_op=PENDING_NONE,
            write_sequence=header.write_sequence,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=header.schema_version,
            vm_category=header.vm_category,
            vm_uuid=header.vm_uuid,
            vm_name=header.vm_name,
            architecture=header.architecture)
        aligned_pwrite(fd, h, 0)
        return True, "Completed Phase 3 for storage change"
    else:
        # MUST NOT clear PendingOp -- data is stale and dangerous
        return False, (
            "STORAGE_CHANGE pending, target data lost. "
            "Metadata is stale. Must execute full-refresh from database.")


def _try_read_target_new_layout(fd, header, lv_size):
    new_layout = calculate_slot_layout(lv_size)
    target_index = 1 - header.active_slot
    if target_index == SLOT_A:
        offset = new_layout.slot_a_offset
        capacity = new_layout.slot_a_capacity
    else:
        offset = new_layout.slot_b_offset
        capacity = new_layout.slot_b_capacity
    return _read_and_parse_slot(fd, offset, capacity, strict=False)


# ---- Slot I/O helpers ----

def _read_active_slot(fd, header):
    return _read_slot_at(fd, header, header.active_slot)


def _read_inactive_slot(fd, header):
    return _read_slot_at(fd, header, 1 - header.active_slot)


def _read_slot_at(fd, header, slot_index):
    if slot_index == SLOT_A:
        offset = header.slot_a_offset
        capacity = header.slot_a_capacity
    else:
        offset = header.slot_b_offset
        capacity = header.slot_b_capacity
    return _read_and_parse_slot(fd, offset, capacity, strict=True)


def _read_and_parse_slot(fd, offset, capacity, strict=True):
    """Optimistic 1-MB-first read; re-reads if payload is larger."""
    read_size = min(capacity, OPTIMISTIC_READ_SIZE) if capacity > 0 \
        else OPTIMISTIC_READ_SIZE
    data = aligned_pread(fd, read_size, offset)

    slot = parse_slot(data, expected_offset=offset,
                      expected_capacity=capacity if strict else None,
                      strict=strict)

    if not slot.valid and read_size < capacity:
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


# ---- Op type determination ----

def _determine_op_type(fd, header, new_payload):
    """CONFIG_UPDATE vs STORAGE_CHANGE based on volume/snapshot topology diff."""
    try:
        active_slot = _read_active_slot(fd, header)
        if active_slot.valid and active_slot.payload:
            if _storage_topology_changed(active_slot.payload, new_payload):
                return PENDING_STORAGE_CHANGE
            else:
                return PENDING_CONFIG_UPDATE
    except Exception as e:
        logger.debug("failed to determine op type, defaulting to STORAGE_CHANGE: %s", e)
    return PENDING_STORAGE_CHANGE


def _storage_topology_changed(old_payload, new_payload):
    """Compare volume UUIDs/installPaths and snapshot UUIDs."""
    try:
        old_str = (old_payload.decode('utf-8')
                   if isinstance(old_payload, bytes) else old_payload)
        new_str = (new_payload.decode('utf-8')
                   if isinstance(new_payload, bytes) else new_payload)
        old = json.loads(old_str)
        new = json.loads(new_str)
    except (ValueError, TypeError):
        return True

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
        for _vol_uuid, snap_list in d.get('snapshots', {}).items():
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


# ---- 4-layer header recovery ----

def _recover_from_corrupted_header(fd, header_bytes, lv_size):
    hints = parse_header_raw_hints(header_bytes, lv_size)

    # Layer 1: raw hints from corrupted header
    if hints:
        result = _try_recovery_with_hints(fd, hints, lv_size)
        if result:
            return result

    # Layer 2: enumerate KNOWN_LV_SIZES for multi-layout probing
    for candidate_lv_size in KNOWN_LV_SIZES:
        if candidate_lv_size > lv_size:
            continue
        candidate_layout = calculate_slot_layout(candidate_lv_size)
        result = _try_recovery_with_layout(fd, candidate_layout, lv_size,
                                           active_hint=hints.get('active_slot'))
        if result:
            return result

    # Layer 3: Slot A self-description -> infer Slot B position
    current_layout = calculate_slot_layout(lv_size)
    slot_a = _read_and_parse_slot(
        fd, current_layout.slot_a_offset, current_layout.slot_a_capacity,
        strict=False)
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

    # Layer 4: brute-force scan
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
    """Pick slot with highest SeqNum (most recent write)."""
    if len(slots) == 1:
        return slots[0]
    return max(slots, key=lambda s: s.seq_num)


def _brute_force_recovery(fd, lv_size, active_hint=None):
    """Scan entire LV for ZSDT magic at ALIGNMENT boundaries (with timeout)."""
    logger.info("Starting brute-force scan (lv_size=%d, timeout=%ds)",
                lv_size, BRUTE_FORCE_TIMEOUT_SEC)
    deadline = time.time() + BRUTE_FORCE_TIMEOUT_SEC
    found = []
    offset = ALIGNMENT
    while offset < lv_size:
        if time.time() > deadline:
            logger.warning("Brute-force scan timed out after %ds at "
                           "offset %d / %d",
                           BRUTE_FORCE_TIMEOUT_SEC, offset, lv_size)
            break
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


# ---- Fresh write (no valid header) ----

def _write_fresh(lv_path, payload_bytes, lv_size,
                 lv_size_getter, lv_extend_func, schema_version,
                 vm_category='', vm_uuid='', vm_name='',
                 architecture=''):
    layout = calculate_slot_layout(lv_size)
    required = SLOT_OVERHEAD + len(payload_bytes)

    if required > layout.slot_a_capacity:
        layout, lv_size = _extend_for_payload(
            lv_path, lv_size, len(payload_bytes),
            lv_size_getter, lv_extend_func)

    fd = open_lv(lv_path)
    try:
        slot_data = build_slot(
            seq_num=1,
            slot_offset=layout.slot_a_offset,
            slot_capacity=layout.slot_a_capacity,
            payload=payload_bytes)
        aligned_pwrite(fd, slot_data, layout.slot_a_offset)

        h = build_header(
            active_slot=SLOT_A,
            pending_op=PENDING_NONE,
            write_sequence=1,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=current_epoch_ms(),
            schema_version=schema_version,
            vm_category=vm_category, vm_uuid=vm_uuid, vm_name=vm_name,
            architecture=architecture)
        aligned_pwrite(fd, h, 0)
    finally:
        os.close(fd)


def _extend_for_payload(lv_path, current_lv_size, payload_len,
                        lv_size_getter, lv_extend_func):
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


def _ensure_bytes(data):
    if isinstance(data, bytes):
        return data
    return data.encode('utf-8')


# ###################################################################
# Handler
# ###################################################################

class SblkMetadataHandler(VmMetadataHandler):
    # VG names in SharedBlock are UUIDs or LVM safe names (alnum + hyphen + underscore + period)
    _SAFE_VG_RE = re.compile(r'^[a-zA-Z0-9_.\-]+$')

    def __init__(self, lvm_module, bash_module):
        self._lvm = lvm_module
        self._bash = bash_module

    def _ensure_metadata_lv(self, metadata_path):
        """Create the metadata LV if it doesn't exist (no I/O initialization here)."""
        if self._lvm.lv_exists(metadata_path):
            return

        self._lvm.create_lv_from_absolute_path(
            metadata_path,
            INITIAL_LV_SIZE,
            tag=LV_METADATA_TAG,
            lock=False,
            exact_size=True,
        )
        logger.info("created metadata LV %s", metadata_path)

    def _initialize_if_needed(self, metadata_path, lv_size):
        """Under exclusive lock, check header and initialize if blank/invalid."""
        fd = open_lv(metadata_path, readonly=True)
        try:
            header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
            header = parse_header(header_bytes)
        finally:
            os.close(fd)

        if not header.valid:
            initialize_metadata_lv(metadata_path, lv_size)
            logger.info("initialized metadata LV %s", metadata_path)

    def _lv_list_func(self, vg):
        if not self._SAFE_VG_RE.match(vg):
            raise Exception("invalid VG name: %s" % vg)
        _r, o = self._bash.bash_ro(
            "lvs --nolocking -t %s --noheadings -o lv_name,lv_path,lv_size"
            " --units b --nosuffix --separator '|'" % vg
        )
        result = []
        for line in o.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 3:
                continue
            lv_name = parts[0].strip()
            lv_path = parts[1].strip()
            lv_size = int(parts[2].strip())
            result.append((lv_name, lv_path, lv_size))
        return result

    def _do_write(self, metadataPath, metadata, vmUuid, vmName, vmCategory, architecture, schemaVersion):
        self._ensure_metadata_lv(metadataPath)

        lvm = self._lvm

        def _get_lv_size():
            return int(lvm.get_lv_size(metadataPath))

        def _extend_lv(new_size):
            lvm.extend_lv(metadataPath, new_size)

        with lvm.OperateLv(metadataPath, shared=False):
            self._initialize_if_needed(metadataPath, _get_lv_size())
            write_metadata(
                lv_path=metadataPath,
                payload=metadata,
                lv_size_getter=_get_lv_size,
                lv_extend_func=_extend_lv,
                schema_version=schemaVersion or '',
                vm_uuid=vmUuid,
                vm_name=vmName,
                vm_category=vmCategory or '',
                architecture=architecture,
            )

        logger.debug("successfully wrote vm metadata to %s", metadataPath)
        return {}

    def _do_get(self, metadataPath):
        lvm = self._lvm

        if not lvm.lv_exists(metadataPath):
            return {'metadata': None}

        try:
            lv_size = int(lvm.get_lv_size(metadataPath))
            with lvm.OperateLv(metadataPath, shared=True):
                read_result = read_metadata(metadataPath, lv_size)
            if read_result.is_usable():
                payload = read_result.payload.decode('utf-8') \
                    if isinstance(read_result.payload, bytes) else read_result.payload
                logger.debug("read vm metadata from %s (%d bytes)",
                             metadataPath, len(payload) if payload else 0)
                return {'metadata': payload}
            else:
                logger.warn("metadata LV %s is not usable: status=%s, error=%s",
                            metadataPath, read_result.status, read_result.error)
                return {'metadata': None}
        except Exception as e:
            logger.warn("failed to read metadata from %s: %s", metadataPath, e)
            return {'metadata': None}

    def _do_scan(self, metadataDir):
        # metadataDir is /dev/{vgUuid} for shared block
        vg_uuid = os.path.basename(metadataDir)
        lvm = self._lvm
        bash = self._bash

        @bash.in_bash
        def _lv_list(vg):
            return self._lv_list_func(vg)

        metadata_lvs = scan_metadata_lvs(vg_uuid, _lv_list)

        entries = []
        for item in metadata_lvs:
            vm_uuid = item['vm_uuid']
            lv_path = item['lv_path']
            lv_size = item['lv_size']

            entry = VmMetadataScanEntry(
                vmUuid=vm_uuid,
                metadataPath=lv_path,
                sizeBytes=lv_size,
            )

            try:
                with lvm.OperateLv(lv_path, shared=True):
                    status = get_metadata_status(lv_path, lv_size)
                if status.get('valid'):
                    entry.schemaVersion = status.get('schema_version', '')
                    entry.lastUpdateTime = status.get('last_update_time', 0)
                    entry.vmName = status.get('vm_name', '')
                    entry.architecture = status.get('architecture', '')
                    entry.vmCategory = status.get('vm_category', '')
            except Exception as e:
                logger.warn("failed to read metadata status for %s: %s", lv_path, e)

            entries.append(entry)

        logger.debug("scan_vm_metadata on vg %s: found %d metadata LVs, returned %d entries",
                     vg_uuid, len(metadata_lvs), len(entries))
        return entries

    def _do_cleanup(self, metadataPath):
        lvm = self._lvm

        try:
            if lvm.lv_exists(metadataPath):
                delete_metadata_lv(metadataPath, lvm.delete_lv)
            else:
                logger.debug("metadata LV %s does not exist, skip cleanup", metadataPath)
        except Exception as e:
            raise Exception("failed to cleanup metadata LV %s: %s" % (metadataPath, str(e))) from e

        logger.debug("cleanup_vm_metadata: cleaned %s", metadataPath)
        return {}
