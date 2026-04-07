"""
Test that lsblk_info() uses stable udev properties (ID_SERIAL, ID_WWN) to
override lsblk output, ensuring the same LUN gets identical identifiers on
different OS versions (see ZSTAC-69641).

Background:
  - C76:  lsblk maps WWN = ID_WWN,                SERIAL = ID_SERIAL_SHORT
  - H84R: lsblk maps WWN = ID_WWN_WITH_EXTENSION, SERIAL = ID_SCSI_SERIAL
  Using udev ID_SERIAL / ID_WWN directly produces consistent values on both.
"""

import unittest
import mock
from zstacklib.utils import lvm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lsblk_output(name="sda", vendor="VENDOR", model="MODEL",
                       wwn="0x6000d31000e56800extended",
                       serial="SCSI_UNIT_SERIAL", hctl="1:0:0:0",
                       dev_type="disk", size="10737418240"):
    """Build a lsblk --pair output line similar to what the real command returns."""
    return (
        'NAME="%s" VENDOR="%s" MODEL="%s" WWN="%s" SERIAL="%s" '
        'HCTL="%s" TYPE="%s" SIZE="%s"\n'
        % (name, vendor, model, wwn, serial, hctl, dev_type, size)
    )


UDEV_OUTPUT_WITH_SERIAL_AND_WWN = """\
DEVNAME=/dev/sda
DEVTYPE=disk
ID_BUS=scsi
ID_SERIAL=360000d31000e56800000000000000010
ID_SERIAL_SHORT=0000d31000e56800000000000000010
ID_WWN=0x6000d31000e56800
ID_WWN_WITH_EXTENSION=0x6000d31000e568000000000000000010
ID_TYPE=disk
"""

UDEV_OUTPUT_WITHOUT_SERIAL = """\
DEVNAME=/dev/sdb
DEVTYPE=disk
ID_TYPE=disk
"""


# ---------------------------------------------------------------------------
# Tests for get_udev_serial_and_wwn
# ---------------------------------------------------------------------------

class TestGetUdevSerialAndWwn(unittest.TestCase):

    def test_parses_serial_and_wwn_correctly(self):
        with mock.patch("zstacklib.utils.bash.bash_ro",
                        return_value=(0, UDEV_OUTPUT_WITH_SERIAL_AND_WWN)):
            serial, wwn = lvm.get_udev_serial_and_wwn("/dev/sda")

        self.assertEqual(serial, "360000d31000e56800000000000000010")
        self.assertEqual(wwn, "0x6000d31000e56800")

    def test_returns_none_when_udev_fails(self):
        with mock.patch("zstacklib.utils.bash.bash_ro",
                        return_value=(1, "")):
            serial, wwn = lvm.get_udev_serial_and_wwn("/dev/sda")

        self.assertIsNone(serial)
        self.assertIsNone(wwn)

    def test_returns_none_when_fields_missing(self):
        with mock.patch("zstacklib.utils.bash.bash_ro",
                        return_value=(0, UDEV_OUTPUT_WITHOUT_SERIAL)):
            serial, wwn = lvm.get_udev_serial_and_wwn("/dev/sdb")

        self.assertIsNone(serial)
        self.assertIsNone(wwn)

    def test_returns_none_when_output_empty(self):
        with mock.patch("zstacklib.utils.bash.bash_ro",
                        return_value=(0, "")):
            serial, wwn = lvm.get_udev_serial_and_wwn("/dev/sda")

        self.assertIsNone(serial)
        self.assertIsNone(wwn)


# ---------------------------------------------------------------------------
# Tests for lsblk_info (integration with udev override)
# ---------------------------------------------------------------------------

