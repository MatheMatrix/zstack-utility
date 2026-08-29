import sys
import types
import unittest

import mock
from zstacklib import utils as zstack_utils

qemu = types.ModuleType("zstacklib.utils.qemu")
qemu.get_path = lambda: "/usr/bin/qemu-system-x86_64"
sys.modules["zstacklib.utils.qemu"] = qemu
zstack_utils.qemu = qemu

from kvmagent.plugins import shared_block_plugin
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import lvm
from zstacklib.utils import sharedblock_lanfree


class FakeOperateLv(object):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class TestSharedBlockGetVolumeSnapshotLanFreeLayouts(unittest.TestCase):
    def setUp(self):
        self.plugin = shared_block_plugin.SharedBlockPlugin()
        self.recursive = mock.patch.object(
            lvm, "RecursiveOperateLv", return_value=FakeOperateLv()).start()
        self.get_chain = mock.patch.object(
            shared_block_plugin.linux, "qcow2_get_file_chain").start()
        self.get_format = mock.patch.object(
            shared_block_plugin.linux, "get_img_fmt", return_value="qcow2").start()
        self.get_virtual_size = mock.patch.object(
            shared_block_plugin.linux, "qcow2_virtualsize", return_value=1024).start()
        self.get_lv_size = mock.patch.object(
            lvm, "get_lv_size", return_value=128).start()
        self.get_ranges = mock.patch.object(
            sharedblock_lanfree, "get_lv_range_descriptors").start()

    def tearDown(self):
        mock.patch.stopall()

    def test_collects_complete_chain_and_returns_source_install_paths(self):
        chain = [
            "/dev/vg/S2", "/dev/vg/manual", "/dev/vg/S1", "/dev/vg/base"]
        self.get_chain.return_value = chain
        self.get_ranges.return_value = self._ranges(4)

        rsp = self._call([{
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeUuid": "volume-1",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }])

        self.assertTrue(rsp.success, rsp.error)
        self.assertEqual(4, len(rsp.layouts[0].layers))
        self.assertEqual(
            ["sharedblock://vg/S2", "sharedblock://vg/manual",
             "sharedblock://vg/S1", "sharedblock://vg/base"],
            [item.sourceInstallPath for item in rsp.layouts[0].layers])
        self.assertEqual(
            [1, 2, 3, None],
            [item.parentLayerIndex for item in rsp.layouts[0].layers])
        range_targets = self.get_ranges.call_args[0][1]
        self.assertEqual(
            chain, [item.absoluteInstallPath for item in range_targets])
        self.recursive.assert_called_once_with(
            "/dev/vg/S2", shared=True,
            skip_deactivate_tags=[shared_block_plugin.IMAGE_TAG],
            delete_when_exception=False)

    def test_rejects_backing_layer_from_another_vg(self):
        self.get_chain.return_value = ["/dev/vg/S2", "/dev/other/base"]

        rsp = self._call([{
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeUuid": "volume-1",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }])

        self.assertFalse(rsp.success)
        self.assertTrue("does not belong" in rsp.error)
        self.assertEqual(0, self.get_ranges.call_count)

    def _ranges(self, count):
        return {
            "luns": [{"wwid": "wwid-a", "capacityBytes": 4096}],
            "descriptors": [
                {"resourceUuid": "snapshot-s2:%s" % index, "ranges": [
                    {"wwid": "wwid-a", "lvOffsetBytes": 0,
                     "lunOffsetBytes": index * 128, "lengthBytes": 128}
                ]}
                for index in range(count)
            ]
        }

    def _call(self, targets):
        response = self.plugin.get_volume_snapshot_lan_free_layouts(
            {http.REQUEST_BODY: jsonobject.dumps(
                {"vgUuid": "vg", "targets": targets})})
        return jsonobject.loads(response)


if __name__ == "__main__":
    unittest.main()
