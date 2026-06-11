"""
NVMe-oF (fabrics) native multipath must not break disk_device_status/state.

Root cause this guards against (ZSV-12307, third independent bug):
  collect_nvme_disk_stat used to enumerate /sys/class/nvme/<ctrl>, which on a
  fabrics host lists the *hidden controller-path* namespaces (e.g. nvme2c2n1).
  Those carry a wwid file (so they passed the old filter) but have NO
  /sys/block/<name>/dev node. generate() then did
      linux.read_file("/sys/block/nvme2c2n1/dev").strip()
  read_file returned None -> .strip() -> AttributeError, which propagated out of
  collect_disk_stat and emptied BOTH disk_device_status and disk_device_state
  for the whole host (observed 5580 crashes/day on 172.25.15.138).

  A naive "report the head instead" is also wrong: the fabrics head nvme2n1 has
  a dev node but NO /sys/block/nvme2n1/device/state, and it IS an LVM PV, so a
  blank state would be converted to 0 and raise a false PV-abnormal alarm. The
  real state lives on the sibling controller /sys/class/nvme/nvme2/state.

These tests pin the contract end-to-end through collect_disk_stat():
  1. presence of c-path devices must NOT raise (the crash regression).
  2. fabrics heads are reported, with state derived from the controller (live).
  3. c-path devices (nvmeXcYnZ) are never reported.
  4. local PCIe NVMe (nvme0n1, state on /sys/block/.../device/state) still works.

Style follows test_prometheus_disk_state.py (import-or-skip + mock.patch.object).
"""
import unittest

try:
    from kvmagent.plugins import prometheus
except ImportError as e:
    raise unittest.SkipTest(
        "kvmagent package not importable (%s); "
        "run with PYTHONPATH=kvmagent:zstacklib" % e)

import mock

# convert_state_to_int contract: 1 for running/live, else 0.
RUNNING, NOT_RUNNING = 1, 0

# Real /sys/block top level on zsv-new (172.25.15.138): local PCIe head nvme0n1,
# fabrics subsystems 2 and 3. nvmeXcYnZ are the hidden controller-path devices.
SYS_BLOCK_ENTRIES = [
    "nvme0n1",
    "nvme2c2n1", "nvme2c2n2", "nvme2c2n3",
    "nvme2n1", "nvme2n2", "nvme2n3",
    "nvme3c3n1",
    "nvme3n1",
]

# /sys/block/<head>/device subsystem dir listing (the sibling controller is nvme2/nvme3).
SUBSYS_ENTRIES = {
    "nvme2n1": ["iopolicy", "model", "nvme2", "nvme2n1", "subsysnqn"],
    "nvme2n2": ["iopolicy", "model", "nvme2", "nvme2n2", "subsysnqn"],
    "nvme2n3": ["iopolicy", "model", "nvme2", "nvme2n3", "subsysnqn"],
    "nvme3n1": ["iopolicy", "model", "nvme3", "nvme3n1", "subsysnqn"],
}

# dev node: heads have one, hidden c-paths do not (None).
DEV_NODE = {
    "nvme0n1": "259:0",
    "nvme2n1": "259:53", "nvme2n2": "259:56", "nvme2n3": "259:58",
    "nvme3n1": "259:62",
    "nvme2c2n1": None, "nvme2c2n2": None, "nvme2c2n3": None, "nvme3c3n1": None,
}

# device/state: local PCIe head has it; fabrics heads do not (None).
DEVICE_STATE = {
    "nvme0n1": "live",
    "nvme2n1": None, "nvme2n2": None, "nvme2n3": None, "nvme3n1": None,
}

# controller state (sibling of the fabrics head under the subsystem dir).
CONTROLLER_STATE = {"nvme2": "live", "nvme3": "live"}


def _sample_pairs(metric_family):
    pairs = {}
    for s in metric_family.samples:
        labels = s.labels if hasattr(s, "labels") else s[1]
        value = s.value if hasattr(s, "value") else s[2]
        pairs[labels["disk"]] = value
    return pairs


