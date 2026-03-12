"""lv_metadata: read_metadata + repair_pending_op -- normal read, active corrupted fallback,
config_update interrupted, storage_change incomplete, header recovery, raw hints.

Real LV I/O on iSCSI-backed shared VG. Uses dd to inject corruption.
Follows the shareblock test pattern."""

import json
import os
import uuid as uuid_mod

from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import pytest_utils, storage_device_utils
from zstacklib.utils import bash, lvm
from zstacklib.utils.lv_protocol import (
    ALIGNMENT, HEADER_BLOCK_SIZE, HEADER_CHECKSUM_OFFSET,
    SLOT_A, SLOT_B, SLOT_OVERHEAD,
    PENDING_NONE, PENDING_CONFIG_UPDATE, PENDING_STORAGE_CHANGE,
    INITIAL_LV_SIZE,
    ReadStatus,
    build_header, parse_header, parse_header_raw_hints,
    build_slot, parse_slot,
)
from zstacklib.utils.lv_metadata import (
    read_metadata, repair_pending_op, write_metadata,
    calculate_slot_layout, open_lv, aligned_pread, aligned_pwrite,
)
from unittest import TestCase
from zstacklib.test.utils import env

storage_device_utils.init_storagedevice_plugin()

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {
        'xml': 'http://smb.zstack.io/mirror/ztest/xml/twoDiskVm.xml',
        'init': ['bash ./createiSCSIStroage.sh']
    }
}

hostUuid = "8b12f74e6a834c5fa90304b8ea54b1dd"
hostId = 24
vgUuid = "36b02490bb944233b0b01990a450ba83"

MB = 1024 * 1024


