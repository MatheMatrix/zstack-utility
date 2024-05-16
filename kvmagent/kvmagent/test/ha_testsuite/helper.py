import mock
from kvmagent.plugins import ha_plugin

unittest_filesystem_mount_point = ha_plugin.FileSyetemMountPoint(
    "/tmp", "/tmp", True, "nfsv4")

def mock_vm_running_on_ps(vm_uuid_list):
    # mock return value of find_ps_running_vm
    ha_plugin.find_ps_running_vm = mock.Mock(return_value=vm_uuid_list)
