from kvmagent.test.utils import vm_utils, network_utils, pytest_utils
from kvmagent.test.utils.stub import *
from zstacklib.test.utils import env, misc
from zstacklib.utils import uuidhelper, xmlobject
from kvmagent.plugins import vm_plugin
from unittest import TestCase
import mock
import libvirt
from kvmagent.plugins.vm_plugin import VolumeSnapshotJobStruct, VolumeSnapshotResultStruct

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
        libvirt.virDomain.snapshotCreateXML = mock.Mock(side_effect=Exception('on purpose'))

        vm_plugin.Vm.rollback_memory_snapshot = mock.Mock()

        vs_structs = self._get_vm_volume_snapshots_json(vm_uuid)

        try:
            vm_utils.take_volumes_snapshots(vm_uuid, vs_structs)
        except Exception as e:
            pass

        self.assertFalse(os.path.isfile(vs_structs[0]['installPath']))
        self.assertFalse(os.path.isfile(vs_structs[1]['installPath']))
        vm_plugin.Vm.rollback_memory_snapshot.assert_called_with(vs_structs[1]['installPath'])

        libvirt.virDomain.snapshotCreateXML = original_create_xml

        self._destroy_vm(vm_uuid)

    def _get_vm_volume_snapshots_json(self, vm_uuid):
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

        return [boot_disk_struct, memory_disk_struct]

    def _get_vm_volume_snapshots_structs(self, vm_uuid):
        xml = vm_utils.get_vm_xmlobject_from_virsh_dump(vm_uuid)
        disk = xml.devices.disk[0]

        vol_path = disk.source.file_
        vol_uuid = os.path.basename(vol_path).split('.')[0]

        snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())

        volume = vm_plugin.VolumeTO()
        volume.deviceType = 'file'
        volume.installPath = vol_path
        boot_disk_struct = vm_plugin.VolumeSnapshotJobStruct(volumeUuid=vol_uuid,
                                                                live=True,
                                                                full=False,
                                                                memory=False,
                                                                volume=volume,
                                                                installPath=snapshot_path,
                                                                newVolumeInstallPath=snapshot_path,
                                                                previousInstallPath=vol_path,
                                                                vmInstanceUuid=vm_uuid)
        boot_disk_struct.installPath = snapshot_path

        memory_snapshot_path = os.path.join(env.SNAPSHOT_DIR, '%s.qcow2' % uuidhelper.uuid())
        volume = vm_plugin.VolumeTO()
        volume.installPath = memory_snapshot_path
        # volumeUuid, volume, installPath, vmInstanceUuid, previousInstallPath,
        #         newVolumeInstallPath, live=True, full=False, memory=False
        memory_disk_struct = vm_plugin.VolumeSnapshotJobStruct(volumeUuid=uuidhelper.uuid(),
                                                                live=True,
                                                                full=False,
                                                                memory=True,
                                                                volume=volume,
                                                                installPath=memory_snapshot_path,
                                                                newVolumeInstallPath=memory_snapshot_path,
                                                                previousInstallPath=memory_snapshot_path,
                                                                vmInstanceUuid=vm_uuid)
        return [boot_disk_struct, memory_disk_struct]

    @pytest_utils.ztest_decorater
    def test_before_take_live_volumes_delta_snapshots(self):
        vm_uuid, vm = self._create_vm()
        vs_structs = self._get_vm_volume_snapshots_structs(vm_uuid)

        vm = vm_plugin.get_vm_by_uuid(vm_uuid)
        disks, disk_names, return_structs, memory_snapshot_struct, snapshot = vm.before_take_live_volumes_delta_snapshots(vs_structs)

        # Assertions for disks
        self.assertIsNotNone(disks)
        self.assertEqual(len(disks), 1)
        self.assertEqual(disks[0].tag, 'disk', 'disks tag is not disks %s' % disks[0].tag)

        # Assertions for disk_names
        self.assertIsNotNone(disk_names)
        self.assertEqual(len(disk_names), 1)
        self.assertIn('vda', disk_names)

        # Assertions for return_structs
        self.assertIsNotNone(return_structs)
        self.assertEqual(len(return_structs), 1)
        self.assertIsInstance(return_structs[0], VolumeSnapshotResultStruct)

        # Assertions for memory_snapshot_struct
        self.assertIsNotNone(memory_snapshot_struct)
        self.assertIsInstance(memory_snapshot_struct, VolumeSnapshotJobStruct)
        self.assertTrue(memory_snapshot_struct.memory)

        # Assertions for snapshot
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.tag, 'domainsnapshot')

        self._destroy_vm(vm_uuid)
