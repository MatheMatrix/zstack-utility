import inspect
import sys
import unittest
try:
    import mock
except ImportError:
    from unittest import mock
try:
    from types import SimpleNamespace
except ImportError:
    class SimpleNamespace(object):
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

from kvmagent.plugins import deip
from kvmagent.plugins.deip import DEip, Eip


def _make_eip(ipVersion=4):
    eip = mock.MagicMock()
    eip.nicName = "vnic1.0"
    eip.eipUuid = "abcdef123456789"
    eip.publicBridgeName = "br_eth0"
    eip.vmBridgeName = "br_eth1"
    eip.vip = "192.168.1.100"
    eip.vipNetmask = "255.255.255.0"
    eip.vipGateway = "192.168.1.1"
    eip.vipPrefixLen = 64
    eip.nicGateway = "10.0.0.1"
    eip.nicNetmask = "255.255.255.0"
    eip.nicPrefixLen = 24
    eip.nicIp = "10.0.0.100"
    eip.nicMac = "00:0c:29:aa:bb:cc"
    eip.vmUuid = "vm-uuid-1234"
    eip.vipUuid = "vip-uuid-5678"
    eip.ipVersion = ipVersion
    eip.addfdb = False
    eip.physicalNic = "eth0"
    eip.skipArpCheck = True
    if ipVersion == 6:
        eip.vip = "fd00:1::100"
        eip.vipGateway = "fd00:1::1"
        eip.nicGateway = "fd00:2::1"
        eip.nicIp = "fd00:2::100"
    return eip


# EIP_UUID[-9:] = '123456789'
# PUB_ODEV = '123456789_eo', PUB_IDEV = '123456789_ei'
# PRI_ODEV = '123456789_o',  PRI_IDEV = '123456789_i'
# NIC_NAME = 'vnic1.0'


def _make_fake_process(executed_cmds):
    """Create a fake shell.get_process that captures resolved commands."""

    def fake_get_process(*args, **kwargs):
        cmd_path = args[0] if args else kwargs.get("cmd_path")
        proc = mock.MagicMock()

        def communicate(*args, **kwargs):
            command = args[0].decode() if args and isinstance(args[0], bytes) else cmd_path
            executed_cmds.append(command)
            # ip link show -> return a MAC for GATEWAY_MAC resolution
            if "ip link show" in command and "awk" in command:
                proc.returncode = 0
                return (b"    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff\n", b"")
            # ip -o -f inet addr show -> return a CIDR for perf monitor
            if "ip -o -f inet addr show" in command:
                proc.returncode = 0
                return (b"10.0.0.100/24\n", b"")
            # ip -o -f inet6 addr show
            if "ip -o -f inet6 addr show" in command:
                proc.returncode = 0
                return (b"fd00:2::100/64\n", b"")
            if "ip -o -4 addr show dev" in command:
                proc.returncode = 0
                return (b"10.0.0.1\n", b"")
            if "brctl show" in command or "route | grep -w default" in command:
                proc.returncode = 1
                return ("", "")
            # ebtables -L ... --Lx -> return empty (no existing jump rules to old chains)
            if "--Lx" in command:
                proc.returncode = 0
                return ("", "")
            # default: success with empty output
            proc.returncode = 0
            return ("", "")

        proc.communicate = communicate
        proc.returncode = 0
        return proc

    return fake_get_process


def _apply_patchers():
    return [
        mock.patch("kvmagent.plugins.deip.EBTABLES_CMD", "ebtables", create=True),
        mock.patch("kvmagent.plugins.deip.IPTABLES_CMD", "iptables", create=True),
        mock.patch("kvmagent.plugins.deip.IP6TABLES_CMD", "ip6tables"),
        mock.patch(
            "kvmagent.plugins.deip.ip.removeZeroFromMacAddress",
            return_value="0:c:29:aa:bb:cc",
        ),
    ]