class TestLsblkInfoUdevOverride(unittest.TestCase):
    """
    Verify that lsblk_info overrides the serial/wwn fields reported by lsblk
    with the stable values from udev, so the same LUN looks the same on C76 and H84R.
    """

    def _run_lsblk_info(self, lsblk_wwn, lsblk_serial,
                        udev_wwn, udev_serial):
        """Helper: mock lsblk + udev and return the resulting struct."""
        lsblk_out = _make_lsblk_output(wwn=lsblk_wwn, serial=lsblk_serial)
        udev_out_lines = "DEVNAME=/dev/sda\n"
        if udev_serial:
            udev_out_lines += "ID_SERIAL=%s\n" % udev_serial
        if udev_wwn:
            udev_out_lines += "ID_WWN=%s\n" % udev_wwn

        def fake_bash_roe(cmd, *args, **kwargs):
            return 0, lsblk_out, ""

        def fake_bash_ro(cmd, *args, **kwargs):
            return 0, udev_out_lines

        with mock.patch("zstacklib.utils.bash.bash_roe", side_effect=fake_bash_roe), \
             mock.patch("zstacklib.utils.bash.bash_ro", side_effect=fake_bash_ro):
            return lvm.lsblk_info("sda")

    def test_udev_serial_overrides_lsblk_serial(self):
        """lsblk SERIAL (OS-specific) should be replaced by udev ID_SERIAL."""
        s = self._run_lsblk_info(
            lsblk_wwn="0x6000d31000e568000000000000000010",  # ID_WWN_WITH_EXTENSION (H84R)
            lsblk_serial="SCSI_UNIT_SERIAL",                 # ID_SCSI_SERIAL (H84R)
            udev_wwn="0x6000d31000e56800",                   # stable ID_WWN
            udev_serial="360000d31000e56800000000000000010",  # stable ID_SERIAL
        )
        self.assertEqual(s.serial, "360000d31000e56800000000000000010")
        self.assertEqual(s.wwn, "0x6000d31000e56800")

    def test_same_lun_serial_consistent_across_os(self):
        """
        Simulate the same LUN appearing on C76 vs H84R.
        lsblk produces different serial/wwn, but udev ID_SERIAL/ID_WWN is the same.
        lsblk_info should always return the udev-based values.
        """
        udev_serial = "360000d31000e56800000000000000010"
        udev_wwn = "0x6000d31000e56800"

        # C76 lsblk output
        s_c76 = self._run_lsblk_info(
            lsblk_wwn="0x6000d31000e56800",        # ID_WWN
            lsblk_serial="6000d31000e5680010",      # ID_SERIAL_SHORT
            udev_wwn=udev_wwn,
            udev_serial=udev_serial,
        )

        # H84R lsblk output (different!)
        s_h84r = self._run_lsblk_info(
            lsblk_wwn="0x6000d31000e568000000000000000010",  # ID_WWN_WITH_EXTENSION
            lsblk_serial="SCSI_UNIT_SERIAL_H84R",            # ID_SCSI_SERIAL
            udev_wwn=udev_wwn,
            udev_serial=udev_serial,
        )

        self.assertEqual(s_c76.serial, s_h84r.serial,
                         "serial should be identical on both OS versions")
        self.assertEqual(s_c76.wwn, s_h84r.wwn,
                         "wwn should be identical on both OS versions")

    def test_falls_back_to_lsblk_when_udev_unavailable(self):
        """When udev returns nothing, lsblk values should be kept as-is."""
        lsblk_out = _make_lsblk_output(wwn="0xABCDEF", serial="LSBLK_SERIAL")

        def fake_bash_roe(cmd, *args, **kwargs):
            return 0, lsblk_out, ""

        def fake_bash_ro(cmd, *args, **kwargs):
            return 1, ""   # udev failure

        with mock.patch("zstacklib.utils.bash.bash_roe", side_effect=fake_bash_roe), \
             mock.patch("zstacklib.utils.bash.bash_ro", side_effect=fake_bash_ro):
            s = lvm.lsblk_info("sda")

        self.assertEqual(s.serial, "LSBLK_SERIAL")
        self.assertEqual(s.wwn, "0xABCDEF")

    def test_returns_none_when_lsblk_fails(self):
        """lsblk_info should return None when lsblk command fails."""
        with mock.patch("zstacklib.utils.bash.bash_roe", return_value=(1, "", "error")):
            s = lvm.lsblk_info("sda")
        self.assertIsNone(s)


if __name__ == "__main__":
    unittest.main()
