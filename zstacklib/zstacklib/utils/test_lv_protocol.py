"""Pure-Python unit tests for lv_protocol codec functions.

No hardware, LVM, or O_DIRECT needed -- exercises only the in-memory
build/parse helpers and constants defined in lv_protocol.py.
"""

import struct
import hashlib
from unittest import TestCase

from zstacklib.utils.lv_protocol import (
    # constants
    HEADER_MAGIC, SLOT_MAGIC,
    ALIGNMENT, INITIAL_LV_SIZE, MAX_LV_SIZE,
    SLOT_HEADER_SIZE, CHECKSUM_SIZE, SLOT_OVERHEAD,
    HEADER_BLOCK_SIZE, HEADER_JSON_OFFSET, HEADER_CHECKSUM_OFFSET,
    HEADER_JSON_MAX_LEN,
    SLOT_A, SLOT_B,
    PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE,
    # codec
    align_up,
    build_header, parse_header, parse_header_raw_hints,
    build_slot, parse_slot,
    # data classes
    ReadStatus, ReadResult,
)


# ---- helpers ----------------------------------------------------------------

def _make_header(**overrides):
    """Build a valid header with sensible defaults; overrides replace fields."""
    defaults = dict(
        active_slot=SLOT_A,
        pending_op=PENDING_NONE,
        write_sequence=1,
        slot_a_offset=4096,
        slot_a_capacity=2 * 1024 * 1024 - 4096,
        slot_b_offset=2 * 1024 * 1024,
        slot_b_capacity=2 * 1024 * 1024 - 4096,
        last_update_time=1700000000000,
        schema_version='1',
    )
    defaults.update(overrides)
    return build_header(**defaults)


# #############################################################################
# TestLvProtocolConstants
# #############################################################################

class TestLvProtocolConstants(TestCase):

    def test_magic_values(self):
        self.assertEqual(HEADER_MAGIC, 0x5A534D54)
        self.assertEqual(SLOT_MAGIC, 0x5A534454)

    def test_alignment_and_sizes(self):
        self.assertEqual(ALIGNMENT, 4096)
        self.assertEqual(INITIAL_LV_SIZE, 4 * 1024 * 1024)
        self.assertEqual(MAX_LV_SIZE, 64 * 1024 * 1024)

    def test_slot_overhead(self):
        self.assertEqual(SLOT_OVERHEAD, SLOT_HEADER_SIZE + CHECKSUM_SIZE)
        self.assertEqual(SLOT_OVERHEAD, 68)

    def test_header_layout_offsets(self):
        self.assertEqual(HEADER_BLOCK_SIZE, 4096)
        self.assertEqual(HEADER_JSON_OFFSET, 8)
        self.assertEqual(HEADER_CHECKSUM_OFFSET, 4064)
        self.assertEqual(HEADER_JSON_MAX_LEN, 4064 - 8)


# #############################################################################
# TestAlignUp
# #############################################################################

class TestAlignUp(TestCase):

    def test_already_aligned(self):
        self.assertEqual(align_up(4096), 4096)

    def test_round_up(self):
        self.assertEqual(align_up(1), 4096)
        self.assertEqual(align_up(4097), 8192)

    def test_zero(self):
        self.assertEqual(align_up(0), 0)

    def test_custom_alignment(self):
        self.assertEqual(align_up(5, 4), 8)
        self.assertEqual(align_up(8, 4), 8)
        self.assertEqual(align_up(9, 4), 12)


# #############################################################################
# TestBuildParseHeader
# #############################################################################

