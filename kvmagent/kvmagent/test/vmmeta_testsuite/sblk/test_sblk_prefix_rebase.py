import threading
import uuid as uuid_mod

from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import pytest_utils, storage_device_utils
from zstacklib.utils import bash, lvm, linux
from zstacklib.utils.lv_metadata import sblk_prefix_rebase_backing_files
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

LV_SIZE = 64 * 1024 * 1024  # 64MB for qcow2 images


def _normalize_path(p):
    """Convert sharedblock:/ scheme to /dev/ path."""
    if p.startswith('sharedblock:/'):
        return p.replace('sharedblock:/', '/dev/', 1)
    return p


def _create_qcow2_on_lv(lv_path, backing=None):
    """Create qcow2 image on an LV."""
    with lvm.OperateLv(lv_path, shared=False):
        if backing:
            bash.bash_errorout(
                'qemu-img create -f qcow2 -b %s -F qcow2 %s'
                % (backing, lv_path))
        else:
            bash.bash_errorout(
                'qemu-img create -f qcow2 %s 32M' % lv_path)


def _get_backing(lv_path):
    """Read backing file from qcow2 image on LV."""
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


class TestVmmetaPrefixRebase(TestCase, SharedBlockPluginTestStub):

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

    def _test_empty_prefix_raises(self):
        with self.assertRaisesRegexp(Exception, 'oldPrefix must not be empty'):
            sblk_prefix_rebase_backing_files(
                [], '', '/dev/new/', _normalize_path, lvm)

    def _test_no_backing_returns_zero(self):
        tid = uuid_mod.uuid4().hex[:8]
        vol_lv = _create_lv('pr_nobk_%s' % tid)
        try:
            _create_qcow2_on_lv(vol_lv)
            count = sblk_prefix_rebase_backing_files(
                [vol_lv], '/dev/some_old_vg', '/dev/%s' % vgUuid,
                _normalize_path, lvm)
            self.assertEqual(count, 0)
        finally:
            _delete_lv(vol_lv)

    def _test_no_matching_prefix_returns_zero(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = _create_lv('pr_base_%s' % tid)
        vol_lv = _create_lv('pr_vol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            backing_before = _get_backing(vol_lv)
            self.assertEqual(backing_before, base_lv)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/nonexistent_old_vg',
                '/dev/nonexistent_new_vg',
                _normalize_path, lvm)

            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_sharedblock_scheme_normalized(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = _create_lv('pr_sbase_%s' % tid)
        vol_lv = _create_lv('pr_svol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            sblk_vol = 'sharedblock:/%s/pr_svol_%s' % (vgUuid, tid)

            count = sblk_prefix_rebase_backing_files(
                [sblk_vol],
                'sharedblock:/%s' % vgUuid,
                'sharedblock:/%s' % vgUuid,
                _normalize_path, lvm)

            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_new_backing_missing_skips(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = _create_lv('pr_miss_base_%s' % tid)
        vol_lv = _create_lv('pr_miss_vol_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/%s' % vgUuid,
                '/dev/nonexistent_new_vg',
                _normalize_path, lvm)
            self.assertEqual(count, 0)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_empty_file_paths(self):
        count = sblk_prefix_rebase_backing_files(
            [], '/dev/old', '/dev/new',
            _normalize_path, lvm)
        self.assertEqual(count, 0)

    def _test_multi_level_chain(self):
        tid = uuid_mod.uuid4().hex[:8]
        base_lv = _create_lv('pr_cbase_%s' % tid)
        snap_lv = _create_lv('pr_csnap_%s' % tid)
        vol_lv = _create_lv('pr_chvl_%s' % tid)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(snap_lv, backing=base_lv)
            _create_qcow2_on_lv(vol_lv, backing=snap_lv)

            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)
            self.assertFalse(_get_backing(base_lv))

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/nonexistent_vg',
                '/dev/%s' % vgUuid,
                _normalize_path, lvm)

            self.assertEqual(count, 0)
            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(snap_lv)
            _delete_lv(base_lv)

    def _test_concurrent_no_deadlock(self):
        tid = uuid_mod.uuid4().hex[:8]
        num_vols = 3
        base_lvs = [_create_lv('pr_ccbase_%s_%d' % (tid, i)) for i in range(num_vols)]
        vol_lvs = [_create_lv('pr_ccvl_%s_%d' % (tid, i)) for i in range(num_vols)]
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
                        _normalize_path, lvm)
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

    def _test_single_rebase_success(self):
        """vol backs to /dev/<fake_vg>/base, rebase to /dev/<real_vg>/base => count=1."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        base_name = 'pr_pbase_%s' % tid
        vol_name = 'pr_pvol_%s' % tid

        base_lv = _create_lv(base_name)
        vol_lv = _create_lv(vol_name)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(vol_lv, backing=base_lv)

            # Force vol's backing to point to a fake old VG path
            fake_backing = '/dev/%s/%s' % (fake_vg, base_name)
            _force_backing(vol_lv, fake_backing)
            self.assertEqual(_get_backing(vol_lv), fake_backing)

            count = sblk_prefix_rebase_backing_files(
                [vol_lv],
                '/dev/%s' % fake_vg,
                '/dev/%s' % vgUuid,
                _normalize_path, lvm)

            self.assertEqual(count, 1)
            self.assertEqual(_get_backing(vol_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(base_lv)

    def _test_multi_level_rebase_success(self):
        """vol -> snap -> base, all with fake VG backing, rebase => count=2."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        base_name = 'pr_mlbase_%s' % tid
        snap_name = 'pr_mlsnap_%s' % tid
        vol_name = 'pr_mlvol_%s' % tid

        base_lv = _create_lv(base_name)
        snap_lv = _create_lv(snap_name)
        vol_lv = _create_lv(vol_name)
        try:
            _create_qcow2_on_lv(base_lv)
            _create_qcow2_on_lv(snap_lv, backing=base_lv)
            _create_qcow2_on_lv(vol_lv, backing=snap_lv)

            # Force both to use fake VG prefix
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
                _normalize_path, lvm)

            self.assertEqual(count, 2)
            self.assertEqual(_get_backing(vol_lv), snap_lv)
            self.assertEqual(_get_backing(snap_lv), base_lv)
        finally:
            _delete_lv(vol_lv)
            _delete_lv(snap_lv)
            _delete_lv(base_lv)

    def _test_concurrent_positive_rebase(self):
        """Multiple independent volumes each needing rebase, run concurrently."""
        tid = uuid_mod.uuid4().hex[:8]
        fake_vg = 'fakevg_' + tid
        num_vols = 3
        base_names = ['pr_cpbase_%s_%d' % (tid, i) for i in range(num_vols)]
        vol_names = ['pr_cpvol_%s_%d' % (tid, i) for i in range(num_vols)]

        base_lvs = [_create_lv(n) for n in base_names]
        vol_lvs = [_create_lv(n) for n in vol_names]
        try:
            for base in base_lvs:
                _create_qcow2_on_lv(base)
            for i, vol in enumerate(vol_lvs):
                _create_qcow2_on_lv(vol, backing=base_lvs[i])

            # Force all vols to use fake VG backing
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
                        _normalize_path, lvm)
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

    @pytest_utils.ztest_decorater
    def test_sblk_prefix_rebase(self):
        self._connect_vg()

        self._test_empty_prefix_raises()
        self._test_no_backing_returns_zero()
        self._test_no_matching_prefix_returns_zero()
        self._test_sharedblock_scheme_normalized()
        self._test_new_backing_missing_skips()
        self._test_empty_file_paths()
        self._test_multi_level_chain()
        self._test_concurrent_no_deadlock()
        self._test_single_rebase_success()
        self._test_multi_level_rebase_success()
        self._test_concurrent_positive_rebase()
