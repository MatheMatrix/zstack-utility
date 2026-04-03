import os
import shutil
import tempfile
from unittest import TestCase

from kvmagent.test.utils import pytest_utils
from kvmagent.test.utils.stub import *

from zstacklib.utils import bash, linux
from zstacklib.utils.file_metadata_handler import (
    qcow2_prefix_rebase_backing_files,
    _is_imagecache_path,
    _get_rebase_lock_path,
)

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {}
}


def _qemu_img_create(path, size='64M', backing=None, fmt='qcow2'):
    """Create a qcow2 file, optionally with a backing file."""
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    if backing:
        bash.bash_errorout('qemu-img create -f %s -b %s -F qcow2 %s' % (fmt, backing, path))
    else:
        bash.bash_errorout('qemu-img create -f %s %s %s' % (fmt, path, size))


def _get_backing(path):
    """Read the backing file path from a qcow2 image."""
    return linux.qcow2_get_backing_file(path)


class TestFilePrefixRebase(TestCase):
    """_is_imagecache_path, _get_rebase_lock_path, and
    qcow2_prefix_rebase_backing_files with real qcow2 files."""

    @classmethod
    def setUpClass(cls):
        return

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='vmmeta_rebase_')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _clean_tmpdir(self):
        for root, dirs, files in os.walk(self.tmpdir, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    os.remove(fp)
                except OSError:
                    pass
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    os.rmdir(dp)
                except OSError:
                    pass

    # -- helper sub-tests --------------------------------------------------

    def _test_is_imagecache_path_positive(self):
        self.assertTrue(_is_imagecache_path(
            '/opt/zstack/nfs/prim-uuid/imagecache/template/img-uuid/img-uuid.qcow2'))

    def _test_is_imagecache_path_negative(self):
        self.assertFalse(_is_imagecache_path(
            '/opt/zstack/nfs/prim-uuid/rootVolumes/vol-uuid/vol-uuid.qcow2'))

    def _test_get_rebase_lock_path(self):
        self.assertEqual(
            _get_rebase_lock_path('/a/imagecache/template/uuid/uuid.qcow2'),
            '/a/imagecache/template/uuid/uuid.vmmeta-lck')

    def _test_get_rebase_lock_path_no_extension(self):
        self.assertEqual(
            _get_rebase_lock_path('/a/imagecache/img'),
            '/a/imagecache/img.vmmeta-lck')

    # -- rebase sub-tests --------------------------------------------------

    def _test_empty_old_prefix_raises(self):
        vol = os.path.join(self.tmpdir, 'vol.qcow2')
        _qemu_img_create(vol, '64M')
        with self.assertRaisesRegexp(Exception, 'old_prefix must not be empty'):
            qcow2_prefix_rebase_backing_files([vol], '', '/new/')

    def _test_empty_new_prefix_raises(self):
        vol = os.path.join(self.tmpdir, 'vol.qcow2')
        _qemu_img_create(vol, '64M')
        with self.assertRaisesRegexp(Exception, 'new_prefix must not be empty'):
            qcow2_prefix_rebase_backing_files([vol], '/old/', '')

    def _test_no_backing_returns_zero(self):
        vol = os.path.join(self.tmpdir, 'vol.qcow2')
        _qemu_img_create(vol, '64M')
        count = qcow2_prefix_rebase_backing_files([vol], '/old', '/new')
        self.assertEqual(count, 0)

    def _test_single_file_single_backing_rebase(self):
        """vol.qcow2 -> /old/base.qcow2  =>  rebase to /new/base.qcow2"""
        old_base = os.path.join(self.tmpdir, 'old', 'base.qcow2')
        new_base = os.path.join(self.tmpdir, 'new', 'base.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_base, '64M')
        os.makedirs(os.path.dirname(new_base))
        shutil.copy2(old_base, new_base)
        _qemu_img_create(vol, backing=old_base)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)

        self.assertEqual(count, 1)
        self.assertEqual(_get_backing(vol), new_base)

    def _test_multi_level_chain(self):
        """vol -> /old/snap -> /old/base   all get rebased."""
        old_dir = os.path.join(self.tmpdir, 'old', 'rootVolumes')
        new_dir = os.path.join(self.tmpdir, 'new', 'rootVolumes')
        old_base = os.path.join(old_dir, 'base.qcow2')
        old_snap = os.path.join(old_dir, 'snap.qcow2')
        new_base = os.path.join(new_dir, 'base.qcow2')
        new_snap = os.path.join(new_dir, 'snap.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_base, '64M')
        _qemu_img_create(old_snap, backing=old_base)
        os.makedirs(new_dir)
        shutil.copy2(old_base, new_base)
        shutil.copy2(old_snap, new_snap)   # preserve old backing ref in qcow2 header
        _qemu_img_create(vol, backing=old_snap)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)

        self.assertEqual(count, 2)
        self.assertEqual(_get_backing(vol), new_snap)
        self.assertEqual(_get_backing(new_snap), new_base)

    def _test_imagecache_backing_acquires_flock(self):
        """Backing in /imagecache/ triggers flock -- lock file should be created."""
        img_uuid = 'a' * 32
        old_cache = os.path.join(self.tmpdir, 'old', 'imagecache', 'template', img_uuid,
                                 img_uuid + '.qcow2')
        new_cache = os.path.join(self.tmpdir, 'new', 'imagecache', 'template', img_uuid,
                                 img_uuid + '.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_cache, '64M')
        os.makedirs(os.path.dirname(new_cache))
        shutil.copy2(old_cache, new_cache)
        _qemu_img_create(vol, backing=old_cache)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)

        self.assertEqual(count, 1)
        self.assertEqual(_get_backing(vol), new_cache)
        lock_path = os.path.splitext(new_cache)[0] + '.vmmeta-lck'
        self.assertTrue(os.path.exists(lock_path),
                        "lock file %s should exist after rebase" % lock_path)

    def _test_no_imagecache_no_locks(self):
        """No /imagecache/ in path -> no flock at all."""
        old_base = os.path.join(self.tmpdir, 'old', 'rootVolumes', 'base.qcow2')
        new_base = os.path.join(self.tmpdir, 'new', 'rootVolumes', 'base.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_base, '64M')
        os.makedirs(os.path.dirname(new_base))
        shutil.copy2(old_base, new_base)
        _qemu_img_create(vol, backing=old_base)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)
        self.assertEqual(count, 1)

        # no .vmmeta-lck anywhere
        r, lck_files = bash.bash_ro('find %s -name "*.vmmeta-lck"' % self.tmpdir)
        self.assertEqual(lck_files.strip(), '',
                         "no lock files expected, found: %s" % lck_files)

    def _test_new_backing_missing_skips_chain(self):
        old_base = os.path.join(self.tmpdir, 'old', 'base.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_base, '64M')
        _qemu_img_create(vol, backing=old_base)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)
        self.assertEqual(count, 0)
        self.assertEqual(_get_backing(vol), old_base)

    def _test_backing_outside_old_prefix_not_rebased(self):
        other_base = os.path.join(self.tmpdir, 'other', 'base.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(other_base, '64M')
        _qemu_img_create(vol, backing=other_base)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)
        self.assertEqual(count, 0)

    def _test_multiple_file_paths_independent_chains(self):
        old_a = os.path.join(self.tmpdir, 'old', 'a.qcow2')
        old_b = os.path.join(self.tmpdir, 'old', 'b.qcow2')
        new_a = os.path.join(self.tmpdir, 'new', 'a.qcow2')
        new_b = os.path.join(self.tmpdir, 'new', 'b.qcow2')
        vol_a = os.path.join(self.tmpdir, 'vol-a.qcow2')
        vol_b = os.path.join(self.tmpdir, 'vol-b.qcow2')

        _qemu_img_create(old_a, '64M')
        _qemu_img_create(old_b, '64M')
        os.makedirs(os.path.join(self.tmpdir, 'new'))
        shutil.copy2(old_a, new_a)
        shutil.copy2(old_b, new_b)
        _qemu_img_create(vol_a, backing=old_a)
        _qemu_img_create(vol_b, backing=old_b)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files(
            [vol_a, vol_b], old_prefix, new_prefix)
        self.assertEqual(count, 2)

    def _test_empty_file_paths(self):
        count = qcow2_prefix_rebase_backing_files([], '/old', '/new')
        self.assertEqual(count, 0)

    def _test_missing_new_backing_skips(self):
        """If new_backing doesn't exist, rebase is skipped (count=0)."""
        old_base = os.path.join(self.tmpdir, 'old', 'base.qcow2')
        vol = os.path.join(self.tmpdir, 'vol.qcow2')

        _qemu_img_create(old_base, '64M')
        _qemu_img_create(vol, backing=old_base)

        old_prefix = os.path.join(self.tmpdir, 'old')
        new_prefix = os.path.join(self.tmpdir, 'new')
        count = qcow2_prefix_rebase_backing_files([vol], old_prefix, new_prefix)

        self.assertEqual(count, 0)
        self.assertEqual(_get_backing(vol), old_base)

    # -- single entry point ------------------------------------------------

    @pytest_utils.ztest_decorater
    def test_file_prefix_rebase(self):
        # helper tests
        self._test_is_imagecache_path_positive()
        self._test_is_imagecache_path_negative()
        self._test_get_rebase_lock_path()
        self._test_get_rebase_lock_path_no_extension()

        # rebase tests - clean tmpdir between each to avoid leftover files
        self._test_empty_old_prefix_raises()
        self._clean_tmpdir()
        self._test_empty_new_prefix_raises()
        self._clean_tmpdir()
        self._test_no_backing_returns_zero()
        self._clean_tmpdir()
        self._test_single_file_single_backing_rebase()
        self._clean_tmpdir()
        self._test_multi_level_chain()
        self._clean_tmpdir()
        self._test_imagecache_backing_acquires_flock()
        self._clean_tmpdir()
        self._test_no_imagecache_no_locks()
        self._clean_tmpdir()
        self._test_new_backing_missing_skips_chain()
        self._clean_tmpdir()
        self._test_backing_outside_old_prefix_not_rebased()
        self._clean_tmpdir()
        self._test_multiple_file_paths_independent_chains()
        self._clean_tmpdir()
        self._test_empty_file_paths()
        self._clean_tmpdir()
        self._test_missing_new_backing_skips()
