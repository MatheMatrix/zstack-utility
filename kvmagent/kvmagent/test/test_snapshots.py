from kvmagent.test.utils import vm_utils, network_utils, pytest_utils
from kvmagent.test.utils.stub import *
from zstacklib.test.utils import env, misc
from zstacklib.utils import uuidhelper
from kvmagent.plugins import vm_plugin
from unittest import TestCase
import mock
import libvirt

init_kvmagent()
vm_utils.init_vm_plugin()


__ENV_SETUP__ = {
    'self': {}
}


class TestSnapshots(TestCase, vm_utils.VmPluginTestStub):
    @classmethod
    def setUpClass(cls):
        network_utils.create_default_bridge_if_not_exist()

    @misc.test_for(handlers=[
        vm_plugin.VmPlugin.KVM_TAKE_VOLUME_SNAPSHOT_PATH,
        vm_plugin.VmPlugin.KVM_MERGE_SNAPSHOT_PATH,
    ])
    @pytest_utils.ztest_decorater
    def test_snapshot_operations(self):
        vm_uuid, vm = self._create_vm()

        xml = vm_utils.get_vm_xmlobject_from_virsh_dump(vm_uuid)
        disk = xml.devices.disk[0]

        vol_path = disk.source.file_
        vol_uuid = os.path.basename(vol_path).split('.')[0]
        snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())

        vm_utils.take_snapshot(vm_uuid, vol_uuid, vol_path, snapshot_path)
        self.assertTrue(os.path.isfile(snapshot_path))

        new_vol_path = snapshot_path
        new_snapshot_path = vol_path

        rsp = vm_utils.merge_snapshots(vm_uuid, new_vol_path, new_snapshot_path)
        self.assertFalse(rsp.success)
        # merge will not delete the snapshot
        self.assertTrue(os.path.isfile(new_snapshot_path))

        self._destroy_vm(vm_uuid)


    @pytest_utils.ztest_decorater
    def test_memory_snapshot_operations(self):
        vm_uuid, vm = self._create_vm()

        xml = vm_utils.get_vm_xmlobject_from_virsh_dump(vm_uuid)
        disk = xml.devices.disk[0]

        vol_path = disk.source.file_
        vol_uuid = os.path.basename(vol_path).split('.')[0]

        snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())

        boot_disk_struct = {
            "volumeUuid": vol_uuid,
            "installPath": snapshot_path,
            "vmInstanceUuid": vm_uuid,
            "previousInstallPath": vol_path,
            "newVolumeInstallPath": snapshot_path,
            "snapshotUuid": uuidhelper.uuid(),
            "volume": {
                "installPath": vol_path,
                "deviceType": "file"
            },
            "memory": False,
            "live": True,
            "full": False,
        }

        memory_snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())
        memory_disk_struct = {
            "volumeUuid": uuidhelper.uuid(),
            "installPath": memory_snapshot_path,
            "vmInstanceUuid": vm_uuid,
            "previousInstallPath": memory_snapshot_path,
            "newVolumeInstallPath": memory_snapshot_path,
            "snapshotUuid": uuidhelper.uuid(),
            "volume": {
                "installPath": memory_snapshot_path
            },
            "memory": True,
            "live": True,
            "full": False,
        }

        vm_utils.take_volumes_snapshots(vm_uuid, [boot_disk_struct, memory_disk_struct])
        self.assertTrue(os.path.isfile(snapshot_path))
        self.assertTrue(os.path.isfile(memory_snapshot_path))

        self._destroy_vm(vm_uuid)


    @pytest_utils.ztest_decorater
    def test_memory_snapshot_rollback(self):
        vm_uuid, vm = self._create_vm()

        original_create_xml = libvirt.virDomain.snapshotCreateXML
        original_rollback_memory_snapshot = vm_plugin.Vm.rollback_memory_snapshot
        libvirt.virDomain.snapshotCreateXML = mock.Mock(side_effect=Exception('on purpose'))

        vm_plugin.Vm.rollback_memory_snapshot = mock.Mock()

        xml = vm_utils.get_vm_xmlobject_from_virsh_dump(vm_uuid)
        disk = xml.devices.disk[0]

        vol_path = disk.source.file_
        vol_uuid = os.path.basename(vol_path).split('.')[0]

        snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())

        boot_disk_struct = {
            "volumeUuid": vol_uuid,
            "installPath": snapshot_path,
            "vmInstanceUuid": vm_uuid,
            "previousInstallPath": vol_path,
            "newVolumeInstallPath": snapshot_path,
            "snapshotUuid": uuidhelper.uuid(),
            "volume": {
                "installPath": vol_path,
                "deviceType": "file"
            },
            "memory": False,
            "live": True,
            "full": False,
        }

        memory_snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())
        memory_disk_struct = {
            "volumeUuid": uuidhelper.uuid(),
            "installPath": memory_snapshot_path,
            "vmInstanceUuid": vm_uuid,
            "previousInstallPath": memory_snapshot_path,
            "newVolumeInstallPath": memory_snapshot_path,
            "snapshotUuid": uuidhelper.uuid(),
            "volume": {
                "installPath": memory_snapshot_path
            },
            "memory": True,
            "live": True,
            "full": False,
        }

        try:
            try:
                vm_utils.take_volumes_snapshots(vm_uuid, [boot_disk_struct, memory_disk_struct])
            except Exception as e:
                pass

            self.assertFalse(os.path.isfile(snapshot_path))
            self.assertFalse(os.path.isfile(memory_snapshot_path))
            vm_plugin.Vm.rollback_memory_snapshot.assert_called_with(memory_snapshot_path)
        finally:
            libvirt.virDomain.snapshotCreateXML = original_create_xml
            vm_plugin.Vm.rollback_memory_snapshot = original_rollback_memory_snapshot
            self._destroy_vm(vm_uuid)


    def test_rollback_memory_snapshot_cleans_mount_path_after_umount(self):
        vm = vm_plugin.Vm.__new__(vm_plugin.Vm)
        vm.uuid = uuidhelper.uuid()

        original_umount = vm_plugin.linux.umount
        original_is_mounted = vm_plugin.linux.is_mounted
        original_rmdir_if_empty = vm_plugin.linux.rmdir_if_empty
        original_deactive_lv = vm_plugin.lvm.deactive_lv

        vm_plugin.linux.umount = mock.Mock(return_value=0)
        vm_plugin.linux.is_mounted = mock.Mock(return_value=False)
        vm_plugin.linux.rmdir_if_empty = mock.Mock()
        vm_plugin.lvm.deactive_lv = mock.Mock()

        try:
            vm.rollback_memory_snapshot('/dev/vg/lv')

            vm_plugin.linux.umount.assert_called_with('/tmp/vg/lv')
            vm_plugin.linux.is_mounted.assert_called_with('/tmp/vg/lv')
            vm_plugin.linux.rmdir_if_empty.assert_called_with('/tmp/vg/lv')
            vm_plugin.lvm.deactive_lv.assert_called_with('/dev/vg/lv')
        finally:
            vm_plugin.linux.umount = original_umount
            vm_plugin.linux.is_mounted = original_is_mounted
            vm_plugin.linux.rmdir_if_empty = original_rmdir_if_empty
            vm_plugin.lvm.deactive_lv = original_deactive_lv
