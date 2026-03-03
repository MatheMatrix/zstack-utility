"""LV lifecycle management: layout calculation, init, extend, delete, scan, health.

Implements §8 (LV management) of vm-metadata-04-sblk.md.

Also provides ``storage_topology_changed()`` as a public helper (used by
rw.py internally but may also be useful to callers).
"""
from __future__ import absolute_import

import os
import logging

from .constants import (
    ALIGNMENT,
    INITIAL_LV_SIZE, MAX_LV_SIZE,
    SLOT_A,
    SLOT_OVERHEAD,
    HEADER_BLOCK_SIZE,
    IO_CHECK_PATTERN, IO_CHECK_PATTERN_LEN,
    LV_METADATA_SUFFIX, LV_METADATA_TAG,
    SlotLayout,
    MetadataIOError, MetadataCapacityError,
)
from .aligned_io import (
    AlignedBuffer, aligned_pwrite, aligned_pread, open_lv, align_up,
)
from .codec import (
    build_header, build_slot, parse_header, current_epoch_ms,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Layout Calculation  (§8.3)
# ===================================================================

def calculate_slot_layout(lv_size):
    """Compute SlotA/SlotB offset & capacity for a given LV size.

    Formula (all values 4 KB-aligned)::

        header_reserved = ALIGNMENT (4096)
        available       = lv_size - header_reserved
        slot_capacity   = floor(available / 2 / ALIGNMENT) * ALIGNMENT
        slot_a_offset   = header_reserved
        slot_b_offset   = header_reserved + slot_capacity

    Example (4 MB LV)::

        available  = 4194304 - 4096 = 4190208
        slot_cap   = (4190208 // 2 // 4096) * 4096 = 2093056  (~2044 KB)
        slot_a_off = 4096
        slot_b_off = 4096 + 2093056 = 2097152

    Returns:
        SlotLayout namedtuple.
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


# ===================================================================
# Stepped Extend Size  (§8.4)
# ===================================================================

def calculate_extend_size(current_lv_size, min_required):
    """Calculate the target LV size using stepped expansion.

    Step sizes::

        current < 8 MB   → step = 2 MB
        8 MB ~ 16 MB     → step = 4 MB
        16 MB ~ 32 MB    → step = 8 MB
        > 32 MB          → step = 16 MB

    Example::

        current=4MB, min_required=6MB+4KB
          step 1: 4+2 = 6 MB   (still < required)
          step 2: 6+2 = 8 MB   (>= required → done)

    Args:
        current_lv_size: current LV size in bytes
        min_required:    minimum LV size to satisfy the payload

    Returns:
        int – new LV target size in bytes (never exceeds MAX_LV_SIZE).

    Raises:
        MetadataCapacityError – if min_required > MAX_LV_SIZE
    """
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


# ===================================================================
# LV Initialisation  (§8.5.1)
# ===================================================================

def initialize_metadata_lv(lv_path, lv_size):
    """Initialise a brand-new metadata LV.

    Steps:
        0. O_DIRECT sanity check (write/read-back at offset 0)
        1. Build empty-payload Slot A (``payload = b'{}'``)
        2. Write Slot A
        3. Write Header (ActiveSlot=0, WriteSeq=1, PendingOp=0)

    After success the LV is in a clean state where the first
    ``read_metadata()`` returns ``OK`` with ``payload=b'{}'``.

    Raises:
        MetadataIOError – if the sanity check fails
    """
    fd = open_lv(lv_path)
    try:
        # Step 0: O_DIRECT sanity check
        _io_sanity_check(fd, lv_path)

        layout = calculate_slot_layout(lv_size)

        # Step 1 + 2: empty-payload Slot A
        empty_payload = b'{}'
        slot_a = build_slot(
            seq_num=1,
            slot_offset=layout.slot_a_offset,
            slot_capacity=layout.slot_a_capacity,
            payload=empty_payload,
        )
        aligned_pwrite(fd, slot_a, layout.slot_a_offset)

        # Step 3: Header
        header = build_header(
            active_slot=SLOT_A,
            pending_op=0,
            write_sequence=1,
            slot_a_offset=layout.slot_a_offset,
            slot_a_capacity=layout.slot_a_capacity,
            slot_b_offset=layout.slot_b_offset,
            slot_b_capacity=layout.slot_b_capacity,
            last_update_time=0,
            schema_version=0,
        )
        aligned_pwrite(fd, header, 0)

        logger.info("Initialized metadata LV %s (size=%d, slot_cap=%d)",
                     lv_path, lv_size, layout.slot_a_capacity)
    finally:
        os.close(fd)


def _io_sanity_check(fd, lv_path):
    """Verify the O_DIRECT I/O path works (write + read-back at offset 0).

    The test data written here will be overwritten by the formal Header
    in the next step of ``initialize_metadata_lv()``.  If that Header
    write fails, offset 0 contains non-Magic data and ``read_metadata()``
    will correctly enter recovery → CORRUPTED (expected: init incomplete).
    """
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


# ===================================================================
# LV Delete  (§8.5.2)
# ===================================================================

def delete_metadata_lv(lv_path, lv_delete_func):
    """Delete a metadata LV – simply delegates to *lv_delete_func*.

    Args:
        lv_path:        path to the metadata LV
        lv_delete_func: ``(path) -> None`` – e.g. ``lvm.delete_lv``
    """
    lv_delete_func(lv_path)
    logger.info("Deleted metadata LV %s", lv_path)


# ===================================================================
# LV Scan  (§8.5.3)
# ===================================================================

def scan_metadata_lvs(vg_uuid, lv_list_func):
    """Scan a VG for metadata LVs (names ending with ``_vmmeta``).

    Args:
        vg_uuid:       VG UUID (also used as VG name in sblk)
        lv_list_func:  ``(vg_uuid) -> list[(lv_name, lv_path, lv_size)]``

    Returns:
        list of dicts::

            [{'vm_uuid': '...', 'lv_path': '...', 'lv_size': int}, ...]
    """
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


# ===================================================================
# Health Check  (§8.6)
# ===================================================================

def get_metadata_status(lv_path, lv_size):
    """Read-only health check: parse the Header and return a status dict.

    Returns:
        dict with keys: valid, header_version, active_slot, pending_op,
        write_sequence, slot_a_offset, slot_a_capacity, slot_b_offset,
        slot_b_capacity, last_update_time, schema_version.
    """
    fd = open_lv(lv_path, readonly=True)
    try:
        header_bytes = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
        header = parse_header(header_bytes)
        return {
            'valid':            header.valid,
            'header_version':   header.header_version,
            'active_slot':      header.active_slot,
            'pending_op':       header.pending_op,
            'write_sequence':   header.write_sequence,
            'slot_a_offset':    header.slot_a_offset,
            'slot_a_capacity':  header.slot_a_capacity,
            'slot_b_offset':    header.slot_b_offset,
            'slot_b_capacity':  header.slot_b_capacity,
            'last_update_time': header.last_update_time,
            'schema_version':   header.schema_version,
        }
    finally:
        os.close(fd)


# ===================================================================
# LV Path Helper
# ===================================================================

def metadata_lv_path(vg_uuid, vm_uuid):
    """Compute the canonical LV device path for a VM's metadata.

    Returns:
        ``'/dev/{vg_uuid}/{vm_uuid}_vmmeta'``
    """
    return '/dev/%s/%s%s' % (vg_uuid, vm_uuid, LV_METADATA_SUFFIX)
