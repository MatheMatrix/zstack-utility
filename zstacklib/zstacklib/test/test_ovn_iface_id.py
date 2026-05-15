import unittest
import sys
import types

sys.modules.setdefault("simplejson", types.ModuleType("simplejson"))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

bash = types.ModuleType("zstacklib.utils.bash")
bash.in_bash = lambda fn: fn
sys.modules.setdefault("zstacklib.utils.bash", bash)

log = types.ModuleType("zstacklib.utils.log")
log.get_logger = lambda name: type("Logger", (), {
    "debug": lambda self, *args, **kwargs: None,
    "error": lambda self, *args, **kwargs: None,
    "info": lambda self, *args, **kwargs: None,
    "warn": lambda self, *args, **kwargs: None,
})()
sys.modules.setdefault("zstacklib.utils.log", log)
sys.modules.setdefault("zstacklib.utils.iproute", types.ModuleType("zstacklib.utils.iproute"))
sys.modules.setdefault("zstacklib.utils.linux", types.ModuleType("zstacklib.utils.linux"))

from zstacklib.utils import ovn


class TestOvnIfaceId(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.original_bash_r = ovn.bash.bash_r if hasattr(ovn.bash, "bash_r") else None
        ovn.bash.bash_r = self.commands.append

    def tearDown(self):
        if self.original_bash_r is None:
            del ovn.bash.bash_r
        else:
            ovn.bash.bash_r = self.original_bash_r

    def test_zcf_3603_uses_explicit_iface_id(self):
        self.assertEqual(
            "zns-segment-port-iface",
            ovn.getInterfaceId("vnic1.0", "cloud-nic-uuid", "zns-segment-port-iface")
        )

    def test_zcf_3603_keeps_ovn_fallback_iface_id(self):
        self.assertEqual(
            "vnic1.0_cloud-nic-uuid",
            ovn.getInterfaceId("vnic1.0", "cloud-nic-uuid")
        )

    def test_zcf_3603_quotes_explicit_iface_id_in_add_port_command(self):
        ovn.VsCtl().addVnic(
            "vnic1.0", "cloud-nic-uuid", "vm-uuid", ifaceId="zns iface; touch /tmp/bad"
        )

        self.assertEqual(1, len(self.commands))
        self.assertIn("external-ids:iface-id='zns iface; touch /tmp/bad'", self.commands[0])


if __name__ == "__main__":
    unittest.main()