class TestBuildParseHeader(TestCase):

    def test_roundtrip(self):
        block = _make_header(
            active_slot=SLOT_B,
            pending_op=PENDING_CONFIG_UPDATE,
            write_sequence=42,
            slot_a_offset=4096,
            slot_a_capacity=100000,
            slot_b_offset=200000,
            slot_b_capacity=100000,
            last_update_time=1700000000000,
            schema_version='2',
        )
        self.assertEqual(len(block), HEADER_BLOCK_SIZE)

        hd = parse_header(block)
        self.assertTrue(hd.valid)
        self.assertEqual(hd.magic, HEADER_MAGIC)
        self.assertEqual(hd.active_slot, SLOT_B)
        self.assertEqual(hd.pending_op, PENDING_CONFIG_UPDATE)
        self.assertEqual(hd.write_sequence, 42)
        self.assertEqual(hd.slot_a_offset, 4096)
        self.assertEqual(hd.slot_a_capacity, 100000)
        self.assertEqual(hd.slot_b_offset, 200000)
        self.assertEqual(hd.slot_b_capacity, 100000)
        self.assertEqual(hd.last_update_time, 1700000000000)
        self.assertEqual(hd.schema_version, '2')

    def test_with_vm_metadata(self):
        block = _make_header(
            vm_category='AppCenter',
            vm_uuid='abcd1234',
            vm_name='my-test-vm',
            architecture='x86_64',
        )
        hd = parse_header(block)
        self.assertTrue(hd.valid)
        self.assertEqual(hd.vm_category, 'AppCenter')
        self.assertEqual(hd.vm_uuid, 'abcd1234')
        self.assertEqual(hd.vm_name, 'my-test-vm')
        self.assertEqual(hd.architecture, 'x86_64')

    def test_invalid_magic_returns_invalid(self):
        block = bytearray(_make_header())
        struct.pack_into('>I', block, 0, 0xDEADBEEF)
        # recompute checksum so only magic is wrong
        hd = parse_header(bytes(block))
        self.assertFalse(hd.valid)

    def test_corrupted_checksum_returns_invalid(self):
        block = bytearray(_make_header())
        # flip one byte in the checksum area
        block[HEADER_CHECKSUM_OFFSET] ^= 0xFF
        hd = parse_header(bytes(block))
        self.assertFalse(hd.valid)

    def test_json_too_large_raises(self):
        with self.assertRaises(ValueError):
            build_header(
                active_slot=0, pending_op=0, write_sequence=1,
                slot_a_offset=4096, slot_a_capacity=4096,
                slot_b_offset=8192, slot_b_capacity=4096,
                last_update_time=0, schema_version='1',
                vm_name='X' * 5000,  # will push JSON well over 4056 bytes
            )

    def test_truncated_block_returns_invalid(self):
        block = _make_header()[:2048]
        hd = parse_header(block)
        self.assertFalse(hd.valid)


# #############################################################################
# TestBuildParseSlot
# #############################################################################

class TestBuildParseSlot(TestCase):

    def _make_slot(self, payload=b'hello world', seq=1,
                   offset=4096, capacity=4096):
        return build_slot(seq, offset, capacity, payload)

    def test_roundtrip(self):
        payload = b'{"key":"value"}'
        data = self._make_slot(payload=payload, seq=7,
                               offset=8192, capacity=4096)
        sd = parse_slot(data, expected_offset=8192, expected_capacity=4096)
        self.assertTrue(sd.valid)
        self.assertEqual(sd.magic, SLOT_MAGIC)
        self.assertEqual(sd.seq_num, 7)
        self.assertEqual(sd.slot_offset, 8192)
        self.assertEqual(sd.slot_capacity, 4096)
        self.assertEqual(sd.payload, payload)
        self.assertEqual(sd.payload_len, len(payload))

    def test_payload_empty_raises(self):
        with self.assertRaises(ValueError):
            build_slot(1, 4096, 4096, b'')

    def test_payload_too_large_raises(self):
        capacity = 128
        big_payload = b'X' * (capacity + 1)  # exceeds capacity even without overhead
        with self.assertRaises(ValueError):
            build_slot(1, 4096, capacity, big_payload)

    def test_corrupted_checksum_returns_invalid(self):
        data = bytearray(self._make_slot())
        # flip the last byte (inside checksum)
        data[-1] ^= 0xFF
        sd = parse_slot(bytes(data), expected_offset=4096, expected_capacity=4096)
        self.assertFalse(sd.valid)

    def test_wrong_offset_returns_invalid(self):
        data = self._make_slot(offset=4096)
        sd = parse_slot(data, expected_offset=9999)
        self.assertFalse(sd.valid)

    def test_wrong_capacity_returns_invalid(self):
        data = self._make_slot(capacity=4096)
        sd = parse_slot(data, expected_offset=4096, expected_capacity=9999,
                        strict=True)
        self.assertFalse(sd.valid)

    def test_strict_false_allows_capacity_mismatch(self):
        data = self._make_slot(capacity=4096)
        sd = parse_slot(data, expected_offset=4096, expected_capacity=9999,
                        strict=False)
        self.assertTrue(sd.valid)
        self.assertEqual(sd.slot_capacity, 4096)


