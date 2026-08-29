import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from zstacklib.utils.lvm_range import validate_pv_duplicate_audit


def _has_loop_lvm_capability():
    return (
        sys.version_info[0] >= 3 and os.name == "posix" and
        os.geteuid() == 0 and
        os.environ.get("ZSTACK_RUN_LVM_LOOP_TEST") == "1" and
        all(shutil.which(name) for name in
            ("blockdev", "losetup", "pvcreate", "pvs")))


@unittest.skipUnless(
    _has_loop_lvm_capability(),
    "set ZSTACK_RUN_LVM_LOOP_TEST=1 as root with losetup/LVM tools")
class DuplicatePvidLoopIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="zstack-pvid-clone-")
        self.loops = []

    def tearDown(self):
        for device in reversed(self.loops):
            if re.match(r"^/dev/loop[0-9]+$", device):
                subprocess.run(
                    ["losetup", "--detach", device],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30, check=False)
        shutil.rmtree(self.work, ignore_errors=True)

    def test_unfiltered_pvs_audit_rejects_a_cloned_pvid(self):
        original = os.path.join(self.work, "original.img")
        clone = os.path.join(self.work, "clone.img")
        with open(original, "wb") as stream:
            stream.truncate(64 * 1024 * 1024)

        first = self._attach(original)
        created = subprocess.run(
            ["pvcreate", "--yes", "--force", first],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=False)
        if created.returncode != 0:
            self.fail(
                "pvcreate failed for private loop[%s]: %s" %
                (first, created.stderr.decode("utf-8", "replace").strip()))
        shutil.copyfile(original, clone)
        second = self._attach(clone)

        pvid = subprocess.check_output(
            ["pvs", "--readonly", "--nolocking", "-t", "--noheadings",
             "-o", "pv_uuid", first],
            stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=30).decode("utf-8").strip()
        audit = json.loads(subprocess.check_output(
            ["pvs", "--readonly", "--nolocking", "-t", "--all",
             "--units", "b", "--nosuffix", "--reportformat", "json",
             "-o", "vg_uuid,pv_uuid,pv_name,pv_duplicate"],
            stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=30).decode("utf-8"))
        target = {"report": [{"pv": [{
            "pv_uuid": pvid,
            "pv_name": first,
        }]}]}

        with self.assertRaisesRegex(ValueError, "LVM_RANGE_PVID_DUPLICATE"):
            validate_pv_duplicate_audit(target, audit)
        names = [row.get("pv_name") for report in audit["report"]
                 for row in report.get("pv", [])
                 if row.get("pv_uuid", "").strip() == pvid]
        self.assertIn(first, names)
        self.assertIn(second, names)

    def _attach(self, path):
        try:
            device = subprocess.check_output(
                ["losetup", "--find", "--show", path],
                stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=30).decode("ascii").strip()
        except (OSError, subprocess.CalledProcessError) as error:
            self.skipTest("loop-device capability unavailable: %s" % error)
        if not re.match(r"^/dev/loop[0-9]+$", device):
            self.fail("losetup returned unsafe device path: %r" % device)
        self.loops.append(device)
        subprocess.run(
            ["blockdev", "--setrw", device],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=True)
        read_only = subprocess.check_output(
            ["blockdev", "--getro", device],
            stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=30).decode("ascii").strip()
        if read_only != "0":
            self.fail("private loop remained read-only: %s" % device)
        return device


if __name__ == "__main__":
    unittest.main()
