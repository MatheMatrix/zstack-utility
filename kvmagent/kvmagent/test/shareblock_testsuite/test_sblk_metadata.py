"""Integration tests for the 5 sblk metadata APIs.

Covers write / get / scan / cleanup / prefix_rebase at the Handler._do_xxx()
level using real LVs on an iSCSI-backed VG.  Requires the ztest environment
(iSCSI target + LVM VG).

Also covers low-level protocol verification (slot alternation, checksums,
slot layout, LV auto-extension).
"""

import hashlib
import json
import os
import threading
import uuid as uuid_mod
from unittest import TestCase

from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import pytest_utils, storage_device_utils

from zstacklib.test.utils import env
from zstacklib.utils import bash, lvm, linux
from zstacklib.utils.lv_metadata import (
    SblkMetadataHandler,
    read_metadata,
    calculate_slot_layout,
    open_lv, aligned_pread, aligned_pwrite,
    sblk_prefix_rebase_backing_files,
)
from zstacklib.utils.lv_protocol import (
    ALIGNMENT, HEADER_BLOCK_SIZE, HEADER_CHECKSUM_OFFSET,
    SLOT_A, SLOT_B, SLOT_OVERHEAD,
    PENDING_NONE,
    INITIAL_LV_SIZE, LV_METADATA_SUFFIX,
    parse_header, parse_slot,
)

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

LV_SIZE = 64 * 1024 * 1024  # 64MB for qcow2 images
MB = 1024 * 1024


# ---- helpers ----------------------------------------------------------------

def _create_qcow2_on_lv(lv_path, backing=None):
    with lvm.OperateLv(lv_path, shared=False):
        if backing:
            bash.bash_errorout(
                'qemu-img create -f qcow2 -b %s -F qcow2 %s'
                % (backing, lv_path))
        else:
            bash.bash_errorout(
                'qemu-img create -f qcow2 %s 32M' % lv_path)


def _get_backing(lv_path):
    with lvm.OperateLv(lv_path, shared=True):
        return linux.qcow2_get_backing_file(lv_path)


def _create_lv(name):
    """Create a small LV in the test VG, return /dev/<vg>/<name> path."""
    lv_path = '/dev/%s/%s' % (vgUuid, name)
    bash.bash_errorout(
        'lvcreate -y -ay --wipesignatures y '
        '--size %sb --name %s %s' % (LV_SIZE, name, vgUuid))
    return lv_path


def _delete_lv(lv_path):
    """Best-effort delete a test LV."""
    bash.bash_r('lvchange -an %s' % lv_path)
    bash.bash_r('lvremove -y %s' % lv_path)


def _force_backing(lv_path, backing_path):
    """Unsafe rebase to set backing path without checking existence."""
    with lvm.OperateLv(lv_path, shared=False):
        bash.bash_errorout(
            'qemu-img rebase -u -b %s -F qcow2 %s' % (backing_path, lv_path))


# #############################################################################
# TestSblkMetadataApi
# #############################################################################