class TestCollectNvmeDiskStatFabrics(unittest.TestCase):

    def _run(self):
        def fake_exists(path):
            if path == "/sys/block":
                return True
            if path == "/sys/class/scsi_disk":
                return False
            return False

        def fake_isdir(path):
            return path.startswith("/sys/block/") and path.endswith("/device")

        def fake_listdir(path):
            if path == "/sys/block":
                return list(SYS_BLOCK_ENTRIES)
            if path.startswith("/sys/block/") and path.endswith("/device"):
                head = path[len("/sys/block/"):-len("/device")]
                return list(SUBSYS_ENTRIES.get(head, []))
            return []

        def fake_read_file_strip(path):
            if path.startswith("/sys/block/") and path.endswith("/dev"):
                return DEV_NODE.get(path[len("/sys/block/"):-len("/dev")])
            if path.startswith("/sys/block/") and path.endswith("/device/state"):
                return DEVICE_STATE.get(path[len("/sys/block/"):-len("/device/state")])
            if path.startswith("/sys/class/nvme/") and path.endswith("/state"):
                return CONTROLLER_STATE.get(path[len("/sys/class/nvme/"):-len("/state")])
            return None

        with mock.patch.object(prometheus.os.path, "exists", side_effect=fake_exists), \
                mock.patch.object(prometheus.os.path, "isdir", side_effect=fake_isdir), \
                mock.patch.object(prometheus.os, "listdir", side_effect=fake_listdir), \
                mock.patch.object(prometheus.linux, "read_file_strip",
                                  side_effect=fake_read_file_strip), \
                mock.patch.object(prometheus, "bash_ro", return_value=(1, "")), \
                mock.patch.object(prometheus, "sblk_pv_vg", {}):
            families = prometheus.collect_disk_stat()

        by_name = {f.name: f for f in families}
        return _sample_pairs(by_name["disk_device_state"]), \
            _sample_pairs(by_name["disk_device_status"])

    def test_does_not_crash_with_cpath_devices_present(self):
        # WHY: the original bug let a hidden c-path (no /sys/block/<n>/dev) reach
        # generate() and raise AttributeError, emptying the whole collector.
        try:
            self._run()
        except AttributeError as e:
            self.fail("collect_disk_stat raised on NVMe-oF c-path layout: %s" % e)

    def test_fabrics_heads_reported_running_via_controller_state(self):
        # WHY: nvme2n1 has no device/state; its state must be read from the
        # sibling controller (/sys/class/nvme/nvme2/state=live) -> running(1),
        # not a blank that converts to 0 and fires a false PV-abnormal alarm.
        state, _ = self._run()
        for head in ("nvme2n1", "nvme2n2", "nvme2n3", "nvme3n1"):
            self.assertEqual(RUNNING, state.get(head),
                             "fabrics head %s must be running(1) via controller "
                             "state, got %s" % (head, state.get(head)))

    def test_local_pcie_head_still_reported(self):
        # WHY: the rewrite must not regress local PCIe NVMe, whose state sits on
        # /sys/block/nvme0n1/device/state directly.
        state, status = self._run()
        self.assertEqual(RUNNING, state.get("nvme0n1"))
        self.assertEqual(1, status.get("nvme0n1"))

    def test_cpath_devices_never_reported(self):
        # WHY: hidden controller-path devices are an implementation detail of
        # native multipath; reporting them would double-count and reintroduce
        # the /sys/block/<c-path>/dev crash surface.
        state, status = self._run()
        for cpath in ("nvme2c2n1", "nvme2c2n2", "nvme2c2n3", "nvme3c3n1"):
            self.assertNotIn(cpath, state,
                             "c-path %s must not appear in disk_device_state" % cpath)
            self.assertNotIn(cpath, status,
                             "c-path %s must not appear in disk_device_status" % cpath)


# Real /sys/block/<name>/stat rows from zsv-new (172.25.15.138). Field [2] is
# read sectors, field [6] write sectors; head rows are all-zero (native
# multipath does not account on the head), real I/O lands on the c-path.
STAT = {
    "nvme2c2n1": "75884 0 16606770 150201 665 0 665 264 0 150369 150466 0 0 0 0",
    "nvme2c2n2": "29025 0 3401776 53278 0 0 0 0 0 53179 53278 0 0 0 0",
    "nvme2c2n3": "29022 0 3401504 66379 0 0 0 0 0 66426 66379 0 0 0 0",
    "nvme3c3n1": "90312 0 7622338 126462 20255 378573 3761542 283129 0 98942 409592 0 0 0 0",
    "nvme2n1": "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0",
    "nvme2n2": "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0",
    "nvme2n3": "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0",
    "nvme3n1": "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0",
    "nvme0n1": "718858 4756 126591169 610199 17393472 2263624 852934096 36105327 0 0 0 0 0 0 0",
}
SECTOR = 512