class _ApplyEipTestBase(unittest.TestCase):
    """Base class that sets up mocks and runs apply_eip, capturing all shell commands."""

    IP_VERSION = 4  # override in subclass for v6

    def setUp(self):
        self.executed_cmds = []

        # Start common patches
        self._patchers = _apply_patchers()
        self._patchers.append(
            mock.patch(
                "zstacklib.utils.shell.get_process",
                side_effect=_make_fake_process(self.executed_cmds),
            )
        )
        self._patchers.append(
            mock.patch(
                "kvmagent.plugins.deip.bash_o",
                side_effect=lambda command: (
                    "aa:bb:cc:dd:ee:ff" if "ip link show" in command else
                    "fd00:2::100/64" if "-o -f inet6" in command else
                    "10.0.0.100/24" if "-o -f inet" in command else
                    ""
                ),
            )
        )
        for p in self._patchers:
            p.start()

        # Mock iproute
        self.patcher_iproute = mock.patch("kvmagent.plugins.deip.iproute")
        self.mock_iproute = self.patcher_iproute.start()
        self.mock_iproute.IpNetnsShell.list_netns.return_value = []
        self.mock_iproute.IpNetnsShell.return_value.get_mac.return_value = (
            None  # force create
        )

        # Mock linux
        self.patcher_linux = mock.patch("kvmagent.plugins.deip.linux")
        self.mock_linux = self.patcher_linux.start()
        self.mock_linux.is_network_device_existing.return_value = False
        self.mock_linux.netmask_to_cidr.return_value = 24
        self.mock_linux.MAX_MTU_OF_VNIC = 65000

        self.patcher_bash_errorout = mock.patch(
            "kvmagent.plugins.deip.bash_errorout", wraps=deip.bash_errorout
        )
        self.mock_bash_errorout = self.patcher_bash_errorout.start()

        # Run the undecorated method so tests don't depend on real file/thread locks.
        eip = _make_eip(ipVersion=self.IP_VERSION)
        eip_cmd = Eip()
        self._apply_eip(eip_cmd, eip)

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self.patcher_iproute.stop()
        self.patcher_linux.stop()
        self.patcher_bash_errorout.stop()

    def _has_cmd(self, pattern):
        return any(pattern in cmd for cmd in self.executed_cmds)

    def _cmds_matching(self, pattern):
        return [cmd for cmd in self.executed_cmds if pattern in cmd]

    def _call_unwrapped_method(self, obj, method_name, *args, **kwargs):
        method = getattr(type(obj), method_name)
        if hasattr(inspect, "unwrap"):
            method = inspect.unwrap(method)
        else:
            while method.func_closure:
                wrapped = [
                    cell.cell_contents for cell in method.func_closure
                    if inspect.isfunction(cell.cell_contents)
                ]
                if not wrapped:
                    break
                method = wrapped[0]
        method(obj, *args, **kwargs)

    def _apply_eip(self, eip_cmd, eip):
        self._call_unwrapped_method(eip_cmd, "apply_eip", eip)


