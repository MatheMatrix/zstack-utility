# coding=utf-8
from kvmagent.test.shareblock_testsuite.shared_block_plugin_teststub import SharedBlockPluginTestStub
from kvmagent.test.utils import sharedblock_utils,pytest_utils,storage_device_utils
from zstacklib.utils import bash, lvm, jsonobject, sanlock, linux
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
        ver = lvm.get_sanlock_patch_version()
        if not (ver and ver.isdigit()) or int(ver) < 7:
            # current sanlock version not support autoRepair
            return

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

        self.lvlk_repair_test()
        self.vglk_repair_test()
        self.lockspace_repair_test()
        self.gllk_repair_test()


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
            bash.bash_errorout("lvmlockctl -r {0}".format(vgUuid))
            self.corrupt_data(vgUuid, 0, length=1048576)
            self.corrupt_data(vgUuid, 65*1024**2, length=1048576)
            if i == 9:
                bash.bash_r("sanlock direct init -s lvm_{0}:1:/dev/mapper/{0}-lvmlock:0".format(vgUuid))
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