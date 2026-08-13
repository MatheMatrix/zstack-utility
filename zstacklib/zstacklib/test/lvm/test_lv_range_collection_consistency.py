import unittest

from zstacklib.utils import lvm_range


MIB = 1024 * 1024


class CallSequence(object):
    def __init__(self, values):
        self.values = list(values)
        self.call_count = 0

    def __call__(self, *unused_args, **unused_kwargs):
        value = self.values[self.call_count]
        self.call_count += 1
        return value


class ConstantCall(object):
    def __init__(self, value):
        self.value = value
        self.call_count = 0

    def __call__(self, *unused_args, **unused_kwargs):
        self.call_count += 1
        return self.value


class TestLvRangeCollectionConsistency(unittest.TestCase):
    def assertRaisesPattern(self, exception, pattern):
        method = getattr(self, "assertRaisesRegex", None)
        if method is None:
            method = self.assertRaisesRegexp
        return method(exception, pattern)

    @staticmethod
    def vg_report(seqno, missing_pv_count=0):
        return {"report": [{"vg": [{
            "vg_name": "ps-uuid",
            "vg_uuid": "lvm-vg-uuid",
            "vg_attr": "wz--ns",
            "vg_extent_size": str(4 * MIB),
            "vg_seqno": str(seqno),
            "pv_count": "1",
            "vg_missing_pv_count": str(missing_pv_count)
        }]}]}

    @staticmethod
    def pv_report():
        return {"report": [{"pv": [{
            "vg_uuid": "lvm-vg-uuid",
            "pv_uuid": "pv-uuid-a",
            "pv_name": "/dev/sdc",
            "pv_size": str(60 * MIB),
            "dev_size": str(64 * MIB),
            "pe_start": str(MIB),
            "pv_pe_count": "15",
            "pv_missing": "",
            "pv_duplicate": ""
        }]}]}

    def install_collectors(self, seqnos, missing_pv_count=0):
        vg = CallSequence([
            self.vg_report(value, missing_pv_count)
            for value in seqnos
        ])
        lv = ConstantCall({"report": []})
        pv = ConstantCall(self.pv_report())
        devices = ConstantCall([])
        builder = ConstantCall({"luns": [], "descriptors": []})
        retries = []
        return vg, lv, pv, devices, builder, retries

    def collect(self, collectors):
        vg, lv, pv, devices, builder, retries = collectors
        result = lvm_range.collect_consistent_lv_range_descriptors(
            "ps-uuid", ["/dev/ps-uuid/lv-1"], [{
                "resourceUuid": "snapshot-1",
                "absoluteInstallPath": "/dev/ps-uuid/lv-1"
            }], vg, lv, pv, devices, builder, retries.append)
        return result, collectors

    def test_retries_transient_vg_metadata_change(self):
        result, collectors = self.collect(
            self.install_collectors([17, 18, 18, 18, 18]))
        vg, lv, _unused_pv, devices, builder, retries = collectors

        self.assertEqual([], result["descriptors"])
        self.assertEqual(5, vg.call_count)
        self.assertEqual(2, lv.call_count)
        self.assertEqual(1, devices.call_count)
        self.assertEqual(1, builder.call_count)
        self.assertEqual(1, len(retries))

    def test_retries_vg_change_during_device_collection(self):
        result, collectors = self.collect(
            self.install_collectors([17, 17, 18, 18, 18, 18]))
        vg, lv, _unused_pv, devices, builder, retries = collectors

        self.assertEqual([], result["descriptors"])
        self.assertEqual(6, vg.call_count)
        self.assertEqual(2, lv.call_count)
        self.assertEqual(2, devices.call_count)
        self.assertEqual(1, builder.call_count)
        self.assertEqual(1, len(retries))

    def test_rejects_continuous_vg_metadata_change(self):
        collectors = self.install_collectors([17, 18, 19, 20, 21, 22])
        vg, _unused_lv, _unused_pv, devices, builder, retries = collectors

        with self.assertRaisesPattern(
                ValueError, "LVM_RANGE_METADATA_CHANGED"):
            self.collect(collectors)

        self.assertEqual(6, vg.call_count)
        self.assertEqual(0, devices.call_count)
        self.assertEqual(0, builder.call_count)
        self.assertEqual(3, len(retries))

    def test_rejects_partial_vg_before_device_collection(self):
        collectors = self.install_collectors(
            [17, 17], missing_pv_count=1)
        _unused_vg, _unused_lv, _unused_pv, devices, builder, retries = collectors

        with self.assertRaisesPattern(ValueError, "LVM_RANGE_VG_PARTIAL"):
            self.collect(collectors)

        self.assertEqual(0, devices.call_count)
        self.assertEqual(0, builder.call_count)
        self.assertEqual([], retries)


if __name__ == "__main__":
    unittest.main()
