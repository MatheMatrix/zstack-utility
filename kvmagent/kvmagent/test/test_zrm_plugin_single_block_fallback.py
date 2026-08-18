import unittest

from kvmagent.plugins import zrm_plugin


class TestZrmPluginSingleBlockFallback(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(zrm_plugin.ZrmPlugin)
        self._orig_execute_qmp_command = zrm_plugin.qmp.execute_qmp_command
        self.plugin._get_zrm_block_jobs = lambda vm_uuid: {}
        self.plugin._get_block_device_for_volume_uuid = lambda vm_uuid, volume_uuid: (None, None)
        self.plugin._get_drive_name_from_domain_xml = lambda vm_uuid, volume_uuid: None
        self.plugin._has_dirty_bitmap = lambda vm_uuid, node_name, bitmap_name: False
        self.plugin._add_dirty_bitmap = lambda vm_uuid, node_name, bitmap_name: True

    def tearDown(self):
        zrm_plugin.qmp.execute_qmp_command = self._orig_execute_qmp_command

    def _start_with_blocks(self, blocks, qmp_volume_uuids=None):
        calls = []
        self.plugin._query_blocks_for_vm = lambda vm_uuid: blocks

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=False, **kwargs):
            calls.append({
                "vm_uuid": vm_uuid,
                "command": command,
                "raise_exception": raise_exception,
                "kwargs": kwargs
            })
            return None

        zrm_plugin.qmp.execute_qmp_command = fake_execute_qmp_command
        error = self.plugin._start_mirrors_for_zr(
            "vm-recovered", ["volume-inventory-uuid"], "nbd://172.26.53.108:10809",
            qmp_volume_uuids=qmp_volume_uuids)
        return error, calls

    def test_starts_mirror_only_when_explicit_qmp_volume_mapping_matches_block(self):
        source_volume_uuid = "2cb6ef5d6a844883ba1f9ec1c545fccb"
        recovery_volume_uuid = "a69cd13f75bf4eb4018587d2b9a62b77"
        calls = []
        self.plugin._query_blocks_for_vm = lambda vm_uuid: [{
            "device": "",
            "qdev": "/machine/peripheral/virtio-disk0/virtio-backend",
            "removable": False,
            "file": "/vms_ds/rootVolumes/acct/vol-%s/%s.qcow2" % (
                source_volume_uuid, source_volume_uuid),
            "node": "libvirt-1-format"
        }]

        def fake_execute_qmp_command(vm_uuid, command, raise_exception=False, **kwargs):
            calls.append({
                "vm_uuid": vm_uuid,
                "command": command,
                "raise_exception": raise_exception,
                "kwargs": kwargs
            })
            return None

        zrm_plugin.qmp.execute_qmp_command = fake_execute_qmp_command
        error = self.plugin._start_mirrors_for_zr(
            "vm-recovered", [recovery_volume_uuid], "nbd://172.26.53.108:10809",
            qmp_volume_uuids={recovery_volume_uuid: source_volume_uuid})

        self.assertIsNone(error)
        mirror = [call for call in calls if call["command"] == "drive-mirror"]
        self.assertEqual(1, len(mirror))
        self.assertEqual("libvirt-1-format", mirror[0]["kwargs"]["device"])
        self.assertTrue(mirror[0]["kwargs"]["target"].endswith(
            "/vol-" + recovery_volume_uuid))

    def test_does_not_start_mirror_from_single_nonremovable_block_without_volume_uuid(self):
        error, calls = self._start_with_blocks([{
            "device": "",
            "qdev": "/machine/peripheral/virtio-disk0/virtio-backend",
            "removable": False,
            "file": "/vms_ds/rootVolumes/recovered/root.qcow2",
            "node": "libvirt-1-format"
        }])

        self.assertIn("no block device found", error)
        self.assertEqual([], calls)

    def test_does_not_guess_when_more_than_one_nonremovable_block_exists(self):
        error, calls = self._start_with_blocks([
            {
                "device": "",
                "qdev": "/machine/peripheral/virtio-disk0/virtio-backend",
                "removable": False,
                "file": "/vms_ds/rootVolumes/recovered/root.qcow2",
                "node": "libvirt-1-format"
            },
            {
                "device": "",
                "qdev": "/machine/peripheral/virtio-disk1/virtio-backend",
                "removable": False,
                "file": "/vms_ds/dataVolumes/recovered/data.qcow2",
                "node": "libvirt-2-format"
            }
        ])

        self.assertIn("no block device found", error)
        self.assertEqual([], calls)


if __name__ == '__main__':
    unittest.main()
