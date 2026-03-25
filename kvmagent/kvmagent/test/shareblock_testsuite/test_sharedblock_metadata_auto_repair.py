# coding=utf-8
from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import sharedblock_utils,pytest_utils,storage_device_utils
from zstacklib.utils import bash, lvm, jsonobject, sanlock, linux, log
from unittest import TestCase
from zstacklib.test.utils import misc,env
import os

storage_device_utils.init_storagedevice_plugin()

PKG_NAME = __name__

# must create iSCSI stroage before run test
__ENV_SETUP__ = {
    'self': {
        'xml':'http://smb.zstack.io/mirror/ztest/xml/twoDiskVm.xml',
        'init':['bash ./createiSCSIStroage.sh']
    }
}

logger = log.get_logger(__name__)
hostUuid = "8b12f74e6a834c5fa90304b8ea54b1dd"
hostId = 24
vgUuid = "36b02490bb944233b0b01990a450ba83"
blockUuids = []

## describe: case will manage by ztest
class TestSharedBlockPlugin(TestCase, SharedBlockPluginTestStub):
    @classmethod
    def setUpClass(cls):
        pass

    def corrupt_data(self, vg, offset, length=512):
        fd = os.open("/dev/mapper/%s-lvmlock" % vg, os.O_RDWR)
        try:
            os.lseek(fd, offset, os.SEEK_SET)
            random_data = os.urandom(length)
            os.write(fd, random_data)
            os.fsync(fd)
        finally:
            os.close(fd)

    @pytest_utils.ztest_decorater
    def test_sharedblock_metadata_auto_repair(self):
        self_vm = env.get_vm_metadata('self')
        rsp = storage_device_utils.iscsi_login(
            self_vm.ip,"3260"
        )
        self.assertEqual(rsp.success, True, rsp.error)

        r, o = bash.bash_ro("ls /dev/disk/by-id | grep scsi-3 | awk -F '-' '{print $2}'")
        blockUuids.extend(o.strip().splitlines())

        rsp = self.connect(blockUuids[0 : 1], blockUuids, vgUuid, hostUuid, hostId, forceWipe=True)
        self.assertEqual(True, rsp.success, rsp.error)
        o = bash.bash_o("vgs")
        self.assertEqual(True, rsp.success, o)

        self.lvm_repair_cmd_test()

        ver = lvm.get_sanlock_patch_version()
        if not (ver and ver.isdigit()) or int(ver) < 7:
            # current sanlock version not support autoRepair
            return

        self.lvlk_repair_test()
        self.vglk_repair_test()
        self.lockspace_repair_test()
        self.gllk_repair_test()

    def lvm_repair_cmd_test(self):
        test_lv = "/dev/{}/testlv".format(vgUuid)
        lvm.create_lv_from_absolute_path("/dev/{}/testlv".format(vgUuid), 4194304, exact_size=True)
        lvm.active_lv_with_check(test_lv, shared=True)
        lvm.active_lv(test_lv, shared=False)
        lvm.extend_lv(test_lv, 20971520, lockopts=["shupdate", "norefresh"])
        lvm.lv_rename(test_lv, "/dev/{}/testlv-new".format(vgUuid))
        test_lv = "/dev/{}/testlv-new".format(vgUuid)
        lvm.deactive_lv(test_lv)
        lvm.delete_lv(test_lv)

    def lvlk_repair_test(self):
        volume_uuid = misc.uuid()
        volume_path = "sharedblock://{}/{}".format(vgUuid, volume_uuid)
        abs_path = "/dev/{}/{}".format(vgUuid, volume_uuid)
        rsp = sharedblock_utils.shareblock_create_empty_volume(
            installPath=volume_path,
            volumeUuid=volume_uuid,
            size=1048576,
            hostUuid=hostUuid,
            vgUuid=vgUuid
        )
        self.assertEqual(True, rsp.success, rsp.error)

        start = int(lvm.get_lv_attr(abs_path, "lv_lockargs").get("lv_lockargs").split(":")[-1])
        # corrupt the first 50 and last 50 sectors
        for i in list(range(0, 50)) + list(range(1998, 2048)):
            lock_offset = start + 512 * i
            self.corrupt_data(vgUuid, lock_offset, length=512)

            rsp = sharedblock_utils.sharedblock_active_lv(
                installPath=volume_path,
                vgUuid=vgUuid,
                lockType=1
            )
            self.assertEqual(True, rsp.success, "lvUuid %s offset %s err %s" % (volume_uuid, lock_offset, rsp.error))

            self.corrupt_data(vgUuid, lock_offset, length=512)
            rsp = sharedblock_utils.sharedblock_active_lv(
                installPath=volume_path,
                vgUuid=vgUuid,
                lockType=2
            )
            self.assertEqual(True, rsp.success, "lvUuid %s offset %s err %s" % (volume_uuid, lock_offset, rsp.error))

            self.corrupt_data(vgUuid, lock_offset, length=512)
            rsp = sharedblock_utils.sharedblock_active_lv(
                installPath=volume_path,
                vgUuid=vgUuid,
                lockType=0
            )
            self.assertEqual(True, rsp.success, "lvUuid %s offset %s err %s" % (volume_uuid, lock_offset, rsp.error))


    def vglk_repair_test(self):
        offset = 66*1024**2
        for i in list(range(0, 50)) + list(range(1998, 2048)):
            lock_offset = offset + 512 * i

            self.corrupt_data(vgUuid, lock_offset, length=512)
            rsp = sharedblock_utils.sharedblock_ping(vgUuid)
            self.assertEqual(rsp.success, True, rsp.error)

            r, o, e = bash.bash_roe("lvcreate --wipesignatures y -y --size 4M --name test_lv %s" % vgUuid)
            self.assertEqual(True, r == 0, "lvcreate failed: %s uuid %s offset %s" % (str(o)+str(e), "VGLK", lock_offset))

            self.corrupt_data(vgUuid, lock_offset, length=512)
            rsp = sharedblock_utils.sharedblock_ping(vgUuid)
            self.assertEqual(rsp.success, True, rsp.error)

            r, o, e = bash.bash_roe("lvremove -y /dev/%s/test_lv" % vgUuid)
            self.assertEqual(True, r == 0, "lvremove failed: %s uuid %s offset %s" % (str(o)+str(e), "VGLK", lock_offset))

    def wait_lockspace_stop(self):
        def _wait(_):
            return bash.bash_r("lvmlockctl -i -d | grep lvm_%s" % vgUuid) != 0
        linux.wait_callback_success(_wait, timeout=10, interval=0.5)

    def lockspace_repair_test(self):
        volume_uuid = misc.uuid()
        volume_path = "sharedblock://{}/{}".format(vgUuid, volume_uuid)
        rsp = sharedblock_utils.shareblock_create_empty_volume(
            installPath=volume_path,
            volumeUuid=volume_uuid,
            size=1048576,
            hostUuid=hostUuid,
            vgUuid=vgUuid
        )
        self.assertEqual(True, rsp.success, rsp.error)
        for i in range(10):
            self.corrupt_data(vgUuid, 0, length=1048576)
            self.corrupt_data(vgUuid, 65*1024**2, length=1048576)
            bash.bash_o("vgchange -an {0} && vgchange --lockstop {0}".format(vgUuid))
            bash.bash_o("lvmlockctl -r {0}".format(vgUuid))
            if i == 9:
                bash.bash_r("sanlock direct init -s lvm_{0}:1:/dev/mapper/{0}-lvmlock:0".format(vgUuid))

            self.wait_lockspace_stop()
            rsp = self.connect(blockUuids[0 : 1], blockUuids, vgUuid, hostUuid, 1, forceWipe=False)
            self.assertEqual(True, rsp.success, "lockspace %s hostId %s err %s" % (vgUuid, 1, rsp.error))

            rsp = sharedblock_utils.sharedblock_active_lv(
                installPath=volume_path,
                vgUuid=vgUuid,
                lockType=2
            )
            self.assertEqual(True, rsp.success, rsp.error)


    def gllk_repair_test(self):
        offset = 65*1024**2
        self.corrupt_data(vgUuid, offset, length=1048576)
        lvm.fix_global_lock()
        r, o = bash.bash_ro("vgs 2>&1")
        self.assertEqual(False, "global lock" in o, str(o))

        bash.bash_r("lvmlockctl -D %s" % vgUuid)
        self.corrupt_data(vgUuid, offset, length=1048576)
        lvm.fix_global_lock()
        r, o = bash.bash_ro("vgs 2>&1")
        self.assertEqual(False, "global lock" in o, str(o))