"""lv_metadata: SblkMetadataHandler -- _do_write, _do_get, _do_scan, _do_cleanup.

Runs against a real SharedBlock VG provisioned via iSCSI (ztest pattern).
No mocks, no loopback VG -- uses the standard shareblock test infrastructure.
Each test scenario is a _test_xxx sub-method called from a single entry point."""

import json
import uuid as uuid_mod

from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import pytest_utils, storage_device_utils
from zstacklib.utils import bash, lvm
from zstacklib.utils.lv_protocol import INITIAL_LV_SIZE
from zstacklib.utils.lv_metadata import SblkMetadataHandler, read_metadata
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


class TestVmmetaHandler(TestCase, SharedBlockPluginTestStub):

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

    def _meta_path(self, vm_uuid):
        return '/dev/%s/%s_vmmeta' % (vgUuid, vm_uuid)

    def _cleanup_lv(self, lv_path):
        """Best-effort remove a test LV."""
        if lvm.lv_exists(lv_path):
            lvm.delete_lv(lv_path, raise_exception=False)

    # -- sub-tests ---------------------------------------------------------

    def _test_write_creates_lv(self, handler):
        tid = uuid_mod.uuid4().hex[:8]
        vm_uuid = 'abc%s' % tid
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"test":1}',
                vmUuid=vm_uuid, vmName='vm1',
                vmCategory='AppCenter', architecture='x86_64',
                schemaVersion='1')

            self.assertTrue(lvm.lv_exists(meta_path),
                            "metadata LV was not created")

            with lvm.OperateLv(meta_path, shared=True):
                lv_size = lvm.get_lv_size(meta_path)
                result = read_metadata(meta_path, lv_size)
            self.assertTrue(result.header.valid)
            self.assertEqual(result.header.vm_uuid, vm_uuid)
        finally:
            self._cleanup_lv(meta_path)

    def _test_write_existing_lv(self, handler):
        tid = uuid_mod.uuid4().hex[:8]
        vm_uuid = 'exist%s' % tid
        meta_path = self._meta_path(vm_uuid)

        try:
            lvm.create_lv_from_absolute_path(
                meta_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
            self.assertTrue(lvm.lv_exists(meta_path),
                            "pre-created LV should exist")

            handler._do_write(
                meta_path, '{"test":1}',
                vmUuid=vm_uuid, vmName='', vmCategory='',
                architecture='', schemaVersion='')

            self.assertTrue(lvm.lv_exists(meta_path))
            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
        finally:
            self._cleanup_lv(meta_path)

    def _test_get_nonexistent(self, handler):
        result = handler._do_get('/dev/%s/nonexistent_vmmeta' % vgUuid)
        self.assertIsNone(result['metadata'])

    def _test_write_then_get(self, handler):
        tid = uuid_mod.uuid4().hex[:8]
        vm_uuid = 'get%s' % tid
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"hello":"world"}',
                vmUuid=vm_uuid, vmName='', vmCategory='',
                architecture='', schemaVersion='')

            result = handler._do_get(meta_path)
            self.assertIsNotNone(result['metadata'])
            self.assertEqual(json.loads(result['metadata']), {"hello": "world"})
        finally:
            self._cleanup_lv(meta_path)

    def _test_cleanup_deletes_lv(self, handler):
        tid = uuid_mod.uuid4().hex[:8]
        vm_uuid = 'cleanup%s' % tid
        meta_path = self._meta_path(vm_uuid)

        lvm.create_lv_from_absolute_path(
            meta_path, INITIAL_LV_SIZE, lock=True, exact_size=True)
        self.assertTrue(lvm.lv_exists(meta_path),
                        "LV should exist before cleanup")

        handler._do_cleanup(meta_path)
        self.assertFalse(lvm.lv_exists(meta_path),
                         "LV should be deleted after cleanup")

    def _test_cleanup_nonexistent(self, handler):
        # should not raise
        handler._do_cleanup('/dev/%s/nonexistent_vmmeta' % vgUuid)

    def _test_scan_finds_metadata(self, handler):
        tid = uuid_mod.uuid4().hex[:8]
        vm_uuid = 'scan%s' % tid
        meta_path = self._meta_path(vm_uuid)

        try:
            handler._do_write(
                meta_path, '{"test":1}',
                vmUuid=vm_uuid, vmName='scan-vm',
                vmCategory='AppCenter', architecture='x86_64',
                schemaVersion='2')

            entries = handler._do_scan('/dev/%s' % vgUuid)
            found = [e for e in entries if e.vmUuid == vm_uuid]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].vmName, 'scan-vm')
            self.assertEqual(found[0].schemaVersion, '2')
        finally:
            self._cleanup_lv(meta_path)

    def _test_scan_returns_list(self, handler):
        entries = handler._do_scan('/dev/%s' % vgUuid)
        self.assertIsInstance(entries, list)

    # -- single entry point ------------------------------------------------

    @pytest_utils.ztest_decorater
    def test_vmmeta_handler(self):
        self._connect_vg()

        handler = SblkMetadataHandler(lvm, bash)

        self._test_write_creates_lv(handler)
        self._test_write_existing_lv(handler)
        self._test_get_nonexistent(handler)
        self._test_write_then_get(handler)
        self._test_cleanup_deletes_lv(handler)
        self._test_cleanup_nonexistent(handler)
        self._test_scan_finds_metadata(handler)
        self._test_scan_returns_list(handler)
