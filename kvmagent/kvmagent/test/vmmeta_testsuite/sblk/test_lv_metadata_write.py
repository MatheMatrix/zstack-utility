import json
import hashlib
import os
import uuid as uuid_mod

from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import pytest_utils, storage_device_utils
from zstacklib.utils import bash, lvm
from zstacklib.utils.lv_protocol import (
    ALIGNMENT, HEADER_BLOCK_SIZE, HEADER_CHECKSUM_OFFSET,
    SLOT_A, SLOT_B, SLOT_OVERHEAD,
    PENDING_NONE,
    INITIAL_LV_SIZE, MAX_LV_SIZE,
    parse_header, parse_slot,
)
from zstacklib.utils.lv_metadata import (
    write_metadata, read_metadata, calculate_slot_layout,
    open_lv, aligned_pread,
)
from unittest import TestCase
from zstacklib.test.utils import env

storage_device_utils.init_storagedevice_plugin()

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {
        'xml': 'http://smb.zstack.io/mirror/ztest/xml/twoDiskVm.xml',
        'init': ['cd ../../shareblock_testsuite && bash ./createiSCSIStroage.sh']
    }
}

hostUuid = "8b12f74e6a834c5fa90304b8ea54b1dd"
hostId = 24
vgUuid = "36b02490bb944233b0b01990a450ba83"

MB = 1024 * 1024


