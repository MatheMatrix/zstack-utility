import unittest

from zstacklib.utils import lvm_range


MIB = 1024 * 1024


class TestLvRangeDescriptor(unittest.TestCase):
    def assertRaisesPattern(self, exception, pattern):
        method = getattr(self, "assertRaisesRegex", None)
        if method is None:
            method = self.assertRaisesRegexp
        return method(exception, pattern)

    def setUp(self):
        self.vg_report = {
            "report": [{"vg": [{
                "vg_name": "ps-uuid",
                "vg_uuid": "lvm-vg-uuid",
                "vg_attr": "wz--ns",
                "vg_extent_size": str(4 * MIB),
                "vg_seqno": "17",
                "pv_count": "1",
                "vg_missing_pv_count": "0"
            }]}]
        }
        self.targets = [{
            "resourceType": "VolumeSnapshot",
            "resourceUuid": "snapshot-1",
            "volumeUuid": "volume-1",
            "requestIndex": 0,
            "installPath": "sharedblock://ps-uuid/lv-1",
            "absoluteInstallPath": "/dev/ps-uuid/lv-1"
        }]

    @staticmethod
    def pv_report(*rows):
        return {"report": [{"pv": list(rows)}]}

    @staticmethod
    def lv_report(*rows):
        return {"report": [{"seg": list(rows)}]}

    @staticmethod
    def block_device(path, wwid, size=64 * MIB, topology="disk",
                     path_capacities=None):
        return {
            "paths": [path],
            "canonicalPath": path,
            "wwid": wwid,
            "size": size,
            "topology": topology,
            "pathCapacities": path_capacities or [{
                "path": path,
                "size": size
            }],
            "transport": "iscsi",
            "targetIdentifier": "iqn.2026-08.test:%s" % wwid,
            "lunId": 0
        }

    @staticmethod
    def linear_row(lv_size, seg_start_pe, seg_size_pe, pe_ranges, segtype="linear"):
        return {
            "vg_uuid": "lvm-vg-uuid",
            "lv_uuid": "lv-uuid-1",
            "lv_name": "lv-1",
            "lv_size": str(lv_size),
            "segtype": segtype,
            "seg_start_pe": str(seg_start_pe),
            "seg_size_pe": str(seg_size_pe),
            "seg_pe_ranges": pe_ranges
        }

    @staticmethod
    def pv_row(name, uuid="pv-uuid-a", pe_start=MIB,
               dev_size=64 * MIB, pe_count=15):
        return {
            "vg_uuid": "lvm-vg-uuid",
            "pv_uuid": uuid,
            "pv_name": name,
            "pv_size": str(pe_count * 4 * MIB),
            "dev_size": str(dev_size),
            "pe_start": str(pe_start),
            "pv_pe_count": str(pe_count),
            "pv_missing": "",
            "pv_duplicate": ""
        }

    def vg_report_for(self, pv_count=1, missing_pv_count=0,
                      vg_attr="wz--ns"):
        row = dict(self.vg_report["report"][0]["vg"][0])
        row["pv_count"] = str(pv_count)
        row["vg_missing_pv_count"] = str(missing_pv_count)
        row["vg_attr"] = vg_attr
        return {"report": [{"vg": [row]}]}

    def test_builds_minimal_single_linear_range(self):
        result = lvm_range.build_lv_range_descriptors(
            self.vg_report,
            self.lv_report(self.linear_row(8 * MIB, 0, 2, "/dev/mapper/lun-a:3-4")),
            self.pv_report(self.pv_row("/dev/mapper/lun-a")),
            [self.block_device("/dev/mapper/lun-a", "wwid-a")],
            self.targets
        )

        self.assertEqual([{
            "wwid": "wwid-a",
            "capacityBytes": 64 * MIB
        }], result["luns"])
        self.assertEqual([{
            "resourceUuid": "snapshot-1",
            "ranges": [{
                "wwid": "wwid-a",
                "lvOffsetBytes": 0,
                "lunOffsetBytes": 13 * MIB,
                "lengthBytes": 8 * MIB
            }]
        }], result["descriptors"])

    def test_orders_fragmented_cross_lun_ranges_by_lv_offset(self):
        result = lvm_range.build_lv_range_descriptors(
            self.vg_report_for(pv_count=2),
            self.lv_report(
                self.linear_row(80 * MIB, 10, 10, "/dev/mapper/lun-a:5-14"),
                self.linear_row(80 * MIB, 0, 5, "/dev/mapper/lun-b:0-4"),
                self.linear_row(80 * MIB, 5, 5, "/dev/mapper/lun-a:30-34")
            ),
            self.pv_report(
                self.pv_row("/dev/mapper/lun-a", "pv-a",
                            dev_size=256 * MIB, pe_count=63),
                self.pv_row("/dev/mapper/lun-b", "pv-b",
                            dev_size=256 * MIB, pe_count=63)
            ),
            [self.block_device("/dev/mapper/lun-a", "wwid-a", 256 * MIB),
             self.block_device("/dev/mapper/lun-b", "wwid-b", 256 * MIB)],
            self.targets
        )

        ranges = result["descriptors"][0]["ranges"]
        self.assertEqual([0, 20 * MIB, 40 * MIB],
                         [item["lvOffsetBytes"] for item in ranges])
        self.assertEqual(["wwid-b", "wwid-a", "wwid-a"],
                         [item["wwid"] for item in ranges])
        self.assertEqual([121 * MIB, 21 * MIB],
                         [item["lunOffsetBytes"] for item in ranges[1:]])
        self.assertEqual(set(["wwid-a", "wwid-b"]),
                         set(item["wwid"] for item in result["luns"]))

    def test_rejects_overlapping_physical_ranges_on_same_lun(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PHYSICAL_OVERLAP"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(
                    self.linear_row(8 * MIB, 0, 1,
                                    "/dev/mapper/lun-a:0-0"),
                    self.linear_row(8 * MIB, 1, 1,
                                    "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_accepts_adjacent_physical_ranges_on_same_lun(self):
        result = lvm_range.build_lv_range_descriptors(
            self.vg_report,
            self.lv_report(
                self.linear_row(8 * MIB, 0, 1,
                                "/dev/mapper/lun-a:0-0"),
                self.linear_row(8 * MIB, 1, 1,
                                "/dev/mapper/lun-a:1-1")),
            self.pv_report(self.pv_row("/dev/mapper/lun-a")),
            [self.block_device("/dev/mapper/lun-a", "wwid-a")],
            self.targets)

        self.assertEqual(2, len(result["descriptors"][0]["ranges"]))

    def test_rejects_distinct_pvs_with_same_wwid(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_WWID_AMBIGUOUS"):
            self._build_two_pv_result(64 * MIB, 64 * MIB)

    def test_rejects_duplicate_wwid_on_unreferenced_vg_pv(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_WWID_AMBIGUOUS"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report_for(pv_count=2),
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(
                    self.pv_row("/dev/mapper/lun-a", "pv-a"),
                    self.pv_row("/dev/mapper/lun-b", "pv-b")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a"),
                 self.block_device("/dev/mapper/lun-b", "wwid-a")],
                self.targets)

    def test_rejects_conflicting_capacity_for_same_wwid(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_WWID_CAPACITY_MISMATCH"):
            self._build_two_pv_result(64 * MIB, 128 * MIB)

    def test_rejects_missing_pvid(self):
        pv = self.pv_row("/dev/mapper/lun-a")
        pv["pv_uuid"] = ""

        with self.assertRaisesPattern(ValueError, "LVM_RANGE_PVID_MISSING"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(pv),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_duplicate_pv_name_with_stable_code(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PV_METADATA_INVALID"):
            lvm_range.validate_lvm_metadata(
                self.vg_report_for(pv_count=2),
                self.pv_report(
                    self.pv_row("/dev/mapper/lun-a", "pv-a"),
                    self.pv_row("/dev/mapper/lun-a", "pv-b")))

    def test_rejects_invalid_vg_report_with_stable_code(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_VG_METADATA_INVALID"):
            lvm_range.validate_lvm_metadata({}, self.pv_report())

    def test_rejects_duplicate_pvid(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_PVID_DUPLICATE"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report_for(pv_count=2),
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(
                    self.pv_row("/dev/mapper/lun-a", "same-pvid"),
                    self.pv_row("/dev/mapper/lun-b", "same-pvid")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a"),
                 self.block_device("/dev/mapper/lun-b", "wwid-b")],
                self.targets)

    def test_rejects_partial_or_missing_vg(self):
        for vg_report in (
                self.vg_report_for(vg_attr="wz-pns"),
                self.vg_report_for(missing_pv_count=1)):
            with self.assertRaisesPattern(ValueError, "LVM_RANGE_VG_PARTIAL"):
                lvm_range.build_lv_range_descriptors(
                    vg_report,
                    self.lv_report(self.linear_row(
                        4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                    self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                    [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                    self.targets)

    def test_rejects_missing_vg_state_field_with_stable_code(self):
        vg_report = self.vg_report_for()
        del vg_report["report"][0]["vg"][0]["vg_missing_pv_count"]
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_VG_METADATA_INVALID"):
            lvm_range.build_lv_range_descriptors(
                vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_missing_or_duplicate_pv_state(self):
        for field, value, code in (
                ("pv_missing", "missing", "LVM_RANGE_PV_MISSING"),
                ("pv_duplicate", "duplicate", "LVM_RANGE_PV_DUPLICATE")):
            pv = self.pv_row("/dev/mapper/lun-a")
            pv[field] = value
            with self.assertRaisesPattern(ValueError, code):
                lvm_range.build_lv_range_descriptors(
                    self.vg_report,
                    self.lv_report(self.linear_row(
                        4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                    self.pv_report(pv),
                    [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                    self.targets)

    def test_rejects_incomplete_pv_report(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_PV_COUNT_MISMATCH"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report_for(pv_count=2),
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_pv_data_area_beyond_device(self):
        pv = self.pv_row(
            "/dev/mapper/lun-a", pe_start=MIB,
            dev_size=64 * MIB, pe_count=16)
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_PV_BOUNDARY"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(pv),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_accepts_pv_data_area_ending_at_device_boundary(self):
        pv = self.pv_row(
            "/dev/mapper/lun-a", pe_start=4 * MIB,
            dev_size=64 * MIB, pe_count=15)

        result = lvm_range.build_lv_range_descriptors(
            self.vg_report,
            self.lv_report(self.linear_row(
                4 * MIB, 0, 1, "/dev/mapper/lun-a:14-14")),
            self.pv_report(pv),
            [self.block_device("/dev/mapper/lun-a", "wwid-a")],
            self.targets)

        self.assertEqual(60 * MIB,
                         result["descriptors"][0]["ranges"][0]["lunOffsetBytes"])
        self.assertEqual(4 * MIB,
                         result["descriptors"][0]["ranges"][0]["lengthBytes"])

    def test_rejects_missing_pv_boundary_field_with_stable_code(self):
        pv = self.pv_row("/dev/mapper/lun-a")
        del pv["pv_pe_count"]
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PV_METADATA_INVALID"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(pv),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_segment_beyond_pv_extent_count(self):
        pv = self.pv_row("/dev/mapper/lun-a", pe_count=1)
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_PV_EXTENT_OVERFLOW"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:1-1")),
                self.pv_report(pv),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_lvm_and_device_capacity_mismatch(self):
        pv = self.pv_row("/dev/mapper/lun-a", dev_size=64 * MIB)
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_DEVICE_CAPACITY_MISMATCH"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(pv),
                [self.block_device(
                    "/dev/mapper/lun-a", "wwid-a", 128 * MIB)],
                self.targets)

    def test_rejects_multipath_map_slave_capacity_mismatch(self):
        capacities = [
            {"path": "/dev/mapper/mpatha", "size": 64 * MIB},
            {"path": "/dev/sda", "size": 64 * MIB},
            {"path": "/dev/sdb", "size": 63 * MIB}
        ]
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_MULTIPATH_CAPACITY_MISMATCH"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/mpatha:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/mpatha")),
                [self.block_device(
                    "/dev/mapper/mpatha", "wwid-a", 64 * MIB,
                    topology="mpath", path_capacities=capacities)],
                self.targets)

    def test_rejects_unproven_block_topology(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_TOPOLOGY_UNSUPPORTED"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device(
                    "/dev/mapper/lun-a", "wwid-a", topology="part")],
                self.targets)

    def test_report_fields_include_mapping_identity_and_boundaries(self):
        for field in ("vg_name", "vg_uuid", "vg_attr", "vg_extent_size",
                      "vg_seqno", "pv_count", "vg_missing_pv_count"):
            self.assertIn(field, lvm_range.VG_RANGE_REPORT_FIELDS)
        for field in ("vg_uuid", "pv_uuid", "pv_name", "pv_size",
                      "dev_size", "pe_start", "pv_pe_count", "pv_attr",
                      "pv_missing", "pv_duplicate"):
            self.assertIn(field, lvm_range.PV_RANGE_REPORT_FIELDS)

    def test_missing_pv_rows_do_not_require_device_resolution(self):
        pv_report = self.pv_report(
            self.pv_row("/dev/sdc", "pv-a"),
            dict(self.pv_row("[unknown]", "pv-b"), pv_missing="missing"))

        self.assertEqual(
            ["/dev/sdc"],
            lvm_range.pv_names_for_device_resolution(pv_report))

    def test_metadata_prevalidation_rejects_partial_vg_before_devices(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_VG_PARTIAL"):
            lvm_range.validate_lvm_metadata(
                self.vg_report_for(missing_pv_count=1),
                self.pv_report(self.pv_row("[unknown]")))

    def test_builds_whole_disk_capacity_evidence(self):
        candidate = {
            "dev_name": "sdc",
            "type": "disk",
            "wwid": "wwid-a",
            "size": "64"
        }
        result = lvm_range.build_block_device_evidence(
            candidate, ["/dev/sdc"], lambda path: path,
            lambda unused_path: [], lambda unused_path: 64)

        self.assertEqual("disk", result["topology"])
        self.assertEqual("/dev/sdc", result["canonicalPath"])
        self.assertEqual(64, result["size"])
        self.assertEqual([{"path": "/dev/sdc", "size": 64}],
                         result["pathCapacities"])

    def test_treats_whole_disk_lvm_pv_candidate_as_disk_topology(self):
        candidate = {
            "dev_name": "sdc",
            "type": "lvm-pv",
            "wwid": "wwid-a"
        }

        result = lvm_range.build_block_device_evidence(
            candidate, ["/dev/sdc"], lambda path: path,
            lambda unused_path: [], lambda unused_path: 64)

        self.assertEqual("disk", result["topology"])

    def test_rejects_candidate_without_wwid_with_stable_code(self):
        candidate = {"dev_name": "sdc", "type": "lvm-pv", "wwid": ""}

        with self.assertRaisesPattern(ValueError, "LVM_RANGE_WWID_MISSING"):
            lvm_range.build_block_device_evidence(
                candidate, ["/dev/sdc"], lambda path: path,
                lambda unused_path: [], lambda unused_path: 64)

    def test_builds_multipath_map_and_slave_capacity_evidence(self):
        candidate = {
            "dev_name": "sda",
            "type": "mpath",
            "multipathPath": "mpatha",
            "wwid": "wwid-a",
            "size": "64"
        }
        capacities = {
            "/dev/mapper/mpatha": 64,
            "/dev/sda": 64,
            "/dev/sdb": 64
        }
        result = lvm_range.build_block_device_evidence(
            candidate, ["/dev/sda", "/dev/mapper/mpatha"],
            lambda path: "/dev/dm-7" if path == "/dev/mapper/mpatha" else path,
            lambda path: ["sdb", "sda"],
            lambda path: capacities[path])

        self.assertEqual("mpath", result["topology"])
        self.assertEqual("/dev/dm-7", result["canonicalPath"])
        self.assertEqual([
            {"path": "/dev/mapper/mpatha", "size": 64},
            {"path": "/dev/sda", "size": 64},
            {"path": "/dev/sdb", "size": 64}
        ], result["pathCapacities"])

    def test_rejects_incomplete_multipath_topology_evidence(self):
        candidate = {
            "dev_name": "sda",
            "type": "mpath",
            "multipathPath": "mpatha",
            "wwid": "wwid-a",
            "size": "64"
        }
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_MULTIPATH_TOPOLOGY_INCOMPLETE"):
            lvm_range.build_block_device_evidence(
                candidate, ["/dev/mapper/mpatha"],
                lambda unused_path: "/dev/dm-7",
                lambda unused_path: [], lambda unused_path: 64)

    def test_resolves_pv_to_one_block_device_evidence(self):
        candidates = [({
            "dev_name": "sdc",
            "type": "disk",
            "wwid": "wwid-a"
        }, ["/dev/sdc"])]
        result = lvm_range.resolve_pv_block_devices(
            ["/dev/sdc"], candidates, lambda path: path,
            lambda unused_path: [], lambda unused_path: 64)

        self.assertEqual(1, len(result))
        self.assertEqual("wwid-a", result[0]["wwid"])
        self.assertIn("/dev/sdc", result[0]["paths"])

    def test_rejects_unresolved_pv_block_device(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PV_DEVICE_UNRESOLVED"):
            lvm_range.resolve_pv_block_devices(
                ["/dev/sdc"], [], lambda path: path,
                lambda unused_path: [], lambda unused_path: 64)

    def test_rejects_ambiguous_pv_block_device(self):
        candidates = [
            ({"dev_name": "sdc", "type": "disk", "wwid": "wwid-a"},
             ["/dev/sdc"]),
            ({"dev_name": "sdc", "type": "disk", "wwid": "wwid-b"},
             ["/dev/sdc"])
        ]
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PV_DEVICE_AMBIGUOUS"):
            lvm_range.resolve_pv_block_devices(
                ["/dev/sdc"], candidates, lambda path: path,
                lambda unused_path: [], lambda unused_path: 64)

    def test_rejects_duplicate_wwid_on_non_pv_candidate(self):
        candidates = [
            ({"dev_name": "sdc", "type": "disk", "wwid": "wwid-a"},
             ["/dev/sdc"]),
            ({"dev_name": "sdd", "type": "disk", "wwid": "wwid-a"},
             ["/dev/sdd"])
        ]
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_WWID_AMBIGUOUS"):
            lvm_range.resolve_pv_block_devices(
                ["/dev/sdc"], candidates, lambda path: path,
                lambda unused_path: [], lambda unused_path: 64)

    def test_ignores_duplicate_wwid_unrelated_to_target_vg(self):
        candidates = [
            ({"dev_name": "sdc", "type": "disk", "wwid": "wwid-a"},
             ["/dev/sdc"]),
            ({"dev_name": "sdd", "type": "disk", "wwid": "wwid-b"},
             ["/dev/sdd"]),
            ({"dev_name": "sde", "type": "disk", "wwid": "wwid-b"},
             ["/dev/sde"])
        ]

        devices = lvm_range.resolve_pv_block_devices(
            ["/dev/sdc"], candidates, lambda path: path,
            lambda unused_path: [], lambda unused_path: 64)

        self.assertEqual(["wwid-a"], [device["wwid"] for device in devices])

    def test_rejects_non_linear_segment(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_SEGMENT_TYPE_UNSUPPORTED"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(
                    8 * MIB, 0, 2, "/dev/mapper/lun-a:0-1", "striped")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                self.targets)

    def test_rejects_gap_and_overlap_in_logical_ranges(self):
        for lv_size, second_start in ((8 * MIB, 0), (12 * MIB, 2)):
            with self.assertRaisesPattern(ValueError, "gap or overlap"):
                lvm_range.build_lv_range_descriptors(
                    self.vg_report,
                    self.lv_report(
                        self.linear_row(lv_size, 0, 1, "/dev/mapper/lun-a:0-0"),
                        self.linear_row(lv_size, second_start, 1, "/dev/mapper/lun-a:1-1")
                    ),
                    self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                    [self.block_device("/dev/mapper/lun-a", "wwid-a")],
                    self.targets)

    def test_rejects_pv_without_wwid(self):
        with self.assertRaisesPattern(ValueError, "LVM_RANGE_WWID_MISSING"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", None)],
                self.targets)

    def test_rejects_ambiguous_pv_device_mapping(self):
        devices = [self.block_device("/dev/mapper/lun-a", "wwid-a"),
                   self.block_device("/dev/mapper/lun-a", "wwid-b")]
        with self.assertRaisesPattern(ValueError, "ambiguous"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                devices,
                self.targets)

    def test_rejects_non_positive_lun_capacity(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_DEVICE_CAPACITY_MISSING"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(4 * MIB, 0, 1, "/dev/mapper/lun-a:0-0")),
                self.pv_report(self.pv_row("/dev/mapper/lun-a")),
                [self.block_device("/dev/mapper/lun-a", "wwid-a", 0)],
                self.targets)

    def test_rejects_range_beyond_lun_capacity(self):
        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_PV_EXTENT_OVERFLOW"):
            lvm_range.build_lv_range_descriptors(
                self.vg_report,
                self.lv_report(self.linear_row(8 * MIB, 0, 2, "/dev/mapper/lun-a:3-4")),
                self.pv_report(self.pv_row(
                    "/dev/mapper/lun-a", dev_size=16 * MIB, pe_count=3)),
                [self.block_device("/dev/mapper/lun-a", "wwid-a", size=16 * MIB)],
                self.targets)

    def _build_two_pv_result(self, first_capacity, second_capacity):
        return lvm_range.build_lv_range_descriptors(
            self.vg_report_for(pv_count=2),
            self.lv_report(
                self.linear_row(8 * MIB, 0, 1, "/dev/mapper/lun-a:0-0"),
                self.linear_row(8 * MIB, 1, 1, "/dev/mapper/lun-b:0-0")
            ),
            self.pv_report(
                self.pv_row("/dev/mapper/lun-a", "pv-a",
                            dev_size=first_capacity,
                            pe_count=(first_capacity - MIB) // (4 * MIB)),
                self.pv_row("/dev/mapper/lun-b", "pv-b",
                            dev_size=second_capacity,
                            pe_count=(second_capacity - MIB) // (4 * MIB))
            ),
            [self.block_device("/dev/mapper/lun-a", "wwid-a", first_capacity),
             self.block_device("/dev/mapper/lun-b", "wwid-a", second_capacity)],
            self.targets)


if __name__ == "__main__":
    unittest.main()