class TestSblkMetadataApi(TestCase, SharedBlockPluginTestStub):

    @classmethod
    def setUpClass(cls):
        pass

    def _connect_vg(self):
        iscsi_server = env.get_vm_metadata('self')
        rsp = storage_device_utils.iscsi_login(iscsi_server.ip, "3260")
        self.assertEqual(rsp.success, True, "iscsiadm login failed")
        r, o = bash.bash_ro(
            "ls /dev/disk/by-id | grep scsi|awk -F '-' '{print $2}'")
        blockUuid = o.strip().replace(' ', '').replace('\n', '').replace('\r', '')
        rsp = self.connect(
            [blockUuid], [blockUuid], vgUuid, hostUuid, hostId, forceWipe=True)
        self.assertEqual(True, rsp.success, rsp.error)

    # -- helpers --------------------------------------------------------------

    def _meta_path(self, vm_uuid):
        return '/dev/%s/%s%s' % (vgUuid, vm_uuid, LV_METADATA_SUFFIX)

    def _create_lv(self, name):
        lv_path = '/dev/%s/%s' % (vgUuid, name)
        lvm.create_lv_from_absolute_path(
            lv_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
        return lv_path

    def _create_qcow2_lv(self, name):
        lv_path = '/dev/%s/%s' % (vgUuid, name)
        bash.bash_errorout(
            'lvcreate -y -ay --wipesignatures y '
            '--size %sb --name %s %s' % (LV_SIZE, name, vgUuid))
        return lv_path

    def _cleanup_lv(self, lv_path):
        if lvm.lv_exists(lv_path):
            lvm.delete_lv(lv_path, raise_exception=False)

    def _make_handler(self):
        return SblkMetadataHandler(lvm, bash)

    # -- low-level write/read helpers (bypass Handler, operate under lock) ----

    def _read_raw(self, lv_path):
        lv_size = lvm.get_lv_size(lv_path)
        return read_metadata(lv_path, lv_size)

    # == write_vm_metadata ====================================================

    def _test_write_creates_lv_and_stores_data(self, handler):
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"test":1}',
                vmUuid=vm_uuid, vmName='write-vm',
                vmCategory='AppCenter', architecture='x86_64',
                schemaVersion='1')

            self.assertTrue(lvm.lv_exists(meta_path),
                            "metadata LV should be created")
            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
            self.assertEqual(json.loads(result['metadata']), {"test": 1})
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_with_vm_summary(self, handler):
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"data":true}',
                vmUuid=vm_uuid, vmName='summary-vm',
                vmCategory='AppCenter', architecture='aarch64',
                schemaVersion='3')

            with lvm.OperateLv(meta_path, shared=True):
                lv_size = lvm.get_lv_size(meta_path)
                read_result = read_metadata(meta_path, lv_size)
            self.assertTrue(read_result.header.valid)
            self.assertEqual(read_result.header.vm_uuid, vm_uuid)
            self.assertEqual(read_result.header.vm_name, 'summary-vm')
            self.assertEqual(read_result.header.vm_category, 'AppCenter')
            self.assertEqual(read_result.header.architecture, 'aarch64')
            self.assertEqual(read_result.header.schema_version, '3')
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_overwrite_updates_payload(self, handler):
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"v":1}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')
            handler._do_write(
                meta_path, '{"v":2}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            result = handler._do_get(meta_path)
            self.assertEqual(json.loads(result['metadata']), {"v": 2})
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_to_pre_existing_lv(self, handler):
        """Write to a LV that was pre-created (not by handler), should work."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            lvm.create_lv_from_absolute_path(
                meta_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
            self.assertTrue(lvm.lv_exists(meta_path))

            handler._do_write(
                meta_path, '{"pre_existing":true}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
            self.assertEqual(json.loads(result['metadata']),
                             {"pre_existing": True})
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_slot_alternation(self, handler):
        """First write -> Slot A, second write -> Slot B."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"v":1}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='1')

            with lvm.OperateLv(meta_path, shared=True):
                r1 = self._read_raw(meta_path)
            self.assertEqual(r1.header.active_slot, SLOT_A)

            handler._do_write(
                meta_path, '{"v":2}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='1')

            with lvm.OperateLv(meta_path, shared=True):
                r2 = self._read_raw(meta_path)
            self.assertEqual(r2.header.active_slot, SLOT_B)
            self.assertEqual(r2.header.write_sequence, 2)
            self.assertEqual(r2.header.pending_op, PENDING_NONE)
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_third_back_to_slot_a(self, handler):
        """Three writes alternate: A -> B -> A."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            for i in range(3):
                handler._do_write(
                    meta_path, '{"v":%d}' % (i + 1),
                    vmUuid=vm_uuid, vmName='',
                    vmCategory='', architecture='',
                    schemaVersion='')

            with lvm.OperateLv(meta_path, shared=True):
                r = self._read_raw(meta_path)
            self.assertEqual(r.header.active_slot, SLOT_A)
            self.assertEqual(r.header.write_sequence, 3)
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_header_checksum_valid(self, handler):
        """Raw header on disk has valid SHA-256 checksum."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"checksum_test":true}',
                vmUuid=vm_uuid, vmName='chk-vm',
                vmCategory='', architecture='',
                schemaVersion='2')

            with lvm.OperateLv(meta_path, shared=True):
                fd = open_lv(meta_path, readonly=True)
                try:
                    raw = aligned_pread(fd, HEADER_BLOCK_SIZE, 0)
                finally:
                    os.close(fd)

            h = parse_header(raw)
            self.assertTrue(h.valid)
            self.assertEqual(h.vm_uuid, vm_uuid)
            checksum = raw[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + 32]
            self.assertEqual(checksum,
                             hashlib.sha256(raw[:HEADER_CHECKSUM_OFFSET]).digest())
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_slot_data_valid(self, handler):
        """Raw slot data on disk passes parse_slot validation."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"slot_verify":"ok"}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            with lvm.OperateLv(meta_path, shared=True):
                lv_size = lvm.get_lv_size(meta_path)
                layout = calculate_slot_layout(lv_size)

                fd = open_lv(meta_path, readonly=True)
                try:
                    slot_raw = aligned_pread(fd, layout.slot_a_capacity,
                                             layout.slot_a_offset)
                finally:
                    os.close(fd)

            slot = parse_slot(slot_raw,
                              expected_offset=layout.slot_a_offset,
                              expected_capacity=layout.slot_a_capacity)
            self.assertTrue(slot.valid)
            self.assertEqual(slot.payload, b'{"slot_verify":"ok"}')
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_slot_layout_geometry(self, handler):
        """Slot layout from real LV matches expected geometry."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            with lvm.OperateLv(meta_path, shared=True):
                lv_size = lvm.get_lv_size(meta_path)

            layout = calculate_slot_layout(lv_size)
            self.assertEqual(layout.slot_a_offset, ALIGNMENT)
            end = layout.slot_b_offset + layout.slot_b_capacity
            self.assertLessEqual(end, lv_size)
            self.assertEqual(layout.slot_a_capacity, layout.slot_b_capacity)
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_extend_for_large_payload(self, handler):
        """Large payload triggers LV auto-extension."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            layout = calculate_slot_layout(INITIAL_LV_SIZE)
            max_payload = layout.slot_a_capacity - SLOT_OVERHEAD
            big_payload = 'x' * (max_payload + 100)

            handler._do_write(
                meta_path, big_payload,
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            with lvm.OperateLv(meta_path, shared=True):
                lv_size = lvm.get_lv_size(meta_path)

            self.assertGreater(lv_size, INITIAL_LV_SIZE,
                               "LV should have been extended")

            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_multiple_sequential(self, handler):
        """5 sequential writes, read returns the latest."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            for i in range(5):
                handler._do_write(
                    meta_path, '{"version":%d}' % i,
                    vmUuid=vm_uuid, vmName='',
                    vmCategory='', architecture='',
                    schemaVersion='')

            result = handler._do_get(meta_path)
            self.assertEqual(json.loads(result['metadata']),
                             {"version": 4})
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_sequence_monotonic(self, handler):
        """Write sequence strictly increases across writes."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            prev_seq = 0
            for i in range(4):
                handler._do_write(
                    meta_path, '{"i":%d}' % i,
                    vmUuid=vm_uuid, vmName='',
                    vmCategory='', architecture='',
                    schemaVersion='')

                with lvm.OperateLv(meta_path, shared=True):
                    r = self._read_raw(meta_path)
                self.assertGreater(r.header.write_sequence, prev_seq,
                                   "write_sequence must be strictly increasing")
                prev_seq = r.header.write_sequence
        finally:
            self._cleanup_lv(meta_path)

    # == get_vm_instance_metadata =============================================

    def _test_get_nonexistent_returns_none(self, handler):
        meta_path = self._meta_path('00' * 16)
        result = handler._do_get(meta_path)
        self.assertIsNone(result['metadata'])

    def _test_get_after_write_returns_payload(self, handler):
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            payload = '{"key":"value","num":42}'
            handler._do_write(
                meta_path, payload,
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')

            result = handler._do_get(meta_path)
            self.assertEqual(json.loads(result['metadata']),
                             json.loads(payload))
        finally:
            self._cleanup_lv(meta_path)

    # == scan_vm_metadata =====================================================

    def _test_scan_finds_written_metadata(self, handler):
        uuid_1 = uuid_mod.uuid4().hex
        uuid_2 = uuid_mod.uuid4().hex
        meta_1 = self._meta_path(uuid_1)
        meta_2 = self._meta_path(uuid_2)

        try:
            handler._do_write(
                meta_1, '{"vm":1}',
                vmUuid=uuid_1, vmName='scan-one',
                vmCategory='AppCenter', architecture='x86_64',
                schemaVersion='1')
            handler._do_write(
                meta_2, '{"vm":2}',
                vmUuid=uuid_2, vmName='scan-two',
                vmCategory='', architecture='aarch64',
                schemaVersion='2')

            entries = handler._do_scan('/dev/%s' % vgUuid)

            by_uuid = {e.vmUuid: e for e in entries}
            self.assertIn(uuid_1, by_uuid)
            self.assertIn(uuid_2, by_uuid)
            self.assertEqual(by_uuid[uuid_1].vmName, 'scan-one')
            self.assertEqual(by_uuid[uuid_2].architecture, 'aarch64')
            self.assertEqual(by_uuid[uuid_2].schemaVersion, '2')
        finally:
            self._cleanup_lv(meta_1)
            self._cleanup_lv(meta_2)

    def _test_scan_empty_vg_returns_empty_list(self, handler):
        """Scan should return empty list (or at least not crash) on a VG
        with no _vmmeta LVs.  Note: other tests may leave LVs, so we only
        verify the call succeeds and returns a list."""
        entries = handler._do_scan('/dev/%s' % vgUuid)
        self.assertIsInstance(entries, list)

    # == cleanup_vm_metadata ==================================================

    def _test_cleanup_deletes_lv(self, handler):
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"cleanup":true}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')
            self.assertTrue(lvm.lv_exists(meta_path))

            handler._do_cleanup(meta_path)
            self.assertFalse(lvm.lv_exists(meta_path))

            result = handler._do_get(meta_path)
            self.assertIsNone(result['metadata'])
        finally:
            self._cleanup_lv(meta_path)

    def _test_cleanup_nonexistent_is_noop(self, handler):
        meta_path = self._meta_path('ff' * 16)
        # should not raise
        handler._do_cleanup(meta_path)

    def _test_cleanup_plain_lv(self, handler):
        """Cleanup a LV that was created directly (not via _do_write)."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            lvm.create_lv_from_absolute_path(
                meta_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
            self.assertTrue(lvm.lv_exists(meta_path))

            handler._do_cleanup(meta_path)
            self.assertFalse(lvm.lv_exists(meta_path))
        finally:
            self._cleanup_lv(meta_path)

    # == prefix_rebase_backing_files ==========================================

    def _test_rebase_empty_file_paths_returns_zero(self):
        count = sblk_prefix_rebase_backing_files(
            [], '/dev/old_vg', '/dev/new_vg', translate_absolute_path_from_install_path, lvm)
        self.assertEqual(count, 0)

    def _test_rebase_empty_old_prefix_raises(self):
        with self.assertRaises(Exception):
            sblk_prefix_rebase_backing_files(
                [], '', '/dev/new/', translate_absolute_path_from_install_path, lvm)

    def _test_rebase_no_backing_returns_zero(self):
        tid = uuid_mod.uuid4().hex[:8]
        vol_lv = self._create_qcow2_lv('api_nobk_%s' % tid)
        try:
            _create_qcow2_on_lv(vol_lv)
            count = sblk_prefix_rebase_backing_files(
                [vol_lv], '/dev/some_old_vg', '/dev/%s' % vgUuid,
                translate_absolute_path_from_install_path, lvm)
            self.assertEqual(count, 0)
        finally:
            _delete_lv(vol_lv)

    def _test_rebase_no_matching_prefix_returns_zero(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = self._create_qcow2_lv('api_nmbase_%s' % tid)
        vol_lv = self._create_qcow2_lv('api_nmvol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            backing_before = _get_backing(vol_lv)
            self.assertEqual(backing_before, base_lv)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/nonexistent_old_vg',
                '/dev/nonexistent_new_vg',
                translate_absolute_path_from_install_path, lvm)
            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_rebase_sharedblock_scheme_normalized(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = self._create_qcow2_lv('api_sbase_%s' % tid)
        vol_lv = self._create_qcow2_lv('api_svol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            sblk_vol = 'sharedblock:/%s/api_svol_%s' % (vgUuid, tid)

            count = sblk_prefix_rebase_backing_files(
                [sblk_vol],
                'sharedblock:/%s' % vgUuid,
                'sharedblock:/%s' % vgUuid,
                translate_absolute_path_from_install_path, lvm)

            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_rebase_new_backing_missing_skips(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = self._create_qcow2_lv('api_mbase_%s' % tid)
        vol_lv = self._create_qcow2_lv('api_mvol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/%s' % vgUuid,
                '/dev/nonexistent_new_vg',
                translate_absolute_path_from_install_path, lvm)
            self.assertEqual(count, 0)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_rebase_multi_level_chain_no_match(self):
        """vol -> snap -> base, none matching old_prefix => count=0."""
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = self._create_qcow2_lv('api_cbase_%s' % tid)
        snap_lv = self._create_qcow2_lv('api_csnap_%s' % tid)
        vol_lv = self._create_qcow2_lv('api_cvol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(snap_lv, backing=base_lv)
            _create_qcow2_on_lv(vol_lv, backing=snap_lv)

            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/nonexistent_vg',
                '/dev/%s' % vgUuid,
                translate_absolute_path_from_install_path, lvm)

            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(snap_lv)
            _delete_lv(base_lv)

    def _test_rebase_concurrent_no_deadlock(self):
        tid = uuid_mod.uuid4().hex[:8]
        num_vols = 3
        base_lvs = [self._create_qcow2_lv('api_ccb_%s_%d' % (tid, i))
                    for i in range(num_vols)]
        vol_lvs = [self._create_qcow2_lv('api_ccv_%s_%d' % (tid, i))
                   for i in range(num_vols)]
        try:
            for base in base_lvs:
                _create_qcow2_on_lv(base)
            for i, vol in enumerate(vol_lvs):
                _create_qcow2_on_lv(vol, backing=base_lvs[i])

            errors = []
            start_event = threading.Event()

            def rebase_one(idx):
                try:
                    start_event.wait(30)
                    sblk_prefix_rebase_backing_files(
                        [vol_lvs[idx]],
                        '/dev/nonexistent_vg',
                        '/dev/%s' % vgUuid,
                        translate_absolute_path_from_install_path, lvm)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=rebase_one, args=(i,))
                       for i in range(num_vols)]
            for t in threads:
                t.start()
            start_event.set()
            for t in threads:
                t.join(timeout=60)
            for t in threads:
                self.assertFalse(t.is_alive(),
                                 "concurrent rebase deadlocked")

            self.assertEqual(len(errors), 0,
                             "concurrent rebase raised: %s" % errors)
            for i, vol in enumerate(vol_lvs):
                self.assertEqual(_get_backing(vol), base_lvs[i])
        finally:
            for lv in vol_lvs + base_lvs:
                _delete_lv(lv)

    def _test_rebase_single_success(self):
        """vol backs to /dev/<fake_vg>/base, rebase to /dev/<real_vg>/base."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        base_name = 'api_pbase_%s' % tid
        vol_name = 'api_pvol_%s' % tid

        base_lv = self._create_qcow2_lv(base_name)
        vol_lv = self._create_qcow2_lv(vol_name)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            fake_backing = '/dev/%s/%s' % (fake_vg, base_name)
            _force_backing(vol_lv, fake_backing)
            self.assertEqual(_get_backing(vol_lv), fake_backing)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/%s' % fake_vg,
                '/dev/%s' % vgUuid,
                translate_absolute_path_from_install_path, lvm)

            self.assertEqual(count, 1)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_rebase_multi_level_success(self):
        """vol -> snap -> base, all with fake VG backing => count=2."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        base_name = 'api_mlb_%s' % tid
        snap_name = 'api_mls_%s' % tid
        vol_name = 'api_mlv_%s' % tid

        base_lv = self._create_qcow2_lv(base_name)
        snap_lv = self._create_qcow2_lv(snap_name)
        vol_lv = self._create_qcow2_lv(vol_name)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(snap_lv, backing=base_lv)
            _create_qcow2_on_lv(vol_lv, backing=snap_lv)

            fake_base = '/dev/%s/%s' % (fake_vg, base_name)
            fake_snap = '/dev/%s/%s' % (fake_vg, snap_name)
            _force_backing(snap_lv, fake_base)
            _force_backing(vol_lv, fake_snap)

            self.assertEqual(_get_backing(vol_lv), fake_snap)
            self.assertEqual(_get_backing(snap_lv), fake_base)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/%s' % fake_vg,
                '/dev/%s' % vgUuid,
                translate_absolute_path_from_install_path, lvm)

            self.assertEqual(count, 2)
            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(snap_lv)
            _delete_lv(base_lv)

    def _test_rebase_concurrent_positive(self):
        """Multiple vols each need rebase, run concurrently => all succeed."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        num_vols = 3
        base_names = ['api_cpb_%s_%d' % (tid, i) for i in range(num_vols)]
        vol_names = ['api_cpv_%s_%d' % (tid, i) for i in range(num_vols)]

        base_lvs = [self._create_qcow2_lv(n) for n in base_names]
        vol_lvs = [self._create_qcow2_lv(n) for n in vol_names]
        try:
            for base in base_lvs:
                _create_qcow2_on_lv(base)
            for i, vol in enumerate(vol_lvs):
                _create_qcow2_on_lv(vol, backing=base_lvs[i])

            for i, vol in enumerate(vol_lvs):
                fake_backing = '/dev/%s/%s' % (fake_vg, base_names[i])
                _force_backing(vol, fake_backing)

            errors = []
            results = [None] * num_vols
            start_event = threading.Event()

            def rebase_one(idx):
                try:
                    start_event.wait(30)
                    c = sblk_prefix_rebase_backing_files(
                        [vol_lvs[idx]],
                        '/dev/%s' % fake_vg,
                        '/dev/%s' % vgUuid,
                        translate_absolute_path_from_install_path, lvm)
                    results[idx] = c
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=rebase_one, args=(i,))
                       for i in range(num_vols)]
            for t in threads:
                t.start()
            start_event.set()
            for t in threads:
                t.join(timeout=60)
            for t in threads:
                self.assertFalse(t.is_alive(),
                                 "concurrent positive rebase deadlocked")

            self.assertEqual(len(errors), 0,
                             "concurrent positive rebase raised: %s" % errors)

            total = sum(r for r in results if r is not None)
            self.assertEqual(total, num_vols,
                             "expected %d rebases, got %d" % (num_vols, total))

            for i, vol in enumerate(vol_lvs):
                self.assertEqual(_get_backing(vol), base_lvs[i])
        finally:
            for lv in vol_lvs + base_lvs:
                _delete_lv(lv)

    # == edge cases (S7-S10) ==================================================

    def _test_write_with_corrupted_header(self, handler):
        """S7: _initialize_if_needed skips initialization when the header is
        non-zero but invalid.  write_metadata falls back to a fresh write and
        the payload is still retrievable."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            # Step 1: create the metadata LV manually (blank, all zeros)
            lvm.create_lv_from_absolute_path(
                meta_path, INITIAL_LV_SIZE, lock=True, exact_size=True)

            # Step 2: corrupt the header with non-zero garbage
            with lvm.OperateLv(meta_path, shared=False):
                garbage = b'\xDE\xAD' * (HEADER_BLOCK_SIZE // 2)
                fd = open_lv(meta_path, readonly=False)
                try:
                    aligned_pwrite(fd, garbage, 0)
                finally:
                    os.close(fd)

                # Verify the header is now invalid
                fd2 = open_lv(meta_path, readonly=True)
                try:
                    raw = aligned_pread(fd2, HEADER_BLOCK_SIZE, 0)
                    h = parse_header(raw)
                finally:
                    os.close(fd2)
                self.assertFalse(h.valid,
                                 "header should be invalid after corruption")
                self.assertNotEqual(raw, b'\x00' * HEADER_BLOCK_SIZE,
                                    "header should be non-zero")

            # Step 3: write through the handler — should NOT crash
            handler._do_write(
                meta_path, '{"corrupted_header_test": true}',
                vmUuid=vm_uuid, vmName='corrupted',
                vmCategory='', architecture='',
                schemaVersion='1')

            # Step 4: verify payload is retrievable
            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
            self.assertEqual(json.loads(result['metadata']),
                             {"corrupted_header_test": True})
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_concurrent_creates_same_lv(self, handler):
        """S8: _ensure_metadata_lv tolerates concurrent creation of the same
        metadata LV — no exception should propagate."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        errors = []
        start_event = threading.Event()

        def writer(payload_val):
            try:
                start_event.wait(30)
                h = self._make_handler()
                h._do_write(
                    meta_path, '{"t":%d}' % payload_val,
                    vmUuid=vm_uuid, vmName='',
                    vmCategory='', architecture='',
                    schemaVersion='')
            except Exception as e:
                errors.append(e)

        try:
            threads = [threading.Thread(target=writer, args=(i,))
                       for i in range(4)]
            for t in threads:
                t.start()
            start_event.set()
            for t in threads:
                t.join(timeout=60)
            for t in threads:
                self.assertFalse(t.is_alive(),
                                 "concurrent write deadlocked")

            self.assertEqual(len(errors), 0,
                             "concurrent writes raised: %s" % errors)

            # Final state should be readable
            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
        finally:
            self._cleanup_lv(meta_path)

    def _test_get_after_cleanup_returns_none(self, handler):
        """S9: write -> cleanup -> get in sequence; get must return None.
        Exercises the _do_get code path that handles a disappeared LV."""
        vm_uuid = uuid_mod.uuid4().hex
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"will_be_cleaned": true}',
                vmUuid=vm_uuid, vmName='',
                vmCategory='', architecture='',
                schemaVersion='')
            self.assertTrue(lvm.lv_exists(meta_path))

            handler._do_cleanup(meta_path)
            self.assertFalse(lvm.lv_exists(meta_path))

            result = handler._do_get(meta_path)
            self.assertIsNone(result['metadata'],
                              "get after cleanup should return None")
        finally:
            self._cleanup_lv(meta_path)

    def _test_scan_invalid_vg_name_raises(self, handler):
        """S10: _lv_list_func rejects VG names with shell-injection
        characters by raising an exception."""
        bad_names = [
            'vg; rm -rf /',
            'vg$(whoami)',
            'vg`id`',
            'vg|cat /etc/passwd',
            'vg && echo pwned',
        ]
        for bad in bad_names:
            with self.assertRaises(Exception,
                                   msg="should reject VG name: %s" % bad):
                handler._lv_list_func(bad)

    # -- single entry point ---------------------------------------------------

    @pytest_utils.ztest_decorater
    def test_sblk_metadata_api(self):
        self._connect_vg()

        handler = self._make_handler()

        # write (12 tests)
        self._test_write_creates_lv_and_stores_data(handler)
        self._test_write_with_vm_summary(handler)
        self._test_write_overwrite_updates_payload(handler)
        self._test_write_to_pre_existing_lv(handler)
        self._test_write_slot_alternation(handler)
        self._test_write_third_back_to_slot_a(handler)
        self._test_write_header_checksum_valid(handler)
        self._test_write_slot_data_valid(handler)
        self._test_write_slot_layout_geometry(handler)
        self._test_write_extend_for_large_payload(handler)
        self._test_write_multiple_sequential(handler)
        self._test_write_sequence_monotonic(handler)

        # get (2 tests)
        self._test_get_nonexistent_returns_none(handler)
        self._test_get_after_write_returns_payload(handler)

        # scan (2 tests)
        self._test_scan_finds_written_metadata(handler)
        self._test_scan_empty_vg_returns_empty_list(handler)

        # cleanup (3 tests)
        self._test_cleanup_deletes_lv(handler)
        self._test_cleanup_nonexistent_is_noop(handler)
        self._test_cleanup_plain_lv(handler)

        # prefix_rebase (12 tests)
        self._test_rebase_empty_file_paths_returns_zero()
        self._test_rebase_empty_old_prefix_raises()
        self._test_rebase_no_backing_returns_zero()
        self._test_rebase_no_matching_prefix_returns_zero()
        self._test_rebase_sharedblock_scheme_normalized()
        self._test_rebase_new_backing_missing_skips()
        self._test_rebase_multi_level_chain_no_match()
        self._test_rebase_concurrent_no_deadlock()
        self._test_rebase_single_success()
        self._test_rebase_multi_level_success()
        self._test_rebase_concurrent_positive()
