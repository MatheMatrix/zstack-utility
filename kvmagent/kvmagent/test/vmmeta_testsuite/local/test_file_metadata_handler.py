import json
import os
import shutil
import tempfile
import threading
import time
from unittest import TestCase

from kvmagent.test.utils import pytest_utils
from kvmagent.test.utils.stub import *

from zstacklib.utils.file_metadata_handler import FileBasedMetadataHandler

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {}
}


class TestFileMetadataHandler(TestCase):
    @classmethod
    def setUpClass(cls):
        return

    def setUp(self):
        self.handler = FileBasedMetadataHandler()
        self.tmpdir = tempfile.mkdtemp(prefix='vmmeta_handler_')

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmpdir):
            os.chmod(root, 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- helpers -----------------------------------------------------------

    def _clean_tmpdir(self):
        """Remove all files and subdirectories inside self.tmpdir so that
        subsequent sub-tests start with a clean slate.  The directory
        itself is kept."""
        for root, dirs, files in os.walk(self.tmpdir, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    os.chmod(fp, 0o644)
                    os.remove(fp)
                except OSError:
                    pass
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    os.chmod(dp, 0o755)
                    os.rmdir(dp)
                except OSError:
                    pass

    def _touch(self, name, content='data'):
        path = os.path.join(self.tmpdir, name)
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.makedirs(d)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def _write_summary(self, meta_name, summary_dict):
        path = os.path.join(self.tmpdir, meta_name + '.summary')
        with open(path, 'w') as f:
            f.write(json.dumps(summary_dict))
        return path

    # == _do_write sub-tests ===============================================

    def _test_write_then_read_returns_same_content(self):
        meta_path = os.path.join(self.tmpdir, 'meta', 'abc123.vmmeta')
        payload = '{"volumes":["vol-1"]}'

        self.handler._do_write(meta_path, payload,
                               vmUuid='abc123', vmName='test-vm',
                               vmCategory='AppCenter', architecture='x86_64',
                               schemaVersion='1')

        result = self.handler._do_get(meta_path)
        self.assertEqual(result['metadata'], payload)

    def _test_write_creates_parent_dir(self):
        nested = os.path.join(self.tmpdir, 'a', 'b', 'c', 'test.vmmeta')
        self.handler._do_write(nested, '{}',
                               vmUuid='aaa', vmName='', vmCategory='',
                               architecture='', schemaVersion='')
        self.assertTrue(os.path.isfile(nested))

    def _test_write_creates_summary_file(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        self.handler._do_write(meta_path, '{}',
                               vmUuid='abc123', vmName='my-vm',
                               vmCategory='AppCenter', architecture='x86_64',
                               schemaVersion='2')

        summary_path = meta_path + '.summary'
        self.assertTrue(os.path.isfile(summary_path))

        with open(summary_path, 'r') as f:
            summary = json.loads(f.read())
        self.assertEqual(summary['vmUuid'], 'abc123')
        self.assertEqual(summary['vmName'], 'my-vm')
        self.assertEqual(summary['vmCategory'], 'AppCenter')
        self.assertEqual(summary['architecture'], 'x86_64')
        self.assertEqual(summary['schemaVersion'], '2')

    def _test_write_without_vm_uuid_removes_stale_summary(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        summary_path = meta_path + '.summary'

        self.handler._do_write(meta_path, '{}',
                               vmUuid='abc123', vmName='vm1',
                               vmCategory='', architecture='',
                               schemaVersion='')
        self.assertTrue(os.path.isfile(summary_path))

        self.handler._do_write(meta_path, '{}',
                               vmUuid='', vmName='',
                               vmCategory='', architecture='',
                               schemaVersion='')
        self.assertFalse(os.path.isfile(summary_path))

    def _test_write_does_not_leave_tmp_file(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        self.handler._do_write(meta_path, '{"ok":true}',
                               vmUuid='abc123', vmName='',
                               vmCategory='', architecture='',
                               schemaVersion='')
        self.assertFalse(os.path.exists(meta_path + '.tmp'))

    def _test_overwrite_updates_content(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        self.handler._do_write(meta_path, '{"v":1}',
                               vmUuid='abc123', vmName='',
                               vmCategory='', architecture='',
                               schemaVersion='')
        self.handler._do_write(meta_path, '{"v":2}',
                               vmUuid='abc123', vmName='',
                               vmCategory='', architecture='',
                               schemaVersion='')

        result = self.handler._do_get(meta_path)
        self.assertEqual(result['metadata'], '{"v":2}')

    def _test_concurrent_writes_do_not_corrupt(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        errors = []
        start_event = threading.Event()

        def writer(idx):
            try:
                start_event.wait(5)
                payload = '{"writer":%d}' % idx
                self.handler._do_write(meta_path, payload,
                                       vmUuid='abc123', vmName='',
                                       vmCategory='', architecture='',
                                       schemaVersion='')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        start_event.set()
        for t in threads:
            t.join(timeout=10)
        for t in threads:
            self.assertFalse(t.is_alive(), "concurrent write deadlocked")

        self.assertEqual(len(errors), 0, "concurrent writes raised: %s" % errors)
        result = self.handler._do_get(meta_path)
        self.assertIsNotNone(result['metadata'])
        data = json.loads(result['metadata'])
        self.assertIn('writer', data)

    def _test_write_read_unicode_content(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        payload = u'{"name":"\u6d4b\u8bd5\u865a\u62df\u673a"}'
        self.handler._do_write(meta_path, payload,
                               vmUuid='abc123', vmName=u'\u6d4b\u8bd5VM',
                               vmCategory='', architecture='',
                               schemaVersion='')

        result = self.handler._do_get(meta_path)
        self.assertIn(u'\u6d4b\u8bd5', result['metadata'])

    # == _do_get sub-tests =================================================

    def _test_read_missing_file_returns_none(self):
        meta_path = os.path.join(self.tmpdir, 'nonexistent.vmmeta')
        result = self.handler._do_get(meta_path)
        self.assertIsNone(result['metadata'])

    def _test_read_with_orphan_tmp_returns_none(self):
        """If only a .tmp file exists (crash before rename), read returns None
        and does NOT promote the .tmp to the final path."""
        meta_path = os.path.join(self.tmpdir, 'orphan_tmp_only.vmmeta')
        tmp_path = meta_path + '.tmp'
        with open(tmp_path, 'w') as f:
            f.write('partial data')

        result = self.handler._do_get(meta_path)
        self.assertIsNone(result['metadata'])
        self.assertFalse(os.path.isfile(meta_path))
        self.assertTrue(os.path.isfile(tmp_path))

    # == _do_scan sub-tests ================================================

    def _test_scan_finds_vmmeta_files(self):
        uuid_hex = 'a' * 32
        self._touch(uuid_hex + '.vmmeta', '{"test":1}')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].vmUuid, uuid_hex)
        self.assertFalse(entries[0].incomplete)
        self.assertGreater(entries[0].sizeBytes, 0)

    def _test_scan_multiple_files(self):
        for i in range(3):
            uuid_hex = ('%x' % i) * 32
            self._touch(uuid_hex + '.vmmeta')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 3)

    def _test_scan_ignores_non_uuid_filenames(self):
        self._touch('not-a-uuid.vmmeta')
        self._touch('SHORT.vmmeta')
        self._touch('ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ.vmmeta')
        uuid_hex = 'a1b2c3d4e5f6' + 'a' * 20
        self._touch(uuid_hex + '.vmmeta')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].vmUuid, uuid_hex)

    def _test_scan_ignores_unrelated_files(self):
        self._touch('readme.txt')
        self._touch('a' * 32 + '.json')
        self._touch('a' * 32 + '.summary')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 0)

    def _test_scan_tmp_only_entry_marked_incomplete(self):
        uuid_hex = 'b' * 32
        self._touch(uuid_hex + '.vmmeta.tmp', 'partial')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].incomplete)
        expected_path = os.path.join(self.tmpdir, uuid_hex + '.vmmeta')
        self.assertEqual(entries[0].metadataPath, expected_path)

    def _test_scan_tmp_ignored_when_final_exists(self):
        """If both .vmmeta and .vmmeta.tmp exist, only the final file is reported."""
        uuid_hex = 'c' * 32
        self._touch(uuid_hex + '.vmmeta', '{"final":true}')
        self._touch(uuid_hex + '.vmmeta.tmp', '{"tmp":true}')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0].incomplete)

    def _test_scan_reads_summary_sidecar(self):
        uuid_hex = 'd' * 32
        self._touch(uuid_hex + '.vmmeta', '{}')
        self._write_summary(uuid_hex + '.vmmeta', {
            'vmUuid': uuid_hex,
            'vmName': 'test-vm',
            'vmCategory': 'AppCenter',
            'architecture': 'x86_64',
            'schemaVersion': '2',
        })

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].vmName, 'test-vm')
        self.assertEqual(entries[0].vmCategory, 'AppCenter')
        self.assertEqual(entries[0].architecture, 'x86_64')
        self.assertEqual(entries[0].schemaVersion, '2')

    def _test_scan_tmp_entry_does_not_read_summary(self):
        """Summary is NOT loaded for incomplete (.tmp-only) entries."""
        uuid_hex = 'e' * 32
        self._touch(uuid_hex + '.vmmeta.tmp', 'partial')
        self._write_summary(uuid_hex + '.vmmeta', {
            'vmUuid': uuid_hex,
            'vmName': 'should-not-appear',
        })

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].vmName, '')

    def _test_scan_tolerates_corrupt_summary(self):
        uuid_hex = 'f' * 32
        self._touch(uuid_hex + '.vmmeta', '{}')
        with open(os.path.join(self.tmpdir, uuid_hex + '.vmmeta.summary'), 'w') as f:
            f.write('NOT JSON')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].vmName, '')

    def _test_scan_empty_directory(self):
        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 0)

    def _test_scan_missing_directory(self):
        missing_dir = os.path.join(self.tmpdir, 'missing_subdir_xyz')
        entries = self.handler._do_scan(missing_dir)
        self.assertEqual(len(entries), 0)

    def _test_scan_relative_path_returns_empty(self):
        entries = self.handler._do_scan('relative/path')
        self.assertEqual(len(entries), 0)

    def _test_scan_none_returns_empty(self):
        entries = self.handler._do_scan(None)
        self.assertEqual(len(entries), 0)

    def _test_scan_populates_last_update_time(self):
        uuid_hex = 'a' * 32
        before_ms = int(time.time() * 1000)
        self._touch(uuid_hex + '.vmmeta', '{}')

        entries = self.handler._do_scan(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertGreaterEqual(entries[0].lastUpdateTime, before_ms - 1000)

    # == _do_cleanup sub-tests =============================================

    def _test_cleanup_removes_all_related_files(self):
        base = 'abc123.vmmeta'
        meta_path = self._touch(base)
        self._touch(base + '.tmp')
        self._touch(base + '.summary')
        self._touch(base + '.summary.tmp')

        self.handler._do_cleanup(meta_path)

        self.assertFalse(os.path.exists(meta_path))
        self.assertFalse(os.path.exists(meta_path + '.tmp'))
        self.assertFalse(os.path.exists(meta_path + '.summary'))
        self.assertFalse(os.path.exists(meta_path + '.summary.tmp'))

    def _test_cleanup_only_main_file(self):
        meta_path = self._touch('abc123.vmmeta')
        self.handler._do_cleanup(meta_path)
        self.assertFalse(os.path.exists(meta_path))

    def _test_cleanup_main_plus_summary(self):
        meta_path = self._touch('abc123.vmmeta')
        self._touch('abc123.vmmeta.summary')
        self.handler._do_cleanup(meta_path)
        self.assertFalse(os.path.exists(meta_path))
        self.assertFalse(os.path.exists(meta_path + '.summary'))

    def _test_cleanup_nonexistent_is_noop(self):
        meta_path = os.path.join(self.tmpdir, 'nonexistent.vmmeta')
        self.handler._do_cleanup(meta_path)

    def _test_cleanup_raises_if_main_file_cannot_be_removed(self):
        if os.getuid() == 0:
            # root can remove files from read-only dirs, skip this test
            return
        meta_path = self._touch('abc123.vmmeta')
        os.chmod(self.tmpdir, 0o444)
        try:
            with self.assertRaises(Exception) as ctx:
                self.handler._do_cleanup(meta_path)
            self.assertIn('failed to cleanup metadata file', str(ctx.exception))
        finally:
            os.chmod(self.tmpdir, 0o755)

    def _test_cleanup_tolerates_sidecar_removal_failure(self):
        """Verify cleanup succeeds even if summary doesn't exist."""
        meta_path = self._touch('abc123.vmmeta')
        summary_path = self._touch('abc123.vmmeta.summary')

        os.remove(summary_path)
        self.handler._do_cleanup(meta_path)
        self.assertFalse(os.path.exists(meta_path))

    def _test_write_cleanup_read_returns_none(self):
        meta_path = os.path.join(self.tmpdir, 'abc123.vmmeta')
        self.handler._do_write(meta_path, '{"data":1}',
                               vmUuid='abc123', vmName='vm1',
                               vmCategory='', architecture='',
                               schemaVersion='')
        self.assertTrue(os.path.isfile(meta_path))

        self.handler._do_cleanup(meta_path)

        result = self.handler._do_get(meta_path)
        self.assertIsNone(result['metadata'])
        self.assertFalse(os.path.exists(meta_path + '.summary'))

    def _test_cleanup_does_not_remove_parent_directory(self):
        meta_path = self._touch('abc123.vmmeta')
        self.handler._do_cleanup(meta_path)
        self.assertTrue(os.path.isdir(self.tmpdir))

    # -- single entry point ------------------------------------------------

    @pytest_utils.ztest_decorater
    def test_file_metadata_handler(self):
        # _do_write
        self._test_write_then_read_returns_same_content()
        self._test_write_creates_parent_dir()
        self._test_write_creates_summary_file()
        self._test_write_without_vm_uuid_removes_stale_summary()
        self._test_write_does_not_leave_tmp_file()
        self._test_overwrite_updates_content()
        self._test_concurrent_writes_do_not_corrupt()
        self._test_write_read_unicode_content()

        # _do_get - clean up leftover files from _do_write tests
        self._clean_tmpdir()
        self._test_read_missing_file_returns_none()
        self._test_read_with_orphan_tmp_returns_none()

        # _do_scan - clean up leftover files from _do_get tests
        self._clean_tmpdir()
        self._test_scan_finds_vmmeta_files()
        self._clean_tmpdir()
        self._test_scan_multiple_files()
        self._clean_tmpdir()
        self._test_scan_ignores_non_uuid_filenames()
        self._clean_tmpdir()
        self._test_scan_ignores_unrelated_files()
        self._clean_tmpdir()
        self._test_scan_tmp_only_entry_marked_incomplete()
        self._clean_tmpdir()
        self._test_scan_tmp_ignored_when_final_exists()
        self._clean_tmpdir()
        self._test_scan_reads_summary_sidecar()
        self._clean_tmpdir()
        self._test_scan_tmp_entry_does_not_read_summary()
        self._clean_tmpdir()
        self._test_scan_tolerates_corrupt_summary()
        self._clean_tmpdir()
        self._test_scan_empty_directory()
        self._test_scan_missing_directory()
        self._test_scan_relative_path_returns_empty()
        self._test_scan_none_returns_empty()
        self._clean_tmpdir()
        self._test_scan_populates_last_update_time()

        # _do_cleanup - clean up before cleanup tests
        self._clean_tmpdir()
        self._test_cleanup_removes_all_related_files()
        self._test_cleanup_only_main_file()
        self._test_cleanup_main_plus_summary()
        self._test_cleanup_nonexistent_is_noop()
        self._test_cleanup_raises_if_main_file_cannot_be_removed()
        self._test_cleanup_tolerates_sidecar_removal_failure()
        self._test_write_cleanup_read_returns_none()
        self._test_cleanup_does_not_remove_parent_directory()