class TestCollectNvmeFabricsDiskOctets(unittest.TestCase):
    """Throughput for fabrics LUNs reuses the EXISTING collectd_disk_disk_octets_0/_1.

    collectd reads /proc/diskstats and emits nothing for a fabrics head (its row is
    all-zero) nor for the hidden c-path (hidden=1, major 0). So the chart PromQL
    (irate(collectd_disk_disk_octets_*) * on(disk) group_left(wwid) node_disk_wwid)
    has no series to light. kvmagent backfills that same metric name for heads with a
    c-path sibling (mirrors the collectd_virt_memory backfill), so no new metric and no
    PromQL change are needed. Heads with no c-path (local PCIe) are left to collectd to
    avoid double-counting.
    """

    def _run(self):
        def fake_exists(path):
            if path == "/sys/block":
                return True
            if path == "/sys/class/scsi_disk":
                return False
            return False

        def fake_isdir(path):
            return path.startswith("/sys/block/") and path.endswith("/device")

        def fake_listdir(path):
            if path == "/sys/block":
                return list(SYS_BLOCK_ENTRIES)
            if path.startswith("/sys/block/") and path.endswith("/device"):
                head = path[len("/sys/block/"):-len("/device")]
                return list(SUBSYS_ENTRIES.get(head, []))
            return []

        def fake_read_file_strip(path):
            if path.startswith("/sys/block/") and path.endswith("/stat"):
                return STAT.get(path[len("/sys/block/"):-len("/stat")])
            if path.startswith("/sys/block/") and path.endswith("/dev"):
                return DEV_NODE.get(path[len("/sys/block/"):-len("/dev")])
            if path.startswith("/sys/block/") and path.endswith("/device/state"):
                return DEVICE_STATE.get(path[len("/sys/block/"):-len("/device/state")])
            if path.startswith("/sys/class/nvme/") and path.endswith("/state"):
                return CONTROLLER_STATE.get(path[len("/sys/class/nvme/"):-len("/state")])
            return None

        with mock.patch.object(prometheus.os.path, "exists", side_effect=fake_exists), \
                mock.patch.object(prometheus.os.path, "isdir", side_effect=fake_isdir), \
                mock.patch.object(prometheus.os, "listdir", side_effect=fake_listdir), \
                mock.patch.object(prometheus.linux, "read_file_strip",
                                  side_effect=fake_read_file_strip), \
                mock.patch.object(prometheus, "bash_ro", return_value=(1, "")), \
                mock.patch.object(prometheus, "sblk_pv_vg", {}):
            families = prometheus.collect_disk_stat()

        return {f.name: f for f in families}

    def _octets(self):
        by_name = self._run()
        return _sample_pairs(by_name["collectd_disk_disk_octets_0"]), \
            _sample_pairs(by_name["collectd_disk_disk_octets_1"])

    def test_cpath_bytes_summed_onto_head(self):
        # WHY: the fabrics head nvme2n1 reports zero in its own stat; the real
        # throughput collectd needs lives on the hidden c-path nvme2c2n1. Pin
        # that we surface it under the head name so the wwid join can find it.
        read, write = self._octets()
        self.assertEqual(16606770 * SECTOR, read.get("nvme2n1"),
                         "nvme2n1 read bytes must equal its c-path read sectors*512")
        self.assertEqual(665 * SECTOR, write.get("nvme2n1"))
        self.assertEqual(7622338 * SECTOR, read.get("nvme3n1"))
        self.assertEqual(3761542 * SECTOR, write.get("nvme3n1"))

    def test_cpath_ops_summed_onto_head(self):
        # WHY: the IOPS charts read collectd_disk_disk_ops_{0,1}. The head's own
        # stat is all-zero, so without backfill the IOPS chart is empty even when
        # bytes work. ops_0=read I/Os (stat f0), ops_1=write I/Os (stat f4).
        by_name = self._run()
        read_ops = _sample_pairs(by_name["collectd_disk_disk_ops_0"])
        write_ops = _sample_pairs(by_name["collectd_disk_disk_ops_1"])
        self.assertEqual(75884, read_ops.get("nvme2n1"))
        self.assertEqual(665, write_ops.get("nvme2n1"))
        self.assertEqual(90312, read_ops.get("nvme3n1"))
        self.assertEqual(20255, write_ops.get("nvme3n1"))

    def test_cpath_io_time_summed_onto_head(self):
        # WHY: the latency chart is (delta(io_time_0)+delta(io_time_1)) /
        # (delta(ops_0)+delta(ops_1)). io_time_0=read ticks ms (stat f3),
        # io_time_1=write ticks ms (stat f7). Without these the latency chart is empty.
        by_name = self._run()
        read_time = _sample_pairs(by_name["collectd_disk_disk_io_time_0"])
        write_time = _sample_pairs(by_name["collectd_disk_disk_io_time_1"])
        self.assertEqual(150201, read_time.get("nvme2n1"))
        self.assertEqual(264, write_time.get("nvme2n1"))
        self.assertEqual(126462, read_time.get("nvme3n1"))
        self.assertEqual(283129, write_time.get("nvme3n1"))

    def test_head_label_not_cpath_label(self):
        # WHY: the join key is the LunVO head name (nvme2n1); emitting the c-path
        # name would never match. The metric must be labelled by head only.
        read, write = self._octets()
        for cpath in ("nvme2c2n1", "nvme2c2n2", "nvme2c2n3", "nvme3c3n1"):
            self.assertNotIn(cpath, read)
            self.assertNotIn(cpath, write)

    def test_local_pcie_head_not_emitted(self):
        # WHY: nvme0n1 is a local single-path device whose real stat collectd
        # already collects. It has no c-path sibling, so this collector must not
        # emit it (that would double-count against collectd).
        read, write = self._octets()
        self.assertNotIn("nvme0n1", read)
        self.assertNotIn("nvme0n1", write)


if __name__ == "__main__":
    unittest.main(verbosity=2)

