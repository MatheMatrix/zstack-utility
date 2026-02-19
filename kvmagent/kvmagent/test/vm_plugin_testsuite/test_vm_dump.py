from kvmagent.plugins import vm_plugin
from kvmagent.test.utils import vm_utils, network_utils, pytest_utils
from kvmagent.test.utils.stub import *
from zstacklib.test.utils import misc
from zstacklib.utils import linux
from unittest import TestCase
from unittest.mock import patch, MagicMock

init_kvmagent()
vm_utils.init_vm_plugin()

__ENV_SETUP__ = {
    'self': {
    }
}


class TestVmPlugin(TestCase, vm_utils.VmPluginTestStub):
    @classmethod
    def setUpClass(cls):
        network_utils.create_default_bridge_if_not_exist()

    @env.test_for(handlers=[
        vm_plugin.VmPlugin.KVM_STOP_VM_PATH
    ])
    @pytest_utils.ztest_decorater
    def test_vm_stop_dump(self):
        vm_uuid, vm = self._create_vm()
        linux.rm_dir_force(vm_plugin.VM_CORE_DUMP_DIR)
        linux.mkdir(vm_plugin.VM_CORE_DUMP_DIR)
        rsp = vm_utils.stop_vm(vm_uuid, debug=True)

        vmcore_dump_path = vm_plugin.VM_CORE_DUMP_DIR + "/" + vm_uuid
        self.assertTrue(os.path.exists(vmcore_dump_path), "core dump file not exists")

        dir_size = linux.get_filesystem_folder_size(vm_plugin.VM_CORE_DUMP_DIR)
        self.assertTrue(dir_size > 0, "core dump file %s size is 0" % vmcore_dump_path)
        self.assertTrue(dir_size < 2 * 1024 * 1024 * 1024, "core dump file %s size is too large" % vmcore_dump_path)
        self._destroy_vm(vm_uuid)

    def test_dump_skipped_when_insufficient_disk_space(self):
        """_dump() must be skipped when free disk space is below VM_CORE_DUMP_MIN_FREE_DISK."""
        plugin = vm_plugin.VmPlugin()
        mock_vm = MagicMock()

        with patch('kvmagent.plugins.vm_plugin.os.path.exists', return_value=True), \
             patch('kvmagent.plugins.vm_plugin.linux.get_free_disk_size', return_value=1 * 1024 * 1024 * 1024), \
             patch('kvmagent.plugins.vm_plugin.linux.get_filesystem_folder_size', return_value=0), \
             patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid', return_value=mock_vm):
            plugin._dump('test-vm-uuid')
            mock_vm.dump_guest_memory.assert_not_called()

    def test_dump_skipped_when_dump_dir_at_limit(self):
        """_dump() must be skipped when dump dir total size reaches VM_CORE_DUMP_DIR_MAX_SIZE."""
        plugin = vm_plugin.VmPlugin()
        mock_vm = MagicMock()

        with patch('kvmagent.plugins.vm_plugin.os.path.exists', return_value=True), \
             patch('kvmagent.plugins.vm_plugin.linux.get_free_disk_size',
                   return_value=vm_plugin.VM_CORE_DUMP_MIN_FREE_DISK + 1), \
             patch('kvmagent.plugins.vm_plugin.linux.get_filesystem_folder_size',
                   return_value=vm_plugin.VM_CORE_DUMP_DIR_MAX_SIZE), \
             patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid', return_value=mock_vm):
            plugin._dump('test-vm-uuid')
            mock_vm.dump_guest_memory.assert_not_called()

    def test_dump_proceeds_when_disk_ok(self):
        """_dump() must call dump_guest_memory when disk space is sufficient."""
        plugin = vm_plugin.VmPlugin()
        mock_vm = MagicMock()

        with patch('kvmagent.plugins.vm_plugin.os.path.exists', return_value=True), \
             patch('kvmagent.plugins.vm_plugin.linux.get_free_disk_size',
                   return_value=vm_plugin.VM_CORE_DUMP_MIN_FREE_DISK + 1), \
             patch('kvmagent.plugins.vm_plugin.linux.get_filesystem_folder_size', return_value=0), \
             patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid', return_value=mock_vm):
            plugin._dump('test-vm-uuid')
            mock_vm.dump_guest_memory.assert_called_once()