class TestLvMetadataWrite(TestCase, SharedBlockPluginTestStub):

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

    def _write(self, lv_path, payload='{"test":1}', **kwargs):
        write_metadata(
            lv_path=lv_path,
            payload=payload,
            lv_size_getter=lambda: lvm.get_lv_size(lv_path),
            lv_extend_func=lambda s: lvm.extend_lv(lv_path, s),
            **kwargs
        )

    def _read(self, lv_path):
        lv_size = lvm.get_lv_size(lv_path)
        return read_metadata(lv_path, lv_size)

    def _test_fresh_write_creates_header_and_slot(self):
        lv_path = self._create_lv('tw_fresh')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"test":1}',
                            schema_version='1', vm_uuid='abc123', vm_name='test-vm')
                result = self._read(lv_path)

            self.assertEqual(result.status, 'OK')
            self.assertTrue(result.header.valid)
            self.assertEqual(result.header.active_slot, SLOT_A)
            self.assertEqual(result.header.pending_op, PENDING_NONE)
            self.assertEqual(result.header.write_sequence, 1)
            self.assertEqual(result.header.vm_uuid, 'abc123')
            self.assertEqual(result.header.schema_version, '1')
            self.assertEqual(result.payload, b'{"test":1}')
        finally:
            self._cleanup_lv(lv_path)

    def _test_parse_header_from_real_lv(self):
        lv_path = self._create_lv('tw_hdr')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"real_lv":true}',
                            schema_version='2', vm_uuid='hdr_test')

                fd = open_lv(lv_path, readonly=True)
                try:
                    raw = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
                finally:
                    os.close(fd)

            h = parse_header(raw)
            self.assertTrue(h.valid)
            self.assertEqual(h.vm_uuid, 'hdr_test')
            self.assertEqual(h.schema_version, '2')
            self.assertEqual(h.active_slot, SLOT_A)
            checksum = raw[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + 32]
            self.assertEqual(checksum, hashlib.sha256(raw[:HEADER_CHECKSUM_OFFSET]).digest())
        finally:
            self._cleanup_lv(lv_path)

    def _test_parse_slot_from_real_lv(self):
        lv_path = self._create_lv('tw_slot')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"slot_data":"ok"}')

                lv_size = lvm.get_lv_size(lv_path)
                layout = calculate_slot_layout(lv_size)

                fd = open_lv(lv_path, readonly=True)
                try:
                    slot_raw = aligned_pread(fd, layout.slot_a_capacity,
                                            layout.slot_a_offset)
                finally:
                    os.close(fd)

            slot = parse_slot(slot_raw, expected_offset=layout.slot_a_offset,
                              expected_capacity=layout.slot_a_capacity)
            self.assertTrue(slot.valid)
            self.assertEqual(slot.payload, b'{"slot_data":"ok"}')
        finally:
            self._cleanup_lv(lv_path)

    def _test_slot_layout_matches_real_lv(self):
        lv_path = self._create_lv('tw_lay')
        try:
            with lvm.OperateLv(lv_path, shared=True):
                lv_size = lvm.get_lv_size(lv_path)

            layout = calculate_slot_layout(lv_size)
            self.assertEqual(layout.slot_a_offset, ALIGNMENT)
            end = layout.slot_b_offset + layout.slot_b_capacity
            self.assertLessEqual(end, lv_size)
            self.assertEqual(layout.slot_a_capacity, layout.slot_b_capacity)
        finally:
            self._cleanup_lv(lv_path)

    def _test_second_write_alternates_slot(self):
        lv_path = self._create_lv('tw_alt')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}', schema_version='1')
                r1 = self._read(lv_path)
                self.assertEqual(r1.header.active_slot, SLOT_A)

                self._write(lv_path, '{"v":2}', schema_version='1')
                r2 = self._read(lv_path)

            self.assertTrue(r2.header.valid)
            self.assertEqual(r2.header.active_slot, SLOT_B)
            self.assertEqual(r2.header.write_sequence, 2)
            self.assertEqual(r2.header.pending_op, PENDING_NONE)
        finally:
            self._cleanup_lv(lv_path)

    def _test_third_write_back_to_slot_a(self):
        lv_path = self._create_lv('tw_3rd')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, '{"v":1}')
                self._write(lv_path, '{"v":2}')
                self._write(lv_path, '{"v":3}')
                r = self._read(lv_path)

            self.assertEqual(r.header.active_slot, SLOT_A)
            self.assertEqual(r.header.write_sequence, 3)
        finally:
            self._cleanup_lv(lv_path)

    def _test_extend_triggered_for_large_payload(self):
        lv_path = self._create_lv('tw_ext')
        try:
            layout = calculate_slot_layout(INITIAL_LV_SIZE)
            max_payload = layout.slot_a_capacity - SLOT_OVERHEAD
            big_payload = 'x' * (max_payload + 100)

            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, big_payload)
                lv_size = lvm.get_lv_size(lv_path)

            self.assertGreater(lv_size, INITIAL_LV_SIZE,
                               "LV should have been extended")
        finally:
            self._cleanup_lv(lv_path)

    def _test_write_then_read_roundtrip(self):
        lv_path = self._create_lv('tw_rr')
        try:
            payload = json.dumps({"volumes": [{"uuid": "vol-1"}]})

            with lvm.OperateLv(lv_path, shared=False):
                self._write(lv_path, payload,
                            schema_version='2', vm_uuid='abc', vm_name='vm1')
                result = self._read(lv_path)

            self.assertEqual(result.status, 'OK')
            self.assertEqual(result.payload, payload.encode('utf-8'))
            self.assertTrue(result.header.valid)
            self.assertEqual(result.header.vm_uuid, 'abc')
        finally:
            self._cleanup_lv(lv_path)

    def _test_multiple_writes_read_latest(self):
        lv_path = self._create_lv('tw_multi')
        try:
            with lvm.OperateLv(lv_path, shared=False):
                for i in range(5):
                    self._write(lv_path, '{"version":%d}' % i)
                result = self._read(lv_path)

            self.assertEqual(result.status, 'OK')
            self.assertEqual(json.loads(result.payload)['version'], 4)
        finally:
            self._cleanup_lv(lv_path)

    @pytest_utils.ztest_decorater
    def test_lv_metadata_write(self):
        self._connect_vg()

        self._test_fresh_write_creates_header_and_slot()
        self._test_parse_header_from_real_lv()
        self._test_parse_slot_from_real_lv()
        self._test_slot_layout_matches_real_lv()
        self._test_second_write_alternates_slot()
        self._test_third_write_back_to_slot_a()
        self._test_extend_triggered_for_large_payload()
        self._test_write_then_read_roundtrip()
        self._test_multiple_writes_read_latest()
