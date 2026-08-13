import unittest
import sys
import types

import mock
from zstacklib import utils as zstack_utils

from zstacklib.utils import sharedblock_lanfree as lanfree


class TestSharedBlockLanFree(unittest.TestCase):
    def assert_raises_regex(self, exception, pattern):
        assertion = getattr(self, "assertRaisesRegex", None)
        if assertion is None:
            assertion = self.assertRaisesRegexp
        return assertion(exception, pattern)

    def test_source_plan_keeps_complete_platform_chain(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }
        chain = [
            "/dev/vg/S2", "/dev/vg/manual", "/dev/vg/S1", "/dev/vg/base"]

        plan = lanfree.build_source_plan("vg", target, chain)

        self.assertEqual(chain, plan["paths"])
        self.assertEqual(
            ["snapshot-s2:0", "snapshot-s2:1", "snapshot-s2:2",
             "snapshot-s2:3"],
            [item.resourceUuid for item in plan["rangeTargets"]])
        self.assertEqual(
            chain, [item.absoluteInstallPath for item in plan["rangeTargets"]])
        self.assertNotIn("sourceChainScope", plan)
        self.assertNotIn("sourceChainSelectionReason", plan)

    def test_source_plan_rejects_empty_duplicate_and_outside_vg_chains(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }
        with self.assert_raises_regex(ValueError, "empty"):
            lanfree.build_source_plan("vg", target, [])
        with self.assert_raises_regex(ValueError, "cycle or duplicate"):
            lanfree.build_source_plan(
                "vg", target,
                ["/dev/vg/S2", "/dev/vg/base", "/dev/vg/base"])
        with self.assert_raises_regex(ValueError, "does not belong"):
            lanfree.build_source_plan(
                "vg", target, ["/dev/vg/S2", "/dev/another/base"])

    def test_source_plan_requires_requested_snapshot_as_chain_head(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }

        with self.assert_raises_regex(ValueError, "chain head"):
            lanfree.build_source_plan(
                "vg", target, ["/dev/vg/other", "/dev/vg/base"])

    def test_source_plan_requires_snapshot_uuid(self):
        target = {
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }

        with self.assert_raises_regex(ValueError, "volumeSnapshotUuid"):
            lanfree.build_source_plan("vg", target, ["/dev/vg/S2"])

        target["volumeSnapshotUuid"] = "  "
        with self.assert_raises_regex(ValueError, "volumeSnapshotUuid"):
            lanfree.build_source_plan("vg", target, ["/dev/vg/S2"])

    def test_rejects_shell_metacharacters_in_vg_and_lv_names(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2;touch-pwned"
        }
        with self.assert_raises_regex(ValueError, "invalid"):
            lanfree.build_source_plan(
                "vg", target, ["/dev/vg/S2;touch-pwned"])

        with self.assert_raises_regex(ValueError, "invalid"):
            lanfree.build_source_plan(
                "vg$(touch-pwned)", {
                    "volumeSnapshotUuid": "snapshot-s2",
                    "volumeSnapshotInstallPath":
                        "sharedblock://vg$(touch-pwned)/S2"
                }, ["/dev/vg$(touch-pwned)/S2"])

    def test_lvm_json_report_has_a_bounded_execution_time(self):
        command = "vgs --readonly --nolocking -t --reportformat json"
        shell_cmd = mock.Mock()
        shell_cmd.return_code = 0
        shell_cmd.stdout = '{"report": []}'
        fake_shell = types.ModuleType("zstacklib.utils.shell")
        fake_shell.ShellCmd = mock.Mock(return_value=shell_cmd)
        with mock.patch.dict(
                sys.modules, {"zstacklib.utils.shell": fake_shell}):
            with mock.patch.object(
                    zstack_utils, "shell", fake_shell, create=True):
                lanfree._run_lvm_json_report(command)

        fake_shell.ShellCmd.assert_called_once_with(
            "timeout %s %s" % (lanfree.LVM_REPORT_TIMEOUT_SECONDS, command))

    def test_source_layout_returns_every_layer_source_path_and_parent(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s2",
            "volumeUuid": "volume-1",
            "volumeSnapshotInstallPath": "sharedblock://vg/S2"
        }
        plan = lanfree.build_source_plan(
            "vg", target,
            ["/dev/vg/S2", "/dev/vg/manual", "/dev/vg/base"])
        range_result = {
            "luns": [{"wwid": "wwid-a", "capacityBytes": 1024}],
            "descriptors": [
                {"resourceUuid": "snapshot-s2:0", "ranges": [
                    {"wwid": "wwid-a", "lvOffsetBytes": 0,
                     "lunOffsetBytes": 512, "lengthBytes": 64},
                    {"wwid": "wwid-a", "lvOffsetBytes": 64,
                     "lunOffsetBytes": 128, "lengthBytes": 64}
                ]},
                {"resourceUuid": "snapshot-s2:1", "ranges": [
                    {"wwid": "wwid-a", "lvOffsetBytes": 0,
                     "lunOffsetBytes": 256, "lengthBytes": 128}
                ]},
                {"resourceUuid": "snapshot-s2:2", "ranges": [
                    {"wwid": "wwid-a", "lvOffsetBytes": 0,
                     "lunOffsetBytes": 384, "lengthBytes": 128}
                ]}
            ]
        }

        layout = lanfree.build_source_layout(
            target, plan, range_result,
            {"/dev/vg/S2": "qcow2", "/dev/vg/manual": "qcow2",
             "/dev/vg/base": "raw"},
            {"/dev/vg/S2": 128, "/dev/vg/manual": 128,
             "/dev/vg/base": 128}, 1024)

        self.assertEqual("snapshot-s2", layout["volumeSnapshotUuid"])
        self.assertEqual("volume-1", layout["volumeUuid"])
        self.assertEqual(
            ["sharedblock://vg/S2", "sharedblock://vg/manual",
             "sharedblock://vg/base"],
            [item["sourceInstallPath"] for item in layout["layers"]])
        self.assertEqual([1, 2, None], [
            item["parentLayerIndex"] for item in layout["layers"]])
        self.assertEqual([0, 64], [
            item["lvOffsetBytes"] for item in layout["layers"][0]["ranges"]])
        for field in (
                "volumeSnapshotInstallPath", "baseVolumeSnapshotUuid",
                "sourceChainScope", "sourceChainSelectionReason"):
            self.assertNotIn(field, layout)
        self.assertNotIn(
            "externalParentVolumeSnapshotUuid", layout["layers"][-1])

    def test_source_layout_rejects_missing_range_descriptor(self):
        target = {
            "volumeSnapshotUuid": "snapshot-s1",
            "volumeUuid": "volume-1",
            "volumeSnapshotInstallPath": "sharedblock://vg/S1"
        }
        plan = lanfree.build_source_plan(
            "vg", target, ["/dev/vg/S1", "/dev/vg/base"])

        with self.assert_raises_regex(ValueError, "mismatched range descriptors"):
            lanfree.build_source_layout(
                target, plan, {"luns": [], "descriptors": []},
                {"/dev/vg/S1": "qcow2", "/dev/vg/base": "raw"},
                {"/dev/vg/S1": 128, "/dev/vg/base": 128}, 1024)

    def test_merge_luns_deduplicates_equal_capacities(self):
        merged = lanfree.merge_luns([
            [{"wwid": "wwid-a", "capacityBytes": 1024}],
            [{"wwid": "wwid-a", "capacityBytes": 1024},
             {"wwid": "wwid-b", "capacityBytes": 2048}]
        ])

        self.assertEqual(["wwid-a", "wwid-b"], [
            item["wwid"] for item in merged])

    def test_merge_luns_rejects_conflicting_capacities(self):
        with self.assert_raises_regex(ValueError, "conflicting capacities"):
            lanfree.merge_luns([
                [{"wwid": "wwid-a", "capacityBytes": 1024}],
                [{"wwid": "wwid-a", "capacityBytes": 2048}]
            ])


if __name__ == "__main__":
    unittest.main()