# #############################################################################
# TestParseHeaderRawHints
# #############################################################################

class TestParseHeaderRawHints(TestCase):

    def test_valid_header_extracts_hints(self):
        block = bytearray(_make_header(
            active_slot=SLOT_A,
            slot_a_offset=4096,
            slot_a_capacity=100000,
            slot_b_offset=200000,
            slot_b_capacity=100000,
        ))
        # corrupt checksum so parse_header would fail, but raw_hints works
        block[HEADER_CHECKSUM_OFFSET] ^= 0xFF
        hints = parse_header_raw_hints(bytes(block), lv_size=4 * 1024 * 1024)
        self.assertEqual(hints.get('active_slot'), SLOT_A)
        self.assertEqual(hints.get('slot_a_offset'), 4096)
        self.assertEqual(hints.get('slot_a_capacity'), 100000)
        self.assertEqual(hints.get('slot_b_offset'), 200000)
        self.assertEqual(hints.get('slot_b_capacity'), 100000)

    def test_invalid_magic_returns_empty(self):
        block = bytearray(HEADER_BLOCK_SIZE)
        struct.pack_into('>I', block, 0, 0xDEADBEEF)
        hints = parse_header_raw_hints(bytes(block), lv_size=4 * 1024 * 1024)
        self.assertEqual(hints, {})

    def test_slot_offset_exceeds_lv_returns_empty(self):
        small_lv = 8192  # only 8 KB
        block = _make_header(
            slot_a_offset=4096,
            slot_a_capacity=100000,  # offset+capacity exceeds small_lv
            slot_b_offset=200000,    # exceeds small_lv
            slot_b_capacity=100000,
        )
        hints = parse_header_raw_hints(block, lv_size=small_lv)
        # slot_a_offset valid but offset+capacity > lv_size => removed
        self.assertNotIn('slot_a_offset', hints)
        # slot_b_offset > lv_size, should not appear
        self.assertNotIn('slot_b_offset', hints)

    def test_minimal_block_too_short_returns_empty(self):
        block = b'\x00' * 5  # less than HEADER_JSON_OFFSET + 2
        hints = parse_header_raw_hints(block, lv_size=4 * 1024 * 1024)
        self.assertEqual(hints, {})


# #############################################################################
# TestReadResult
# #############################################################################

class TestReadResult(TestCase):

    def test_is_usable_for_ok_states(self):
        for status in (ReadStatus.OK, ReadStatus.NEED_REPAIR,
                       ReadStatus.RECOVERED, ReadStatus.DEGRADED):
            rr = ReadResult(status=status, payload=b'data')
            self.assertTrue(rr.is_usable(),
                            "%s should be usable" % status)

    def test_not_usable_for_corrupted(self):
        for status in (ReadStatus.CORRUPTED,
                       ReadStatus.STORAGE_CHANGE_INCOMPLETE):
            rr = ReadResult(status=status)
            self.assertFalse(rr.is_usable(),
                             "%s should not be usable" % status)

    def test_repr(self):
        rr = ReadResult(status=ReadStatus.OK, payload=b'abc',
                        error='none')
        s = repr(rr)
        self.assertIn('OK', s)
        self.assertIn('3', s)  # payload_len
        self.assertIn('none', s)


if __name__ == '__main__':
    import unittest
    unittest.main()
