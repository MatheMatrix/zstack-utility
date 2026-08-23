import unittest

from kvmagent.plugins import vm_plugin


class TestVmPluginBlockGraphFallback(unittest.TestCase):
    def setUp(self):
        self._orig_execute_qmp_command = vm_plugin.qmp.execute_qmp_command
        self._orig_block_graph_capability = dict(vm_plugin._BLOCK_GRAPH_CAPABILITY)
        vm_plugin._BLOCK_GRAPH_CAPABILITY.clear()

    def tearDown(self):
        vm_plugin.qmp.execute_qmp_command = self._orig_execute_qmp_command
        vm_plugin._BLOCK_GRAPH_CAPABILITY.clear()
        vm_plugin._BLOCK_GRAPH_CAPABILITY.update(
            self._orig_block_graph_capability)

    def test_query_block_match_is_used_when_block_graph_unavailable(self):
        calls = []

        def fake_execute_qmp_command(vm_uuid, command,
                                     raise_exception=False, **kwargs):
            calls.append(command)
            if command == "query-block":
                return [{
                    "device": "drive-virtio-disk0",
                    "inserted": {
                        "node-name": "drive-node0",
                        "file": (
                            "/var/lib/zstack/volumes/"
                            "volume-vol-old-qemu.qcow2")
                    }
                }]
            if command == "x-debug-query-block-graph":
                return None
            return None

        vm_plugin.qmp.execute_qmp_command = fake_execute_qmp_command

        node_name, device_name = vm_plugin.get_mirror_device_for_volume_uuid(
            "vm-qemu-old", "vol-old-qemu")

        self.assertEqual("drive-node0", node_name)
        self.assertEqual("drive-virtio-disk0", device_name)
        self.assertEqual(
            False, vm_plugin._BLOCK_GRAPH_CAPABILITY.get("vm-qemu-old"))
        self.assertEqual(
            ["query-block", "x-debug-query-block-graph"], calls)


if __name__ == "__main__":
    unittest.main()
