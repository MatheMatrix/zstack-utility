import unittest

import mock

from kvmagent.plugins import vm_plugin


class MigrateCmd(object):
    vmUuid = 'vm-uuid'
    destHostManagementIp = '10.0.0.2'
    destHostIp = '172.24.0.2'


class TestMigrateVmFalseFailure(unittest.TestCase):
    def setUp(self):
        self.cmd = MigrateCmd()

    @mock.patch.object(vm_plugin, 'get_vm_by_uuid')
    @mock.patch.object(vm_plugin, 'get_connect')
    def test_destination_running_confirms_false_failure(self, get_connect,
                                                        get_vm_by_uuid):
        conn = mock.MagicMock()
        get_connect.return_value = conn
        get_vm_by_uuid.return_value = mock.Mock(
            state=vm_plugin.Vm.VM_STATE_RUNNING)

        self.assertTrue(vm_plugin.Vm.is_running_on_destination(self.cmd))
        get_connect.assert_called_once_with('10.0.0.2')
        get_vm_by_uuid.assert_called_once_with('vm-uuid', False, conn)
        conn.close.assert_called_once_with()

    @mock.patch.object(vm_plugin, 'get_vm_by_uuid')
    @mock.patch.object(vm_plugin, 'get_connect')
    def test_destination_not_running_preserves_failure(self, get_connect,
                                                       get_vm_by_uuid):
        get_connect.return_value = mock.MagicMock()
        get_vm_by_uuid.return_value = mock.Mock(
            state=vm_plugin.Vm.VM_STATE_PAUSED)

        self.assertFalse(vm_plugin.Vm.is_running_on_destination(self.cmd))

    @mock.patch.object(vm_plugin, 'get_vm_by_uuid', return_value=None)
    @mock.patch.object(vm_plugin, 'get_connect')
    def test_missing_destination_preserves_failure(self, get_connect,
                                                   get_vm_by_uuid):
        get_connect.return_value = mock.MagicMock()

        self.assertFalse(vm_plugin.Vm.is_running_on_destination(self.cmd))

    @mock.patch.object(vm_plugin, 'get_connect',
                       side_effect=Exception('connect failed'))
    def test_destination_lookup_error_keeps_false_failure_recovery(self,
                                                                   get_connect):
        self.assertTrue(vm_plugin.Vm.is_running_on_destination(self.cmd))


if __name__ == '__main__':
    unittest.main()
