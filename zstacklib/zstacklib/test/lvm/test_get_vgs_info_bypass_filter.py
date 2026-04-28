"""Pin the LVM `--config` override on get_vgs_info().

APIDiscoverStrangePrimaryStorageMsg drives the sblk agent's
/sharedblock/vgs/info handler, which calls lvm.get_vgs_info(). On a
host that has not yet been connected to any sblk PS, /etc/lvm/lvm.conf
carries the distro-default narrow filter (e.g. only /dev/vda*, /dev/sda),
so newly attached iSCSI/FC/NVMe LUNs are rejected and `vgs` returns
nothing. We override devices/filter and devices/global_filter inline
via --config so this single read-only invocation sees every LVM2_member
block device on the host. -t keeps it test-mode (no metadata writes).
"""

import unittest

try:
    import mock
except ImportError:
    from unittest import mock

from zstacklib.utils import lvm
from zstacklib.utils import bash


class TestGetVgsInfoBypassFilter(unittest.TestCase):
    def test_vgs_command_carries_inline_accept_all_filter(self):
        captured = {}

        def fake_bash_roe(cmd):
            captured["cmd"] = cmd
            return 0, "", ""

        with mock.patch.object(lvm, "get_block_devices", return_value=[]), \
                mock.patch.object(bash, "bash_roe", side_effect=fake_bash_roe):
            lvm.get_vgs_info(tag="zs::sharedblock::init")

        cmd = captured["cmd"]
        # The command must still be the read-only vgs probe.
        self.assertIn("vgs ", cmd)
        self.assertIn("--nolocking", cmd)
        self.assertIn("--shared", cmd)
        self.assertIn("--foreign", cmd)
        self.assertIn(" -t ", cmd)
        # The filter override must be in-process via --config, NOT a
        # write to /etc/lvm/lvm.conf.
        self.assertIn("--config", cmd)
        self.assertIn('devices/filter=["a|.*|"]', cmd)
        self.assertIn('devices/global_filter=["a|.*|"]', cmd)


if __name__ == "__main__":
    unittest.main()
