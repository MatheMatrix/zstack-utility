import mock

from kvmagent.plugins import vm_plugin
from unittest import TestCase


class TestVmStopStrategy(TestCase):
    def test_grace_stop_without_detected_os_uses_cold_strategy(self):
        cmd = vm_plugin.StopVmCmd()
        cmd.uuid = "test-vm"
        cmd.type = "grace"
        cmd.timeout = 120
        cmd.forceStopIfNoOperatingSystemDetected = True

        vm = mock.Mock()
        vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        vm.VM_STATE_SHUTDOWN = vm_plugin.Vm.VM_STATE_SHUTDOWN
        vm.check_if_vm_has_operating_system_by_memory_state.return_value = False

        plugin = vm_plugin.VmPlugin.__new__(vm_plugin.VmPlugin)
        plugin.kill_vm = mock.Mock()

        with mock.patch.object(vm_plugin, "get_vm_by_uuid", return_value=vm), \
                mock.patch.object(vm_plugin.ovs, "isVmUseOpenvSwitch", return_value=False):
            plugin._stop_vm(cmd)

        vm.check_if_vm_has_operating_system_by_memory_state.assert_called_once_with()
        vm.stop.assert_called_once_with(strategy="cold")