class TestLvMetadataReadRecovery(TestCase, SharedBlockPluginTestStub):

    @classmethod
    def setUpClass(cls):
        pass

    def _connect_vg(self):
        """iSCSI login + shareblock connect -- call once at test entry."""
        iscsi_server = env.get_vm_metadata('self')
        rsp = storage_device_utils.iscsi_login(iscsi_server.ip, "3260")
        self.assertEqual(rsp.success, True, "iscsiadm login failed")
        r, o = bash.bash_ro("ls /dev/disk/by-id | grep scsi|awk -F '-' '{print $2}'")
        blockUuid = o.strip().replace(' ', '').replace('\n', '').replace('\r', '')
        rsp = self.connect([blockUuid], [blockUuid], vgUuid, hostUuid, hostId, forceWipe=True)
        self.assertEqual(True, rsp.success, rsp.error)

    def _create_lv(self, tag):
        tid = uuid_mod.uuid4().hex[:8]
        name = '%s_%s' % (tag, tid)
        lv_path = '/dev/%s/%s' % (vgUuid, name)
        lvm.create_lv_from_absolute_path(lv_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
        return lv_path

    def _cleanup_lv(self, lv_path):
        if lvm.lv_exists(lv_path):
            lvm.delete_lv(lv_path, raise_exception=False)

    def _write(self, lv_path, payload='{"init":true}', **kwargs):
        write_metadata(lv_path, payload,
                       lambda: lvm.get_lv_size(lv_path),
                       lambda s: lvm.extend_lv(lv_path, s),
                       **kwargs)

    def _read(self, lv_path):
        lv_size = lvm.get_lv_size(lv_path)
        return read_metadata(lv_path, lv_size)

    # -- sub-tests ---------------------------------------------------------

    def _test_read_ok(self):
        lv_path = self._create_lv('tr_ok')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"test":1}')
                result = self._read(lv_path)
            self.assertEqual(result.status, ReadStatus.OK)
            self.assertEqual(json.loads(result.payload), {"test": 1})
        finally:
            self._cleanup_lv(lv_path)

    def _test_active_slot_corrupted_fallback(self):
        lv_path = self._create_lv('tr_deg')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')
                self._write(lv_path, '{"v":2}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)
                bash.bash_errorout(
                    'dd if=/dev/zero of=%s bs=4096 count=1 seek=%d conv=notrunc oflag=direct'
                    % (lv_path, layout.slot_b_offset // 4096))

                result = read_metadata(lv_path, lv_size)
            self.assertEqual(result.status, ReadStatus.DEGRADED)
            self.assertEqual(json.loads(result.payload), {"v": 1})
        finally:
            self._cleanup_lv(lv_path)

    def _test_both_slots_corrupted(self):
        lv_path = self._create_lv('tr_corr')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"test":1}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)

                bash.bash_errorout(
                    'dd if=/dev/zero of=%s bs=4096 count=1 seek=%d conv=notrunc oflag=direct'
                    % (lv_path, layout.slot_a_offset // 4096))
                bash.bash_errorout(
                    'dd if=/dev/zero of=%s bs=4096 count=1 seek=%d conv=notrunc oflag=direct'
                    % (lv_path, layout.slot_b_offset // 4096))

                result = read_metadata(lv_path, lv_size)
            self.assertEqual(result.status, ReadStatus.CORRUPTED)
        finally:
            self._cleanup_lv(lv_path)

    def _test_config_update_interrupted(self):
        lv_path = self._create_lv('tr_cfgu')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)
                result_init = self._read(lv_path)
                header = result_init.header

                new_seq = header.write_sequence + 1
                fd = open_lv(lv_path, readonly=False)
                try:
                    phase1 = build_header(
                        active_slot=header.active_slot,
                        pending_op=PENDING_CONFIG_UPDATE,
                        write_sequence=new_seq,
                        slot_a_offset=layout.slot_a_offset,
                        slot_a_capacity=layout.slot_a_capacity,
                        slot_b_offset=layout.slot_b_offset,
                        slot_b_capacity=layout.slot_b_capacity,
                        last_update_time=header.last_update_time,
                        schema_version='')
                    aligned_pwrite(fd, phase1, 0)

                    slot_data = build_slot(
                        seq_num=new_seq,
                        slot_offset=layout.slot_b_offset,
                        slot_capacity=layout.slot_b_capacity,
                        payload=b'{"v":2}')
                    aligned_pwrite(fd, slot_data, layout.slot_b_offset)
                finally:
                    os.close(fd)

                result = read_metadata(lv_path, lv_size)

            self.assertEqual(result.status, ReadStatus.NEED_REPAIR)
            self.assertEqual(json.loads(result.payload), {"v": 2})
            self.assertEqual(result.repair_action, 'complete_phase3')
        finally:
            self._cleanup_lv(lv_path)

    def _test_storage_change_incomplete(self):
        lv_path = self._create_lv('tr_stg')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)
                result_init = self._read(lv_path)
                header = result_init.header

                fd = open_lv(lv_path, readonly=False)
                try:
                    phase1 = build_header(
                        active_slot=header.active_slot,
                        pending_op=PENDING_STORAGE_CHANGE,
                        write_sequence=header.write_sequence + 1,
                        slot_a_offset=layout.slot_a_offset,
                        slot_a_capacity=layout.slot_a_capacity,
                        slot_b_offset=layout.slot_b_offset,
                        slot_b_capacity=layout.slot_b_capacity,
                        last_update_time=header.last_update_time,
                        schema_version='')
                    aligned_pwrite(fd, phase1, 0)
                finally:
                    os.close(fd)

                result = read_metadata(lv_path, lv_size)

            self.assertEqual(result.status, ReadStatus.STORAGE_CHANGE_INCOMPLETE)
        finally:
            self._cleanup_lv(lv_path)

    def _test_repair_completes_config_update(self):
        lv_path = self._create_lv('tr_rep')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)
                result_init = self._read(lv_path)
                header = result_init.header
                new_seq = header.write_sequence + 1

                fd = open_lv(lv_path, readonly=False)
                try:
                    phase1 = build_header(
                        active_slot=header.active_slot,
                        pending_op=PENDING_CONFIG_UPDATE,
                        write_sequence=new_seq,
                        slot_a_offset=layout.slot_a_offset,
                        slot_a_capacity=layout.slot_a_capacity,
                        slot_b_offset=layout.slot_b_offset,
                        slot_b_capacity=layout.slot_b_capacity,
                        last_update_time=0, schema_version='')
                    aligned_pwrite(fd, phase1, 0)

                    slot_data = build_slot(new_seq, layout.slot_b_offset,
                                           layout.slot_b_capacity, b'{"v":2}')
                    aligned_pwrite(fd, slot_data, layout.slot_b_offset)
                finally:
                    os.close(fd)

                repaired, msg = repair_pending_op(lv_path, lv_size)
                self.assertTrue(repaired)
                self.assertIn('Completed Phase 3', msg)

                result = self._read(lv_path)
            self.assertEqual(result.status, ReadStatus.OK)
            self.assertEqual(json.loads(result.payload), {"v": 2})
        finally:
            self._cleanup_lv(lv_path)

    def _test_repair_no_pending(self):
        lv_path = self._create_lv('tr_rnp')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')
                lv_size = lvm.get_lv_size(lv_path)
                repaired, msg = repair_pending_op(lv_path, lv_size)
            self.assertTrue(repaired)
            self.assertIn('No pending', msg)
        finally:
            self._cleanup_lv(lv_path)

    def _test_corrupted_header_recovery(self):
        lv_path = self._create_lv('tr_hdr')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"recovered":true}')

                bash.bash_errorout(
                    'dd if=/dev/zero of=%s bs=%d count=1 conv=notrunc oflag=direct'
                    % (lv_path, HEADER_BLOCK_SIZE))

                lv_size = lvm.get_lv_size(lv_path)
                result = read_metadata(lv_path, lv_size)

            self.assertIn(result.status, [ReadStatus.RECOVERED, ReadStatus.CORRUPTED])
            if result.status == ReadStatus.RECOVERED:
                self.assertEqual(json.loads(result.payload), {"recovered": True})
        finally:
            self._cleanup_lv(lv_path)

    def _test_all_data_zeroed(self):
        lv_path = self._create_lv('tr_zero')
        try:
            with lvm.OperateLv(lv_path, shared=True):
                lv_size = lvm.get_lv_size(lv_path)
                result = read_metadata(lv_path, lv_size)
            self.assertEqual(result.status, ReadStatus.CORRUPTED)
        finally:
            self._cleanup_lv(lv_path)

    def _test_raw_hints_from_corrupted_lv_header(self):
        lv_path = self._create_lv('tr_hints')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"hints":1}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)

                fd = open_lv(lv_path, readonly=True)
                try:
                    header_block = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
                finally:
                    os.close(fd)

                corrupted = bytearray(header_block)
                corrupted[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + 32] = b'\xFF' * 32
                corrupted = bytes(corrupted)

                parsed = parse_header(corrupted, lv_size)
                self.assertFalse(parsed.valid)

                hints = parse_header_raw_hints(corrupted, lv_size)
                self.assertEqual(hints.get('slot_a_offset'), layout.slot_a_offset)
                self.assertEqual(hints.get('slot_b_offset'), layout.slot_b_offset)
        finally:
            self._cleanup_lv(lv_path)

    def _test_raw_hints_from_fully_zeroed_header(self):
        lv_path = self._create_lv('tr_hintz')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"data":1}')

                lv_size = lvm.get_lv_size(lv_path)

                bash.bash_errorout(
                    'dd if=/dev/zero of=%s bs=%d count=1 conv=notrunc oflag=direct'
                    % (lv_path, HEADER_BLOCK_SIZE))

                fd = open_lv(lv_path, readonly=True)
                try:
                    header_block = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
                finally:
                    os.close(fd)

                hints = parse_header_raw_hints(header_block, lv_size)
                self.assertEqual(hints, {})
        finally:
            self._cleanup_lv(lv_path)

    # -- single entry point ------------------------------------------------

    @pytest_utils.ztest_decorater
    def test_lv_metadata_read_recovery(self):
        self._connect_vg()

        self._test_read_ok()
        self._test_active_slot_corrupted_fallback()
        self._test_both_slots_corrupted()
        self._test_config_update_interrupted()
        self._test_storage_change_incomplete()
        self._test_repair_completes_config_update()
        self._test_repair_no_pending()
        self._test_corrupted_header_recovery()
        self._test_all_data_zeroed()
        self._test_raw_hints_from_corrupted_lv_header()
        self._test_raw_hints_from_fully_zeroed_header()
