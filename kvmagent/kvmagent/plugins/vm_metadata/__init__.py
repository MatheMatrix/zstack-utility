"""vm_metadata – AB Dual Slot binary protocol for sblk VM metadata.

Package layout::

    vm_metadata/
        __init__.py      ← you are here (public API re-exports)
        constants.py     ← magic numbers, struct formats, exceptions, data classes
        aligned_io.py    ← AlignedBuffer, O_DIRECT helpers
        codec.py         ← Header / Slot binary encode & decode
        rw.py            ← three-phase write, read + recovery, repair
        lv_manager.py    ← LV calculation, init, delete, scan, health check

Usage::

    from kvmagent.plugins.vm_metadata import (
        write_metadata,
        read_metadata,
        repair_pending_op,
        initialize_metadata_lv,
        get_metadata_status,
        ReadStatus,
    )

See ``vm-metadata-04a-sblk-overview.md`` (and 04b–04e sub-documents) for the full
protocol specification.
"""
from __future__ import absolute_import

# -- constants & data classes -------------------------------------------
from .constants import (                                           # noqa
    # Magic / version
    HEADER_MAGIC, SLOT_MAGIC,
    CURRENT_HEADER_VERSION,
    # PendingOp
    PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE,
    # Slot index
    SLOT_A, SLOT_B,
    # Size limits
    ALIGNMENT, INITIAL_LV_SIZE, MAX_LV_SIZE,
    SLOT_OVERHEAD,
    # LV naming
    LV_METADATA_SUFFIX, LV_METADATA_TAG,
    # Data classes
    SlotLayout, HeaderData, SlotData,
    ReadStatus, ReadResult,
    # Exceptions
    MetadataError, MetadataIOError,
    MetadataVersionError, MetadataCapacityError,
    MetadataCorruptedError,
)

# -- core read / write / repair -----------------------------------------
from .rw import (                                                  # noqa
    write_metadata,
    read_metadata,
    repair_pending_op,
)

# -- LV lifecycle -------------------------------------------------------
from .lv_manager import (                                          # noqa
    calculate_slot_layout,
    calculate_extend_size,
    initialize_metadata_lv,
    delete_metadata_lv,
    scan_metadata_lvs,
    get_metadata_status,
    metadata_lv_path,
)

# -- codec utilities (less frequently needed by callers) ----------------
from .codec import (                                               # noqa
    encode_schema_version,
    decode_schema_version,
)
