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
        self.original_bash_roe = ovn.bash.bash_roe if hasattr(ovn.bash, "bash_roe") else None
        self.original_is_ovs_running = ovn.VsCtl.isOvsRunning
        ovn.bash.bash_r = self.commands.append

    def tearDown(self):
        if self.original_bash_r is None:
            del ovn.bash.bash_r
        else:
            ovn.bash.bash_r = self.original_bash_r
        if self.original_bash_roe is None and hasattr(ovn.bash, "bash_roe"):
            del ovn.bash.bash_roe
        elif self.original_bash_roe is not None:
            ovn.bash.bash_roe = self.original_bash_roe
        ovn.VsCtl.isOvsRunning = self.original_is_ovs_running

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

    def test_zcf_3603_quotes_safe_explicit_iface_id_in_add_port_command(self):
        ovn.VsCtl().addVnic(
            "vnic1.0", "cloud-nic-uuid", "vm-uuid", ifaceId="zns-segment:port_1.0"
        )

        self.assertEqual(1, len(self.commands))
        self.assertIn("external-ids:iface-id=zns-segment:port_1.0", self.commands[0])

    def test_zcf_3603_rejects_unsafe_explicit_iface_id(self):
        with self.assertRaises(ValueError):
            ovn.getInterfaceId("vnic1.0", "cloud-nic-uuid", "zns iface; touch /tmp/bad")

        with self.assertRaises(ValueError):
            ovn.VsCtl().addVnic(
                "vnic1.0", "cloud-nic-uuid", "vm-uuid", ifaceId="zns iface; touch /tmp/bad"
            )

        self.assertEqual(0, len(self.commands))

    def test_parse_ovs_map_keeps_commas_and_quotes_inside_value(self):
        parsed = ovn.VsCtl.parseOvsMap(
            r'{key1="value, with comma", key2=value2, key3="escaped \"quote\""}'
        )

        self.assertEqual("value, with comma", parsed["key1"])
        self.assertEqual("value2", parsed["key2"])
        self.assertEqual('escaped "quote"', parsed["key3"])

    def test_ensure_ovs_running_does_not_mask_ovsdb_restart_failure(self):
        ovn.VsCtl.isOvsRunning = lambda self: False

        def bash_roe(cmd):
            self.commands.append(cmd)
            if cmd == "systemctl restart ovsdb-server":
                return 1, "", "start failed"
            if cmd == "systemctl list-unit-files ovsdb-server.service --no-legend":
                return 0, "ovsdb-server.service enabled\n", ""
            raise AssertionError("unexpected command: %s" % cmd)

        ovn.bash.bash_roe = bash_roe

        ok, err = ovn.VsCtl().ensureOvsRunning()

        self.assertFalse(ok)
        self.assertIn("restart ovsdb-server failed", err)
        self.assertNotIn("systemctl restart openvswitch", self.commands)

    def test_ensure_ovs_running_falls_back_when_ovsdb_unit_is_absent(self):
        ovn.VsCtl.isOvsRunning = lambda self: False

        def bash_roe(cmd):
            self.commands.append(cmd)
            if cmd == "systemctl restart ovsdb-server":
                return 1, "", "Unit not found"
            if cmd == "systemctl list-unit-files ovsdb-server.service --no-legend":
                return 0, "", ""
            if cmd in ("systemctl restart openvswitch", "systemctl restart ovn-controller"):
                return 0, "", ""
            raise AssertionError("unexpected command: %s" % cmd)

        ovn.bash.bash_roe = bash_roe

        ok, err = ovn.VsCtl().ensureOvsRunning()

        self.assertTrue(ok)
        self.assertEqual("", err)
        self.assertIn("systemctl restart openvswitch", self.commands)


if __name__ == "__main__":
    unittest.main()