class TestPrepareEip(_ApplyEipTestBase):
    def _apply_eip(self, eip_cmd, eip):
        self._call_unwrapped_method(eip_cmd, "apply_eip", eip, False)

    def test_interface_alias_keeps_existing_schema(self):
        aliases = [
            call[1]["alias"]
            for call in self.mock_iproute.set_link_attribute.call_args_list
            if "alias" in call[1]
        ]
        self.assertTrue(aliases)
        self.assertFalse(any("vip_gateway:" in alias for alias in aliases))

    def test_prepare_keeps_inner_up_and_public_outer_down(self):
        namespace = self.mock_iproute.IpNetnsShell.return_value
        self.assertIn(mock.call("123456789_ei"), namespace.set_link_up.call_args_list)
        self.assertNotIn(
            mock.call("123456789_eo"),
            self.mock_iproute.set_link_up.call_args_list,
            "Passive prepare must not activate the public outer interface",
        )
        self.assertFalse(
            any("PUB_IDEV}} down" in call[0][0]
                for call in self.mock_bash_errorout.call_args_list),
            "Passive prepare must keep the namespace interface configured",
        )

    def test_repeated_prepare_never_activates_existing_public_outer(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = [
            "br_eth0_192_168_1_100"
        ]
        self.mock_iproute.IpNetnsShell.return_value.get_mac.return_value = (
            "aa:bb:cc:dd:ee:ff"
        )
        self.mock_linux.is_network_device_existing.return_value = True
        self.mock_iproute.set_link_up.reset_mock()
        self.mock_iproute.set_link_down.reset_mock()

        self._apply_eip(Eip(), _make_eip())

        self.mock_iproute.set_link_down.assert_any_call("123456789_eo")
        self.assertNotIn(
            mock.call("123456789_eo"),
            self.mock_iproute.set_link_up.call_args_list,
        )

    def test_does_not_announce_public_vip(self):
        self.assertFalse(
            self._has_cmd("arping -q -A"),
            "Passive prepare must not announce the public VIP",
        )

    def test_does_not_announce_private_gateway(self):
        self.assertFalse(
            self._has_cmd("arping -q -U"),
            "Passive prepare must not change the VM gateway MAC cache",
        )


class TestEipPublicInterfaceState(unittest.TestCase):
    def setUp(self):
        self.eip = _make_eip()
        self.executed_cmds = []
        self.iproute_patcher = mock.patch("kvmagent.plugins.deip.iproute")
        self.mock_iproute = self.iproute_patcher.start()
        self.linux_patcher = mock.patch("kvmagent.plugins.deip.linux")
        self.mock_linux = self.linux_patcher.start()
        self.mock_linux.is_network_device_existing.return_value = True
        self.process_patcher = mock.patch(
            "zstacklib.utils.shell.get_process",
            side_effect=_make_fake_process(self.executed_cmds),
        )
        self.process_patcher.start()
        self.bash_o_patcher = mock.patch(
            "kvmagent.plugins.deip.bash_o", return_value="10.0.0.1"
        )
        self.bash_o_patcher.start()

    def tearDown(self):
        self.bash_o_patcher.stop()
        self.process_patcher.stop()
        self.linux_patcher.stop()
        self.iproute_patcher.stop()

    def _set_state(self, active):
        Eip().set_public_interface_state(
            "br_eth0_192_168_1_100",
            self.eip.eipUuid,
            self.eip.vip,
            self.eip.ipVersion,
            active,
            active,
            self.eip.vipGateway,
        )

    def test_enable_is_idempotent_and_announces_vip(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = [
            "br_eth0_192_168_1_100"
        ]
        self.mock_iproute.IpNetnsShell.return_value.get_mac.return_value = (
            "aa:bb:cc:dd:ee:ff"
        )

        self._set_state(True)

        self.mock_iproute.set_link_up.assert_called_once_with("123456789_eo")
        self.assertTrue(any("arping -q -A" in cmd for cmd in self.executed_cmds))
        self.assertTrue(any("arping -q -U" in cmd for cmd in self.executed_cmds))

    def test_public_and_private_announcements_run_in_parallel_and_wait(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = [
            "br_eth0_192_168_1_100"
        ]
        self.mock_iproute.IpNetnsShell.return_value.get_mac.return_value = (
            "aa:bb:cc:dd:ee:ff"
        )

        self._set_state(True)

        announce_commands = [
            command for command in self.executed_cmds
            if "arping -q -A" in command and "arping -q -U" in command
        ]
        self.assertEqual(1, len(announce_commands))
        self.assertIn(" & ", announce_commands[0])
        self.assertTrue(announce_commands[0].endswith(" & wait"))

    def test_disable_missing_namespace_is_idempotent(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = []

        self._set_state(False)

        self.assertFalse(
            self.mock_iproute.set_link_down.called
        )

    def test_disable_sets_public_outer_down(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = [
            "br_eth0_192_168_1_100"
        ]
        self.mock_iproute.IpNetnsShell.return_value.get_mac.return_value = (
            "aa:bb:cc:dd:ee:ff"
        )

        self._set_state(False)

        self.mock_iproute.set_link_down.assert_called_once_with("123456789_eo")

    def test_enable_missing_namespace_fails(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = []

        with self.assertRaisesRegexp(Exception, "cannot find EIP namespace"):
            self._set_state(True)

    def test_enable_incomplete_namespace_fails_before_public_interface_is_up(self):
        self.mock_iproute.IpNetnsShell.list_netns.return_value = [
            "br_eth0_192_168_1_100"
        ]
        self.mock_iproute.IpNetnsShell.return_value.get_mac.side_effect = [
            "aa:bb:cc:dd:ee:ff",
            None,
        ]

        with self.assertRaisesRegexp(Exception, "cannot find EIP private interface"):
            self._set_state(True)

        self.mock_iproute.set_link_up.assert_not_called()


class TestEipMigrationEvent(unittest.TestCase):
    def setUp(self):
        self.libvirt = SimpleNamespace(
            VIR_DOMAIN_EVENT_STARTED=2,
            VIR_DOMAIN_EVENT_STARTED_MIGRATED=1,
            VIR_DOMAIN_EVENT_RESUMED=4,
            VIR_DOMAIN_EVENT_RESUMED_MIGRATED=1,
            VIR_DOMAIN_EVENT_STOPPED=5,
            VIR_DOMAIN_EVENT_STOPPED_MIGRATED=3,
            VIR_DOMAIN_RUNNING=1,
            VIR_DOMAIN_PAUSED=3,
        )
        self.plugin = DEip()
        self.domain = mock.MagicMock()
        self.domain.name.return_value = "vm-uuid-1234"

    def _dispatch(self, event, detail, domain_state=None):
        if domain_state is not None:
            self.domain.state.return_value = (domain_state, 0)
        with mock.patch.dict(sys.modules, {"libvirt": self.libvirt}):
            with mock.patch(
                "kvmagent.plugins.deip.thread.ThreadFacade.run_in_thread"
            ) as run_in_thread:
                self.plugin._on_vm_lifecycle_event(
                    None, self.domain, event, detail, None
                )
                return run_in_thread

    def test_source_stopped_migrated_disables_eip(self):
        run_in_thread = self._dispatch(
            self.libvirt.VIR_DOMAIN_EVENT_STOPPED,
            self.libvirt.VIR_DOMAIN_EVENT_STOPPED_MIGRATED,
        )

        run_in_thread.assert_called_once_with(
            self.plugin._set_eips_public_interface_state_by_vm_uuid,
            ("vm-uuid-1234", False),
        )

    def test_destination_resumed_migrated_enables_eip(self):
        run_in_thread = self._dispatch(
            self.libvirt.VIR_DOMAIN_EVENT_RESUMED,
            self.libvirt.VIR_DOMAIN_EVENT_RESUMED_MIGRATED,
        )

        run_in_thread.assert_called_once_with(
            self.plugin._set_eips_public_interface_state_by_vm_uuid,
            ("vm-uuid-1234", True),
        )

    def test_started_migrated_only_enables_running_domain(self):
        paused = self._dispatch(
            self.libvirt.VIR_DOMAIN_EVENT_STARTED,
            self.libvirt.VIR_DOMAIN_EVENT_STARTED_MIGRATED,
            self.libvirt.VIR_DOMAIN_PAUSED,
        )
        paused.assert_not_called()

        running = self._dispatch(
            self.libvirt.VIR_DOMAIN_EVENT_STARTED,
            self.libvirt.VIR_DOMAIN_EVENT_STARTED_MIGRATED,
            self.libvirt.VIR_DOMAIN_RUNNING,
        )
        running.assert_called_once()

    def test_unrelated_event_is_ignored(self):
        run_in_thread = self._dispatch(
            self.libvirt.VIR_DOMAIN_EVENT_STOPPED,
            0,
        )

        run_in_thread.assert_not_called()

    def test_parser_ignores_transitional_gateway_metadata(self):
        alias = (
            "eip:abcdef123456789,eip_addr:192.168.1.100,"
            "vnic:vnic1.0,vnic_ip:10.0.0.100,"
            "vm:vm-uuid-1234,vip:vip-uuid-5678,"
            "vip_gateway:192.168.1.1"
        )

        parsed = Eip().parse_eip_string(alias)

        self.assertEqual(7, len(parsed))
        self.assertEqual("vip-uuid-5678", parsed[1])

    @mock.patch("kvmagent.plugins.deip.bash_o")
    def test_alias_metadata_recovers_all_eips_for_vm(self, bash_o):
        alias = (
            "eip:abcdef123456789,eip_addr:192.168.1.100,"
            "vnic:vnic1.0,vnic_ip:10.0.0.100,"
            "vm:vm-uuid-1234,vip:vip-uuid-5678"
        )
        other_vm_alias = (
            "eip:other987654321,eip_addr:192.168.1.101,"
            "vnic:vnic2.0,vnic_ip:10.0.0.101,"
            "vm:vm-uuid-5678,vip:vip-uuid-9876"
        )
        bash_o.return_value = "1: dev0 alias %s\n2: dev1 alias %s\n3: dev2 alias %s" % (
            alias, alias, other_vm_alias)

        with mock.patch.object(Eip, "find_namespace_name_by_eip",
                               return_value="br_eth0_192_168_1_100") as find_namespace:
            with mock.patch.object(
                Eip,
                "set_public_interface_state",
            ) as set_state:
                with mock.patch.object(Eip, "announce_public_interface") as announce:
                    with mock.patch(
                        "kvmagent.plugins.deip.thread.ThreadFacade.run_in_thread"
                    ) as run_in_thread:
                        self.plugin._set_eips_public_interface_state_by_vm_uuid(
                            "vm-uuid-1234", True
                        )

        find_namespace.assert_called_once_with(
            "192.168.1.100", 4, "abcdef123456789"
        )
        set_state.assert_called_once_with(
            "br_eth0_192_168_1_100",
            "abcdef123456789",
            "192.168.1.100",
            4,
            True,
            False,
            announce=False,
        )
        run_in_thread.assert_called_once_with(
            announce,
            ("br_eth0_192_168_1_100", "abcdef123456789", "192.168.1.100", 4),
        )

    @mock.patch("kvmagent.plugins.deip.bash_o")
    def test_source_event_disables_only_matching_vm_without_announcement(self, bash_o):
        matching_alias = (
            "eip:abcdef123456789,eip_addr:192.168.1.100,"
            "vnic:vnic1.0,vnic_ip:10.0.0.100,"
            "vm:vm-uuid-1234,vip:vip-uuid-5678"
        )
        other_vm_alias = (
            "eip:other987654321,eip_addr:192.168.1.101,"
            "vnic:vnic2.0,vnic_ip:10.0.0.101,"
            "vm:vm-uuid-5678,vip:vip-uuid-9876"
        )
        bash_o.return_value = "%s\n%s" % (matching_alias, other_vm_alias)

        with mock.patch.object(Eip, "find_namespace_name_by_eip",
                               return_value="br_eth0_192_168_1_100"):
            with mock.patch.object(Eip, "set_public_interface_state") as set_state:
                with mock.patch(
                    "kvmagent.plugins.deip.thread.ThreadFacade.run_in_thread"
                ) as run_in_thread:
                    self.plugin._set_eips_public_interface_state_by_vm_uuid(
                        "vm-uuid-1234", False
                    )

        set_state.assert_called_once_with(
            "br_eth0_192_168_1_100",
            "abcdef123456789",
            "192.168.1.100",
            4,
            False,
            False,
            announce=False,
        )
        run_in_thread.assert_not_called()



if __name__ == "__main__":
    unittest.main()
