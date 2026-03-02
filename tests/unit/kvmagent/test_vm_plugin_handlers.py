# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
# pyright: reportAny=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportAttributeAccessIssue=false
"""Handler-level unit tests for kvmagent.plugins.vm_plugin."""
import json
import pytest
from unittest.mock import patch, MagicMock

from zstacklib.utils import http, jsonobject
from kvmagent.plugins import vm_plugin


def _make_req(body_dict=None):
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


vm_plugin.http = http
vm_plugin.jsonobject = jsonobject


def _make_vm_plugin():
    plugin = vm_plugin.VmPlugin.__new__(vm_plugin.VmPlugin)
    plugin.config = {}
    return plugin


@pytest.mark.kvmagent
class TestAttachIsoHandler:
    def test_attach_iso(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.attach_iso(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid')
        mock_vm.attach_iso.assert_called_once()


@pytest.mark.kvmagent
class TestDetachIsoHandler:
    def test_detach_iso(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.detach_iso(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid')
        mock_vm.detach_iso.assert_called_once()


@pytest.mark.kvmagent
class TestUpdateNicHandler:
    def test_update_nic(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmInstanceUuid': 'vm-uuid'})
        result = plugin.update_nic(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid')
        mock_vm.update_nic.assert_called_once()


@pytest.mark.kvmagent
class TestHardenConsoleHandler:
    def test_harden_console(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid', 'hostManagementIp': '10.0.0.1'})
        result = plugin.harden_console(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.harden_console.assert_called_once_with('10.0.0.1')


@pytest.mark.kvmagent
class TestCreateCephSecretKeyHandler:
    def test_create_ceph_secret_key(self):
        plugin = _make_vm_plugin()
        vm_plugin.VmPlugin._create_ceph_secret_key = MagicMock()

        req = _make_req({'userKey': 'secret', 'uuid': 'secret-uuid'})
        result = plugin.create_ceph_secret_key(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.VmPlugin._create_ceph_secret_key.assert_called_once_with('secret', 'secret-uuid')


@pytest.mark.kvmagent
class TestVmPriorityHandler:
    def test_vm_priority(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import linux
        linux.find_vm_pid_by_uuid = MagicMock(return_value=12345)
        linux.set_vm_priority = MagicMock()

        req = _make_req({
            'priorityConfigStructs': [
                {'vmUuid': 'vm-uuid', 'priority': 10},
            ]
        })
        result = plugin.vm_priority(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        linux.find_vm_pid_by_uuid.assert_called_once_with('vm-uuid')
        linux.set_vm_priority.assert_called_once()


@pytest.mark.kvmagent
class TestKvmResizeVolumeHandler:
    def test_kvm_resize_volume(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.touchQmpSocketWhenExists = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {'uuid': 'vol-uuid'}, 'size': 1024})
        result = plugin.kvm_resize_volume(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid', exception_if_not_existing=False)
        mock_vm.resize_volume.assert_called_once()
        vm_plugin.touchQmpSocketWhenExists.assert_called_once_with('vm-uuid')


@pytest.mark.kvmagent
class TestApplyMemoryBalloonHandler:
    def test_apply_memory_balloon(self):
        plugin = _make_vm_plugin()
        plugin.do_apply_memory_balloon_to_vm = MagicMock()

        req = _make_req({
            'vmUuids': ['vm-uuid'],
            'direction': 'Increase',
            'adjustPercent': 10,
            'vmReservedMemory': None,
        })
        result = plugin.apply_memory_balloon(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.do_apply_memory_balloon_to_vm.assert_called_once_with('vm-uuid', 'Increase', 10, 0)


@pytest.mark.kvmagent
class TestCleanFirmwareFlashHandler:
    def test_clean_firmware_flash(self):
        plugin = _make_vm_plugin()
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=None)
        plugin.clean_vm_firmware_flash = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.clean_firmware_flash(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.clean_vm_firmware_flash.assert_called_once_with('vm-uuid')


@pytest.mark.kvmagent
class TestChangeNicStateHandler:
    def test_change_nic_state(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid', 'state': 'enable'})
        result = plugin.change_nic_state(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.enable_nic.assert_called_once()


@pytest.mark.kvmagent
class TestDetachNicHandler:
    def test_detach_nic(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'nic': {'type': 'VNIC', 'uuid': 'nic-uuid'},
        })
        result = plugin.detach_nic(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid', False)
        mock_vm.detach_nic.assert_called_once()


@pytest.mark.kvmagent
class TestGetNicQosHandler:
    def test_get_nic_qos(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock(side_effect=['1000\n', '2000\n'])

        req = _make_req({'vmUuid': 'vm-uuid', 'internalName': 'eth0'})
        result = plugin.get_nic_qos(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['inbound'] == 1000 * 8 * 1024
        assert rsp['outbound'] == 2000 * 8 * 1024


@pytest.mark.kvmagent
class TestChangeVmPasswordHandler:
    def test_change_vm_password(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({
            'accountPerference': {
                'vmUuid': 'vm-uuid',
                'accountPassword': 'secret',
                'accountName': 'root',
            }
        })
        result = plugin.change_vm_password(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.change_vm_password.assert_called_once()
        assert rsp['accountPerference']['accountPassword'] == '******'


@pytest.mark.kvmagent
class TestCheckVolumeHandler:
    def test_check_volume(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({
            'uuid': 'vm-uuid',
            'volumes': [{'installPath': '/path/vol1'}, {'installPath': '/path/vol2'}],
        })
        result = plugin.check_volume(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert mock_vm._get_target_disk.call_count == 2


@pytest.mark.kvmagent
class TestDeleteConsoleFirewallRuleHandler:
    def test_delete_console_firewall_rule(self):
        plugin = _make_vm_plugin()
        mock_rule = MagicMock()
        vm_plugin.VncPortIptableRule = MagicMock(return_value=mock_rule)

        req = _make_req({'vmInternalId': 123, 'hostManagementIp': '10.0.0.2'})
        result = plugin.delete_console_firewall_rule(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_rule.delete.assert_called_once()


@pytest.mark.kvmagent
class TestGetIothreadPinHandler:
    def test_get_iothread_pin(self):
        plugin = _make_vm_plugin()
        plugin.get_iothread_info = MagicMock(return_value=[('1', '0-3'), ('2', '4-7')])

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.get_iothread_pin(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['ioThreadInfo'] == [
            {'ioThreadId': '1', 'ioThreadPin': '0-3'},
            {'ioThreadId': '2', 'ioThreadPin': '4-7'},
        ]


@pytest.mark.kvmagent
class TestQueryBlockJobStatusHandler:
    def test_query_block_job_status(self):
        plugin = _make_vm_plugin()
        vm_plugin.qmp.execute_qmp_command = MagicMock()
        with patch('time.sleep', return_value=None):
            req = _make_req({'vmUuid': 'vm-uuid'})
            result = plugin.query_block_job_status(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert vm_plugin.qmp.execute_qmp_command.call_count == 6


@pytest.mark.kvmagent
class TestSetEmulatorPinningHandler:
    def test_set_emulator_pinning(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock()

        req = _make_req({'uuid': 'vm-uuid', 'emulatorPinning': '0-3'})
        result = plugin.set_emulator_pinning(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        shell.call.assert_called_once_with('virsh emulatorpin vm-uuid  0-3')


@pytest.mark.kvmagent
class TestAttachSshKeyPairHandler:
    def test_attach_ssh_key_pair(self):
        plugin = _make_vm_plugin()
        plugin.do_attach_ssh_key_pair = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'publicKey': 'ssh-rsa AAA'})
        result = plugin.attach_ssh_key_pair(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.do_attach_ssh_key_pair.assert_called_once_with('vm-uuid', 'ssh-rsa AAA')


@pytest.mark.kvmagent
class TestDetachSshKeyPairHandler:
    def test_detach_ssh_key_pair(self):
        plugin = _make_vm_plugin()
        plugin.do_detach_ssh_key_pair = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'publicKey': 'ssh-rsa AAA'})
        result = plugin.detach_ssh_key_pair(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.do_detach_ssh_key_pair.assert_called_once_with('vm-uuid', 'ssh-rsa AAA')


@pytest.mark.kvmagent
class TestLogoutIscsiTargetHandler:
    def test_logout_iscsi_target(self):
        def _identity_lock(*_args, **_kwargs):
            def _decorator(func):
                return func
            return _decorator

        vm_plugin.lock.lock = _identity_lock
        import importlib
        reloaded = importlib.reload(vm_plugin)
        reloaded.http = http
        reloaded.jsonobject = jsonobject
        plugin = reloaded.VmPlugin.__new__(reloaded.VmPlugin)
        plugin.config = {}
        from zstacklib.utils import shell
        shell.call = MagicMock()

        req = _make_req({'target': 'iqn.test', 'hostname': '127.0.0.1', 'port': 3260})
        result = plugin.logout_iscsi_target(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        shell.call.assert_called_once_with(
            'iscsiadm  -m node  --targetname "iqn.test" --portal "127.0.0.1:3260" --logout'
        )


@pytest.mark.kvmagent
class TestSyncVmDeviceinfoHandler:
    def test_sync_vm_deviceinfo(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_vm_device_info = MagicMock(return_value=(['nic'], ['dev'], None))
        plugin.collect_vm_virtualizer_info = MagicMock()
        vm_plugin.pci.get_pci_passthrough_mapping = MagicMock(return_value={'host': 'guest'})
        vm_plugin.pci.get_mdev_passthrough_mapping = MagicMock(return_value={'mdev': 'info'})

        req = _make_req({'vmInstanceUuid': 'vm-uuid'})
        result = plugin.sync_vm_deviceinfo(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['pciDeviceInfos'] == {'guest': 'host'}
        assert rsp['mdevDeviceInfos'] == {'mdev': 'info'}
        plugin.get_vm_device_info.assert_called_once_with('vm-uuid')
        vm_plugin.get_vm_by_uuid.assert_called_once_with('vm-uuid')


@pytest.mark.kvmagent
class TestCheckVmStateHandler:
    def test_check_vm_state(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_r = MagicMock(return_value=0)
        vm_plugin.get_all_vm_states = MagicMock(return_value={})
        vm_plugin.get_all_vm_states_with_process = MagicMock(return_value={'vm1': vm_plugin.Vm.VM_STATE_RUNNING})
        plugin.get_vm_stat_with_ps = MagicMock(return_value=vm_plugin.Vm.VM_STATE_SHUTDOWN)

        req = _make_req({'vmUuids': ['vm-uuid']})
        result = plugin.check_vm_state(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['states']['vm-uuid'] == vm_plugin.Vm.VM_STATE_SHUTDOWN


@pytest.mark.kvmagent
class TestStopVmHandler:
    def test_stop_vm(self):
        plugin = _make_vm_plugin()
        plugin._dump = MagicMock()
        plugin._record_operation = MagicMock()
        plugin._stop_vm = MagicMock()
        vm_plugin.notify_vrouter = MagicMock()
        vm_plugin.transform_to_tf_uuid = MagicMock(return_value='tf-uuid')

        req = _make_req({'uuid': 'vm-uuid', 'debug': False, 'timeout': 10, 'vmNics': [{'uuid': 'nic-uuid', 'type': 'TFVNIC'}]})
        result = plugin.stop_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin._stop_vm.assert_called_once()
        vm_plugin.notify_vrouter.assert_called_once()


@pytest.mark.kvmagent
class TestPauseVmHandler:
    def test_pause_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'uuid': 'vm-uuid'})
        result = plugin.pause_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.pause.assert_called_once()


@pytest.mark.kvmagent
class TestResumeVmHandler:
    def test_resume_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'uuid': 'vm-uuid'})
        result = plugin.resume_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.resume.assert_called_once()


@pytest.mark.kvmagent
class TestRebootVmHandler:
    def test_reboot_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        plugin.collect_vm_virtualizer_info = MagicMock()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'uuid': 'vm-uuid'})
        result = plugin.reboot_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.reboot.assert_called_once()
        plugin.collect_vm_virtualizer_info.assert_called_once()


@pytest.mark.kvmagent
class TestDestroyVmHandler:
    def test_destroy_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.ovs.isVmUseOpenvSwitch = MagicMock(return_value=False)
        vm_plugin.delVnicFromOvsByVmUuidIfExist = MagicMock()
        vm_plugin.notify_vrouter = MagicMock()
        vm_plugin.transform_to_tf_uuid = MagicMock(return_value='tf-uuid')

        req = _make_req({'uuid': 'vm-uuid', 'vmNics': [{'uuid': 'nic-uuid', 'type': 'TFVNIC'}]})
        result = plugin.destroy_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.destroy.assert_called_once()


@pytest.mark.kvmagent
class TestAttachDataVolumeHandler:
    def test_attach_data_volume(self):
        plugin = _make_vm_plugin()
        plugin.get_device_address_info = MagicMock(return_value=vm_plugin.VirtualDeviceInfo())
        vm_plugin.touchQmpSocketWhenExists = MagicMock()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm._get_target_disk = MagicMock(return_value=(MagicMock(), 'vda'))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'volume': {'installPath': '/path/vol', 'volumeUuid': 'vol-uuid'}, 'addons': {}})
        result = plugin.attach_data_volume(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.attach_data_volume.assert_called_once()
        mock_vm.refresh.assert_called_once()


@pytest.mark.kvmagent
class TestDetachDataVolumeHandler:
    def test_detach_data_volume(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm._get_target_disk = MagicMock(return_value=(MagicMock(), 'vda'))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.volume_support_block_node = MagicMock(return_value=False)

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'volume': {'installPath': '/path/vol', 'volumeUuid': 'vol-uuid'}})
        result = plugin.detach_data_volume(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.detach_data_volume.assert_called_once()


@pytest.mark.kvmagent
class TestSetVolumeBandwidthHandler:
    def test_set_volume_bandwidth(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(None, 'vda'))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        from zstacklib.utils import shell
        shell.call = MagicMock()

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {'installPath': '/path/vol'},
            'mode': 'total',
            'totalBandwidth': 1024,
            'readBandwidth': 0,
            'writeBandwidth': 0,
            'totalIOPS': 0,
            'readIOPS': 0,
            'writeIOPS': 0,
        })
        result = plugin.set_volume_bandwidth(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        shell.call.assert_called()


@pytest.mark.kvmagent
class TestDeleteVolumeBandwidthHandler:
    def test_delete_volume_bandwidth(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(None, 'vda'))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin._get_volume_bandwidth_value = MagicMock(return_value='0')
        from zstacklib.utils import shell
        shell.call = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {'installPath': '/path/vol'}, 'mode': 'all'})
        result = plugin.delete_volume_bandwidth(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        shell.call.assert_called()


@pytest.mark.kvmagent
class TestGetVolumeBandwidthHandler:
    def test_get_volume_bandwidth(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(None, 'vda'))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        from zstacklib.utils import shell
        shell.call = MagicMock(return_value=(
            'total_bytes_sec: 1024\n'
            'read_bytes_sec: 2048\n'
            'write_bytes_sec: 4096\n'
            'total_iops_sec: 12\n'
            'read_iops_sec: 3\n'
            'write_iops_sec: 4\n'
        ))

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {'installPath': '/path/vol'}})
        result = plugin.get_volume_bandwidth(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['bandWidth'] == '1024'
        assert rsp['bandWidthRead'] == '2048'
        assert rsp['bandWidthWrite'] == '4096'
        assert rsp['iopsTotal'] == '12'
        assert rsp['iopsRead'] == '3'
        assert rsp['iopsWrite'] == '4'


@pytest.mark.kvmagent
class TestSetNicQosHandler:
    def test_set_nic_qos(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock()

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'internalName': 'eth0',
            'inboundBandwidth': 1024 * 8 * 1024,
            'outboundBandwidth': 2048 * 8 * 1024,
        })
        result = plugin.set_nic_qos(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        shell.call.assert_called()


@pytest.mark.kvmagent
class TestAttachNicHandler:
    def test_attach_nic(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        iface = MagicMock()
        iface.mac.address_ = '00:11:22:33:44:55'
        iface.address.bus_ = '0x00'
        iface.address.function_ = '0x0'
        iface.address.type_ = 'pci'
        iface.address.domain_ = '0x0000'
        iface.address.slot_ = '0x05'
        mock_vm.domain_xmlobject.devices.get_child_node_as_list = MagicMock(return_value=[iface])
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid', 'nic': {'mac': '00:11:22:33:44:55'}})
        result = plugin.attach_nic(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.attach_nic.assert_called_once()


@pytest.mark.kvmagent
class TestNotifyTfNicHandler:
    def test_notify_tf_nic(self):
        plugin = _make_vm_plugin()
        vm_plugin.notify_vrouter = MagicMock()
        vm_plugin.transform_to_tf_uuid = MagicMock(side_effect=lambda v: 'tf-%s' % v)

        req = _make_req({
            'accountUuid': 'acct-uuid',
            'vmInstanceUuid': 'vm-uuid',
            'sugonSdnAction': 'add',
            'nics': [{
                'type': 'TFVNIC',
                'uuid': 'nic-uuid',
                'l2NetworkUuid': 'l2-uuid',
                'nicInternalName': 'tap0',
                'mac': '00:11:22:33:44:55',
                'ipForTf': '10.0.0.1',
            }]
        })
        result = plugin.notify_tf_nic(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.notify_vrouter.assert_called_once()


@pytest.mark.kvmagent
class TestGetConsolePortHandler:
    def test_get_console_port(self):
        plugin = _make_vm_plugin()
        plugin.get_vm_console_info = MagicMock(return_value=('vnc', 5901, None, None))

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.get_console_port(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['port'] == 5901


@pytest.mark.kvmagent
class TestTakeConsoleScreenshotHandler:
    def test_take_console_screenshot(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.image.convert_image = MagicMock(return_value='/tmp/vm-uuid.png')
        vm_plugin.linux.rm_file_force = MagicMock()
        stream = MagicMock()
        stream.recv = MagicMock(side_effect=[b''])
        stream.finish = MagicMock()

        def _fake_reconnect(_func):
            def _wrapper(*_args, **_kwargs):
                return stream
            return _wrapper

        vm_plugin.LibvirtAutoReconnect = _fake_reconnect

        from unittest.mock import mock_open
        m_write = mock_open()
        m_read = mock_open(read_data=b'img')

        def _open_side_effect(file, mode='r', *args, **kwargs):
            if 'rb' in mode:
                return m_read(file, mode, *args, **kwargs)
            return m_write(file, mode, *args, **kwargs)

        with patch('builtins.open', side_effect=_open_side_effect):
            req = _make_req({'vmUuid': 'vm-uuid'})
            result = plugin.take_console_screenshot(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.domain.screenshot.assert_called_once()


@pytest.mark.kvmagent
class TestOnlineIncreaseMemHandler:
    def test_online_increase_mem(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.get_memory = MagicMock(return_value=2048)
        vm_plugin.get_vm_by_uuid = MagicMock(side_effect=[mock_vm, mock_vm])

        req = _make_req({'vmUuid': 'vm-uuid', 'memorySize': 2048})
        result = plugin.online_increase_mem(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.hotplug_mem.assert_called_once_with(2048)


@pytest.mark.kvmagent
class TestOnlineIncreaseCpuHandler:
    def test_online_increase_cpu(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.get_cpu_num = MagicMock(return_value=4)
        vm_plugin.get_vm_by_uuid = MagicMock(side_effect=[mock_vm, mock_vm])

        req = _make_req({'vmUuid': 'vm-uuid', 'cpuNum': 4})
        result = plugin.online_increase_cpu(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.hotplug_cpu.assert_called_once_with(4)


@pytest.mark.kvmagent
class TestOnlineChangeCpuMemHandler:
    def test_online_change_cpumem(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.get_cpu_num = MagicMock(return_value=4)
        mock_vm.get_memory = MagicMock(return_value=4096)
        vm_plugin.get_vm_by_uuid = MagicMock(side_effect=[mock_vm, mock_vm])

        req = _make_req({'vmUuid': 'vm-uuid', 'cpuNum': 4, 'memorySize': 4096})
        result = plugin.online_change_cpumem(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.hotplug_mem.assert_called_once_with(4096)
        mock_vm.hotplug_cpu.assert_called_once_with(4)


@pytest.mark.kvmagent
class TestGetCpuXmlHandler:
    def test_get_cpu_xml(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import shell
        mock_cmd = MagicMock()
        mock_cmd.stdout = 'cpu-xml'
        mock_cmd.stderr = ''
        mock_cmd.return_code = 0
        mock_cmd.__call__ = MagicMock()
        shell.ShellCmd = MagicMock(return_value=mock_cmd)
        vm_plugin.linux.get_cpu_model = MagicMock(return_value=('x86', 'Intel'))

        req = _make_req()
        result = plugin.get_cpu_xml(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['cpuXml'] == 'cpu-xml'
        assert rsp['cpuModelName'] == 'Intel'


@pytest.mark.kvmagent
class TestCompareCpuFunctionHandler:
    def test_compare_cpu_function(self):
        plugin = _make_vm_plugin()
        from zstacklib.utils import shell
        mock_cmd = MagicMock()
        mock_cmd.stdout = 'ok'
        mock_cmd.stderr = ''
        mock_cmd.return_code = 0
        mock_cmd.__call__ = MagicMock()
        shell.ShellCmd = MagicMock(return_value=mock_cmd)
        vm_plugin.linux.write_to_temp_file = MagicMock(return_value='/tmp/cpu.xml')
        vm_plugin.linux.rm_file_force = MagicMock()

        req = _make_req({'cpuXml': '<cpu></cpu>'})
        result = plugin.compare_cpu_function(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.linux.rm_file_force.assert_called_once_with('/tmp/cpu.xml')


@pytest.mark.kvmagent
class TestMergeSnapshotToVolumeHandler:
    def test_merge_snapshot_to_volume(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        with patch('os.path.exists', return_value=False):
            req = _make_req({'vmUuid': 'vm-uuid'})
            result = plugin.merge_snapshot_to_volume(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.merge_snapshot.assert_called_once()


@pytest.mark.kvmagent
class TestBlockStreamHandler:
    def test_block_stream(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {'installPath': '/path/vol'}})
        result = plugin.block_stream(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.block_stream_disk.assert_called_once()


@pytest.mark.kvmagent
class TestBlockCommitHandler:
    def test_block_commit(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.VmPlugin._get_snapshot_size = MagicMock(return_value=123)

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {'installPath': '/path/vol'},
            'base': '/path/base',
            'topChildrenInstallPathInDb': [],
        })
        result = plugin.block_commit(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['size'] == 123
        mock_vm.do_block_commit.assert_called_once()


@pytest.mark.kvmagent
class TestBlockPullHandler:
    def test_block_pull(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.get_volume_actual_installpath = MagicMock(return_value='/path/vol')
        vm_plugin.VmPlugin._get_snapshot_size = MagicMock(return_value=456)

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {'installPath': '/path/vol'},
            'base': '/path/base',
        })
        result = plugin.block_pull(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['size'] == 456
        mock_vm.block_stream_disk.assert_called_once()


@pytest.mark.kvmagent
class TestCheckRecoverHandler:
    def test_check_recover(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.domain_xmlobject.devices.get_child_node_as_list = MagicMock(return_value=[])
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.is_nbd_disk = MagicMock(return_value=False)

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.check_recover(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['status'] == 'done'


@pytest.mark.kvmagent
class TestLoginIscsiTargetHandler:
    def test_login_iscsi_target(self):
        plugin = _make_vm_plugin()
        vm_plugin.iscsi.connect_iscsi_target = MagicMock()

        req = _make_req({'url': 'iscsi://127.0.0.1/iqn.test'})
        result = plugin.login_iscsi_target(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.iscsi.connect_iscsi_target.assert_called_once_with('iscsi://127.0.0.1/iqn.test')


@pytest.mark.kvmagent
class TestFstrimVmHandler:
    def test_fstrim_vm(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.fstrim_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestGetVmFirstBootDeviceHandler:
    def test_get_vm_first_boot_device(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.domain.XMLDesc = MagicMock(return_value='<xml/>')
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.find_domain_first_boot_device = MagicMock(return_value='hd')

        req = _make_req({'uuid': 'vm-uuid'})
        result = plugin.get_vm_first_boot_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['firstBootDevice'] == 'hd'


@pytest.mark.kvmagent
class TestGetVmDeviceAddressHandler:
    def test_get_vm_device_address(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.VmPlugin._find_volume_device_address = MagicMock(return_value=['addr1'])

        req = _make_req({'uuid': 'vm-uuid', 'deviceTOs': {'VolumeVO': [{'uuid': 'vol-uuid'}]}})
        result = plugin.get_vm_device_address(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['addresses']['VolumeVO'] == ['addr1']


@pytest.mark.kvmagent
class TestGetVirtualizerInfoHandler:
    def test_get_virtualizer_info(self):
        plugin = _make_vm_plugin()
        plugin.config = {vm_plugin.kvmagent.HOST_UUID: 'host-uuid'}
        vm_plugin.qemu.get_path = MagicMock(return_value='/usr/bin/qemu')
        vm_plugin.qemu.get_version_from_exe_file = MagicMock(return_value='6.2')
        plugin.collect_vm_virtualizer_info = MagicMock()

        req = _make_req({'vmUuids': ['vm-uuid']})
        result = plugin.get_virtualizer_info(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.collect_vm_virtualizer_info.assert_called_once()


@pytest.mark.kvmagent
class TestSetIothreadPinHandler:
    def test_set_iothread_pin(self):
        plugin = _make_vm_plugin()
        plugin.get_iothread_info = MagicMock(return_value=[])
        plugin.add_io_thread = MagicMock(return_value=None)
        plugin.pin_io_thread = MagicMock(return_value=None)

        req = _make_req({'vmUuid': 'vm-uuid', 'ioThreadId': 1, 'pin': '0-3'})
        result = plugin.set_iothread_pin(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['ioThreadId'] == 1


@pytest.mark.kvmagent
class TestDelIothreadPinHandler:
    def test_del_iothread_pin(self):
        plugin = _make_vm_plugin()
        plugin.get_iothread_info = MagicMock(return_value=[('1', '0-3')])
        plugin.del_io_thread = MagicMock(return_value=None)

        req = _make_req({'vmUuid': 'vm-uuid', 'ioThreadId': 1})
        result = plugin.del_iothread_pin(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['ioThreadId'] == 1


@pytest.mark.kvmagent
class TestSetScsiControllerHandler:
    def test_set_scsi_controller(self):
        plugin = _make_vm_plugin()
        plugin.add_scsi_controller = MagicMock(return_value=2)

        req = _make_req({'vmUuid': 'vm-uuid', 'ioThreadId': 1})
        result = plugin.set_scsi_controller(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['controllerIndex'] == '2'


@pytest.mark.kvmagent
class TestDelScsiControllerHandler:
    def test_del_scsi_controller(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        controller = MagicMock()
        controller.type_ = 'scsi'
        controller.driver.iothread_ = '1'
        controller.alias.name_ = 'scsi1'
        mock_vm.domain_xmlobject.devices.get_child_node_as_list = MagicMock(return_value=[controller])
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.detach_controller_by_alias = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'ioThreadId': 1})
        result = plugin.del_scsi_controller(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.detach_controller_by_alias.assert_called_once_with('vm-uuid', 'scsi1')


@pytest.mark.kvmagent
class TestSyncVmClockNowHandler:
    def test_sync_vm_clock_now(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm.get_name = MagicMock(return_value='vm')
        mock_vm._wait_until_qemuga_ready = MagicMock()
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.is_qga_connected = MagicMock(return_value=True)
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))

        req = _make_req({'vmUuid': 'vm-uuid'})
        result = plugin.sync_vm_clock_now(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestConfigSecondaryVmHandler:
    def test_config_secondary_vm(self):
        plugin = _make_vm_plugin()
        vm_plugin.execute_qmp_command = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'primaryVmHostIp': '10.0.0.1', 'nbdServerPort': 1234})
        result = plugin.config_secondary_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert vm_plugin.execute_qmp_command.call_count == 2


@pytest.mark.kvmagent
class TestConfigPrimaryVmHandler:
    def test_config_primary_vm(self):
        plugin = _make_vm_plugin()
        vm_plugin.ft.cleanup_vm_before_setup_colo_primary_vm = MagicMock()
        vm_plugin.qmp.execute_qmp_command = MagicMock(return_value=[])
        vm_plugin.linux.is_port_available = MagicMock(return_value=True)
        mock_vm = MagicMock()
        mock_vm.domain.XMLDesc = MagicMock(return_value='')
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        req = _make_req({
            'vmInstanceUuid': 'vm-uuid',
            'hostIp': '10.0.0.1',
            'configs': [{
                'mirrorPort': 7000,
                'primaryInPort': 7001,
                'secondaryInPort': 7002,
                'primaryOutPort': 7003,
            }],
        })
        result = plugin.config_primary_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.qmp.execute_qmp_command.assert_called()


@pytest.mark.kvmagent
class TestVmSyncHandler:
    def test_vm_sync(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_r = MagicMock(return_value=0)

        def _set_states(rsp):
            rsp.states = {'vm1': vm_plugin.Vm.VM_STATE_RUNNING}

        plugin.get_vm_state_from_libvirt = MagicMock(side_effect=_set_states)
        vm_plugin.get_all_vm_states_with_process = MagicMock(return_value={'vm1': vm_plugin.Vm.VM_STATE_RUNNING})
        vm_plugin.get_vm_states_from_cache = MagicMock(return_value={})

        req = _make_req()
        result = plugin.vm_sync(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['states']['vm1'] == vm_plugin.Vm.VM_STATE_RUNNING


@pytest.mark.kvmagent
class TestVolumeSyncHandler:
    def test_volume_sync(self):
        plugin = _make_vm_plugin()
        vm_plugin.last_inactive_vol_paths = {}
        vm_plugin.bash.bash_o = MagicMock(return_value='')
        vm_plugin.glob.glob = MagicMock(return_value=[])
        vm_plugin.os.path.isdir = MagicMock(return_value=True)

        req = _make_req({'storagePaths': ['file:///tmp/vols']})
        result = plugin.volume_sync(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestRollbackQuorumConfigHandler:
    def test_rollback_quorum_config(self):
        plugin = _make_vm_plugin()
        vm_plugin.xrange = range
        mock_vm = MagicMock()
        mock_vm._get_all_volume_alias_names = MagicMock(return_value=['drive0'])
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.qmp.execute_qmp_command = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'volumes': [], 'nicNumber': 0})
        result = plugin.rollback_quorum_config(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.qmp.execute_qmp_command.assert_called()


@pytest.mark.kvmagent
class TestCheckMountDomainHandler:
    def test_check_mount_domain(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.is_valid_nfs_url = MagicMock(return_value=True)

        req = _make_req({'url': 'nfs://127.0.0.1:/export', 'timeout': 1000})
        result = plugin.check_mount_domain(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['active'] is True


@pytest.mark.kvmagent
class TestAttachGuestToolsIsoToVmHandler:
    def test_attach_guest_tools_iso_to_vm(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        with patch('os.path.exists', return_value=True):
            req = _make_req({'vmInstanceUuid': 'vm-uuid', 'platform': 'Linux', 'needTempDisk': False})
            result = plugin.attach_guest_tools_iso_to_vm(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.detach_iso.assert_called_once()
        mock_vm.attach_iso.assert_called_once()


@pytest.mark.kvmagent
class TestDetachGuestToolsIsoFromVmHandler:
    def test_detach_guest_tools_iso_from_vm(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.domain_xml = 'prefix-%s' % vm_plugin.GUEST_TOOLS_ISO_LINUX_PATH
        mock_vm._check_target_disk_existing_by_path = MagicMock(return_value=False)
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.linux.rm_file_force = MagicMock()
        with patch('os.path.exists', return_value=False):
            req = _make_req({'vmInstanceUuid': 'vm-uuid', 'platform': 'Linux'})
            result = plugin.detach_guest_tools_iso_from_vm(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.detach_iso.assert_called_once()


@pytest.mark.kvmagent
class TestAttachPciDeviceToHostHandler:
    def test_attach_pci_device_to_host(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        with patch('os.path.exists', return_value=False):
            req = _make_req({'pciDeviceAddress': '0000:00:01.0'})
            result = plugin.attach_pci_device_to_host(req)
            rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestDetachPciDeviceFromHostHandler:
    def test_detach_pci_device_from_host(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        with patch('os.path.exists', return_value=False):
            req = _make_req({'pciDeviceAddress': '0000:00:01.0'})
            result = plugin.detach_pci_device_from_host(req)
            rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestBlockMigrateHandler:
    def test_block_migrate(self):
        plugin = _make_vm_plugin()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=MagicMock())
        plugin._record_operation = MagicMock()
        plugin._build_dest_disk_xml = MagicMock(return_value=('vda', '/tmp/disk.xml'))
        plugin._do_block_copy = MagicMock(return_value=(True, None))
        vm_plugin.os.remove = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'oldVolumePath': '/path/old', 'newVolume': {}})
        result = plugin.block_migrate(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin._record_operation.assert_called_once()
        vm_plugin.os.remove.assert_called_once_with('/tmp/disk.xml')


@pytest.mark.kvmagent
class TestCancelBackupJobsHandler:
    def test_cancel_backup_jobs(self):
        plugin = _make_vm_plugin()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=MagicMock())
        plugin.do_cancel_vm_backup_jobs = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'force': False})
        result = plugin.cancel_backup_jobs(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.do_cancel_vm_backup_jobs.assert_called_once()


@pytest.mark.kvmagent
class TestCancelBackupJobHandler:
    def test_cancel_backup_job(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(MagicMock(), None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-0')
        plugin.do_cancel_volume_backup_job = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {'volumeUuid': 'vol-uuid'}, 'force': False})
        result = plugin.cancel_backup_job(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.do_cancel_volume_backup_job.assert_called_once()


@pytest.mark.kvmagent
class TestCancelVolumeCbtBackupHandler:
    def test_cancel_volume_cbt_backup(self):
        plugin = _make_vm_plugin()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=MagicMock())
        client = MagicMock()
        client.stop_vm_cbt_backup_jobs = MagicMock()
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)

        req = _make_req({'vmUuid': 'vm-uuid', 'records': []})
        result = plugin.cancel_volume_cbt_backup(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        client.stop_vm_cbt_backup_jobs.assert_called_once_with('vm-uuid', [])


@pytest.mark.kvmagent
class TestCancelVolumeMirrorHandler:
    def test_cancel_volume_mirror(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(MagicMock(), None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-0')
        client = MagicMock()
        client.stop_mirror = MagicMock()
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)

        req = _make_req({'vmUuid': 'vm-uuid', 'volume': {}, 'complete': False, 'force': False})
        result = plugin.cancel_volume_mirror(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        client.stop_mirror.assert_called_once()


@pytest.mark.kvmagent
class TestCheckColoVmStateHandler:
    def test_check_colo_vm_state(self):
        plugin = _make_vm_plugin()
        vm_plugin.get_all_vm_states = MagicMock(return_value={'vm-uuid': vm_plugin.Vm.VM_STATE_RUNNING})

        req = _make_req({'vmInstanceUuid': 'vm-uuid'})
        result = plugin.check_colo_vm_state(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['state'] == vm_plugin.Vm.VM_STATE_RUNNING


@pytest.mark.kvmagent
class TestCheckVolumeSnapshotHandler:
    def test_check_volume_snapshot(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm.VM_STATE_RUNNING = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm.VM_STATE_SHUTDOWN = vm_plugin.Vm.VM_STATE_SHUTDOWN
        mock_vm.VM_STATE_PAUSED = vm_plugin.Vm.VM_STATE_PAUSED
        mock_vm._get_target_disk_by_path = MagicMock(return_value=(MagicMock(), 'vda'))
        mock_vm._get_backfile_chain = MagicMock(return_value=[])
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.difflib.context_diff = MagicMock(return_value=[])
        mock_vm.domain_xmlobject.devices.get_child_node_as_list = MagicMock(return_value=[])

        cmd = MagicMock(
            vmUuid='vm-uuid',
            volumeUuid='vol-uuid',
            currentInstallPath='/path1',
            volumeChainToCheck={'/path1': 1},
            volume=MagicMock(deviceId=0),
            excludeInstallPaths=None,
        )
        from builtins import map as builtin_map
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd), \
                patch('builtins.map', side_effect=lambda *args, **kwargs: list(builtin_map(*args, **kwargs))):
            req = _make_req({})
            result = plugin.check_volume_snapshot(req)
            rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestDetachVirtioDriverHandler:
    def test_detach_virtio_driver(self):
        plugin = _make_vm_plugin()
        plugin.eject_floppy = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'driverFormat': 'VFD'})
        result = plugin.detach_virtio_driver(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.eject_floppy.assert_called_once()


@pytest.mark.kvmagent
class TestExportNbdVolumesHandler:
    def test_export_nbd_volumes(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.parse_port_range = MagicMock(return_value=(6000, 6001))
        lock = MagicMock()
        vm_plugin.linux.find_free_port_with_locking = MagicMock(return_value=(6000, lock))
        plugin.get_cbt_volume_actual_install_path = MagicMock(return_value='/path/vol')
        plugin.active_volume_if_need = MagicMock()
        vm_plugin.qemu_nbd.export = MagicMock(return_value=MagicMock())
        vm_plugin.linux.check_socket_available = MagicMock(return_value=True)

        req = _make_req({
            'portRange': '6000-6001',
            'volumeInfos': [{'volume': {'format': 'qcow2', 'installPath': '/path/vol', 'volumeUuid': 'vol-uuid'}}],
        })
        result = plugin.export_nbd_volumes(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert len(rsp['volumeInfos']) == 1


@pytest.mark.kvmagent
class TestFailColoPvmHandler:
    def test_fail_colo_pvm(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.sshpass_run = MagicMock(return_value=(0, '', ''))

        req = _make_req({
            'vmInstanceUuid': 'vm-uuid',
            'targetHostIp': '10.0.0.1',
            'targetHostPassword': 'password',
            'targetHostPort': 22,
        })
        result = plugin.fail_colo_pvm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestGetVmGuestToolsInfoHandler:
    def test_get_vm_guest_tools_info(self):
        plugin = _make_vm_plugin()
        plugin.get_linux_vm_guest_tools_info = MagicMock(return_value=(vm_plugin.VmPlugin.GUESTTOOLS_STATE_RUNNING, '1.0'))

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'platform': 'linux'})
        result = plugin.get_vm_guest_tools_info(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestGetVmMetricsRoutingStatusHandler:
    def test_get_vm_metrics_routing_status(self):
        plugin = _make_vm_plugin()
        plugin.get_lighttpd_status_for_vm = MagicMock()
        plugin.get_push_gateway_routing_for_vm = MagicMock()

        cmd = MagicMock(vmInstanceUuid='vm-uuid', items=['lighttpd', 'pushgateway'])
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.get_vm_metrics_routing_status(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.get_lighttpd_status_for_vm.assert_called_once()
        plugin.get_push_gateway_routing_for_vm.assert_called_once()


@pytest.mark.kvmagent
class TestGetVolumeMirrorModeHandler:
    def test_get_volume_mirror_mode(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(MagicMock(), None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-0')
        client = MagicMock()
        client.get_mirror_mode = MagicMock(return_value='full')
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {'installPath': '/path/vol'},
            'lastMirrorVolume': 'last',
        })
        result = plugin.get_volume_mirror_mode(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['mode'] == 'full'


@pytest.mark.kvmagent
class TestGetVolumesCbtBitmapsHandler:
    def test_get_volumes_cbt_bitmaps(self):
        plugin = _make_vm_plugin()
        vm_plugin.qemu.get_data_bitmap = MagicMock(return_value={0: 1})
        vm_plugin.qemu.compress_and_encode_bitmap = MagicMock(return_value='encoded')
        cmd = MagicMock()
        volume_info = MagicMock()
        volume_info.mode = 'incremental'
        volume_info.scratchNodeName = 'node'
        volume_info.nbdServer = '127.0.0.1'
        volume_info.nbdPort = 10809
        cmd.bitmapTimestamp = 'ts'
        cmd.volumeInfos = [volume_info]
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.get_volumes_cbt_bitmaps(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert len(rsp['volumeInfos']) == 1


@pytest.mark.kvmagent
class TestHotPlugMdevDeviceHandler:
    def test_hot_plug_mdev_device(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.write_to_temp_file = MagicMock(return_value='/tmp/mdev.xml')
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.pci.get_mdev_passthrough_mapping = MagicMock(return_value={'11111111-1111-1111-1111-111111111111': 'mdev-addr'})
        vm_plugin.uuid.UUID = MagicMock(side_effect=lambda value: value)

        req = _make_req({'vmUuid': 'vm-uuid', 'MdevDeviceUuid': '11111111-1111-1111-1111-111111111111'})
        result = plugin.hot_plug_mdev_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHotPlugPciDeviceHandler:
    def test_hot_plug_pci_device(self):
        plugin = _make_vm_plugin()
        plugin.timeout_object = MagicMock()
        vm_plugin.linux.write_to_temp_file = MagicMock(return_value='/tmp/pci.xml')
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        vm_plugin.pci.get_vm_pci_device_address_by_host_address = MagicMock(return_value='0000:00:00.0')

        req = _make_req({'vmUuid': 'vm-uuid', 'pciDeviceAddress': '0000:00:01.0'})
        result = plugin.hot_plug_pci_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['vmPciDeviceAddress'] == '0000:00:00.0'


@pytest.mark.kvmagent
class TestHotUnplugMdevDeviceHandler:
    def test_hot_unplug_mdev_device(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        vm_plugin.uuid.UUID = MagicMock(side_effect=lambda value: value)
        vm_plugin.linux.wait_callback_success = MagicMock(return_value=True)
        vm_plugin.linux.write_to_temp_file = MagicMock(return_value='/tmp/mdev.xml')

        req = _make_req({'vmUuid': 'vm-uuid', 'MdevDeviceUuid': '11111111-1111-1111-1111-111111111111'})
        result = plugin.hot_unplug_mdev_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHotUnplugPciDeviceHandler:
    def test_hot_unplug_pci_device(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=MagicMock())

        req = _make_req({'vmUuid': 'vm-uuid', 'pciDeviceAddress': '0000:00:01.0'})
        result = plugin.hot_unplug_pci_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestKvmAttachUsbDeviceHandler:
    def test_kvm_attach_usb_device(self):
        plugin = _make_vm_plugin()
        plugin._attach_usb_by_libvirt = MagicMock(return_value=(True, None))

        req = _make_req({'vmUuid': 'vm-uuid', 'attachType': 'PassThrough'})
        result = plugin.kvm_attach_usb_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestKvmDetachUsbDeviceHandler:
    def test_kvm_detach_usb_device(self):
        plugin = _make_vm_plugin()
        plugin._detach_usb_by_libvirt = MagicMock()

        req = _make_req({'vmUuid': 'vm-uuid', 'attachType': 'PassThrough'})
        result = plugin.kvm_detach_usb_device(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestListExportedVolumesHandler:
    def test_list_exported_volumes(self):
        plugin = _make_vm_plugin()
        vm_plugin.qemu_nbd.find_qemu_nbd_process = MagicMock(side_effect=[0, 1])
        volume_one = MagicMock(volumeUuid='vol-1', installPath='/path/vol1')
        volume_two = MagicMock(volumeUuid='vol-2', installPath='/path/vol2')
        cmd = MagicMock(volumes=[volume_one, volume_two])
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.list_exported_volumes(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['volumeExportInfos']['vol-1'] is True
        assert rsp['volumeExportInfos']['vol-2'] is False


@pytest.mark.kvmagent
class TestMigrateVmHandler:
    def test_migrate_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        mock_vm = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        cmd = MagicMock(vmUuid='vm-uuid', reload=False, migrateFromDestination=False)
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.migrate_vm(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        mock_vm.migrate.assert_called_once()


@pytest.mark.kvmagent
class TestQueryVmMirrorLatenciesBoundaryHandler:
    def test_query_vm_mirror_latencies_boundary(self):
        plugin = _make_vm_plugin()
        thread_obj = MagicMock()
        thread_obj.getResult = MagicMock(return_value=('vm-uuid', {'max': 1}, {'min': 2}))
        vm_plugin.QueryVmLatenciesThread = MagicMock(return_value=thread_obj)

        req = _make_req({'vmUuids': ['vm-uuid'], 'times': [1]})
        result = plugin.query_vm_mirror_latencies_boundary(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestQueryVolumeMirrorHandler:
    def test_query_volume_mirror(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        target_disk = MagicMock()
        target_disk.alias.name_ = 'virtio-disk0'
        mock_vm._get_target_disk = MagicMock(return_value=(target_disk, None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-virtio-disk0')
        vm_plugin.get_block_node_name_by_disk_name = MagicMock(return_value='node-0')
        client = MagicMock()
        client.query_mirror_volumes = MagicMock(return_value={'drive-virtio-disk0': True})
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)

        volume = MagicMock(volumeUuid='vol-uuid')
        cmd = MagicMock(vmUuid='vm-uuid', volumes=[volume], stopExtra=False)
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.query_volume_mirror(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['mirrorVolumes'] == ['vol-uuid']


@pytest.mark.kvmagent
class TestRecoverVolumesHandler:
    def test_recover_volumes(self):
        plugin = _make_vm_plugin()
        vm_plugin.VM_RECOVER_DICT = {'vm-uuid': MagicMock()}
        vm_plugin.VM_RECOVER_TASKS = {}
        vm_plugin.parse_url = MagicMock(return_value=MagicMock(scheme=None))
        task = MagicMock()
        task.__enter__.return_value = task
        task.__exit__.return_value = None
        task.recover_vm_volumes = MagicMock()
        vm_plugin.VmVolumesRecoveryTask = MagicMock(return_value=task)
        vm_plugin.linux.wait_callback_success = MagicMock(return_value=True)
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=MagicMock())

        req = _make_req({'vmUuid': 'vm-uuid', 'volumes': [{'installPath': '/path/vol'}]})
        result = plugin.recover_volumes(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        task.recover_vm_volumes.assert_called_once()


@pytest.mark.kvmagent
class TestRegisterPrimaryVmHeartbeatHandler:
    def test_register_primary_vm_heartbeat(self):
        plugin = _make_vm_plugin()
        plugin.vm_heartbeat = {}
        thread_obj = MagicMock()
        thread_obj.is_alive = MagicMock(return_value=True)
        vm_plugin.thread = MagicMock()
        vm_plugin.thread.ThreadFacade.run_in_thread = MagicMock(return_value=thread_obj)

        with patch('socket.socket') as mock_socket:
            sock = MagicMock()
            mock_socket.return_value = sock
            req = _make_req({'vmInstanceUuid': 'vm-uuid', 'targetHostIp': '10.0.0.1', 'heartbeatPort': 1234})
            result = plugin.register_primary_vm_heartbeat(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.thread.ThreadFacade.run_in_thread.assert_called_once()


@pytest.mark.kvmagent
class TestReloadRedirectUsbHandler:
    def test_reload_redirect_usb(self):
        plugin = _make_vm_plugin()
        plugin._detach_usb_by_libvirt = MagicMock()
        plugin._attach_usb_by_libvirt = MagicMock(return_value=(True, None))

        req = _make_req({'vmUuid': 'vm-uuid', 'attachType': 'Redirect', 'usbVersion': '2.0'})
        result = plugin.reload_redirect_usb(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin._detach_usb_by_libvirt.assert_called_once()
        plugin._attach_usb_by_libvirt.assert_called_once()


@pytest.mark.kvmagent
class TestScriptExecOnVmHandler:
    def test_script_exec_on_vm(self):
        plugin = _make_vm_plugin()
        qga = MagicMock()
        qga.guest_exec_bash = MagicMock(side_effect=[(0, '', ''), (0, '', ''), (0, 'stdout', '')])
        qga.guest_file_is_exist = MagicMock(return_value=False)
        vm_plugin.VmQga = MagicMock(return_value=qga)
        def _fake_reconnect(_func):
            def _wrapper(*_args, **_kwargs):
                return MagicMock()
            return _wrapper
        vm_plugin.LibvirtAutoReconnect = _fake_reconnect

        cmd = MagicMock(vmUuid='vm-uuid', scriptType='Shell', scriptTimeout=1, logPath=None)
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.script_exec_on_vm(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['exitCode'] == 0


@pytest.mark.kvmagent
class TestSetSyncVmClockTaskHandler:
    def test_set_sync_vm_clock_task(self):
        plugin = _make_vm_plugin()
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))

        class _SyncMap(dict[int, str]):
            def has_key(self, key):
                return key in self

        plugin.sync_clock_cron_exp_map = _SyncMap({60: '*/1 * * * *'})

        from unittest.mock import mock_open
        class _IntervalMap(dict[int, str]):
            def has_key(self, key):
                return key in self

        with patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open()), \
                patch('tempfile.mktemp', return_value='/tmp/cron'), \
                patch('os.chmod'), \
                patch('os.remove'):
            cmd = MagicMock(intervalMap=_IntervalMap())
            with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
                req = _make_req({})
                result = plugin.set_sync_vm_clock_task(req)
                rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSetVfNicMacHandler:
    def test_set_vf_nic_mac(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.get_pf_name_by_vf_pci_address = MagicMock(return_value='pf0')
        vm_plugin.linux.get_vf_index_by_pci_address = MagicMock(return_value=1)
        vm_plugin.normalize_pci_address = MagicMock(return_value='0000:00:01.0')
        vm_plugin.bash.bash_roe = MagicMock(return_value=(0, '', ''))

        req = _make_req({'nics': [{'mac': '00:11:22:33:44:55', 'pciDeviceAddress': '0000:00:01.0'}]})
        result = plugin.set_vf_nic_mac(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.bash.bash_roe.assert_called()


@pytest.mark.kvmagent
class TestSetVfNicStateHandler:
    def test_set_vf_nic_state(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.state = vm_plugin.Vm.VM_STATE_RUNNING
        mock_vm.domain_xmlobject.devices.get_child_node_as_list = MagicMock(return_value=[])
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.set_domain_network_device = MagicMock()
        plugin.set_domain_iflink_state = MagicMock()
        vm_plugin.normalize_pci_address = MagicMock(return_value='0000:00:01.0')

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'haState': 'Enabled',
            'nic': {
                'mac': '00:11:22:33:44:55',
                'mtu': 1500,
                'bridgeName': 'br0',
                'nicInternalName': 'eth0',
                'vHostAddOn': {'queueNum': 1, 'rxBufferSize': 1024, 'txBufferSize': 1024},
            }
        })
        result = plugin.set_vf_nic_state(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin.set_domain_network_device.assert_called()


@pytest.mark.kvmagent
class TestStartColoSyncHandler:
    def test_start_colo_sync(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm._get_all_volume_alias_names = MagicMock(return_value=[])
        mock_vm.domain.XMLDesc = MagicMock(return_value='')
        vm_plugin.get_vm_by_uuid_no_retry = MagicMock(return_value=mock_vm)
        vm_plugin.qmp.execute_qmp_command = MagicMock(return_value={'status': 'colo'})
        vm_plugin.execute_qmp_command = MagicMock()

        req = _make_req({
            'vmInstanceUuid': 'vm-uuid',
            'volumes': [],
            'nics': [],
            'fullSync': False,
            'secondaryVmHostIp': '10.0.0.2',
            'nbdServerPort': 6000,
            'blockReplicationPort': 7000,
            'checkpointDelay': 10,
            'nicNumber': 0,
        })
        result = plugin.start_colo_sync(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestStartVmHandler:
    def test_start_vm(self):
        plugin = _make_vm_plugin()
        plugin._record_operation = MagicMock()
        plugin._start_vm = MagicMock()
        plugin.get_vm_device_info = MagicMock(return_value=([], [], None))
        plugin.collect_vm_virtualizer_info = MagicMock()
        vm_plugin.linux.find_vm_pid_by_uuid = MagicMock(return_value=123)
        vm_plugin.linux.enable_process_coredump = MagicMock()
        vm_plugin.linux.set_vm_priority = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'vmName': 'vm', 'priorityConfigStruct': {}})
        result = plugin.start_vm(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        plugin._start_vm.assert_called_once()
        vm_plugin.linux.set_vm_priority.assert_called_once()


@pytest.mark.kvmagent
class TestTakeVolumeBackupHandler:
    def test_take_volume_backup(self):
        plugin = _make_vm_plugin()
        storage = MagicMock()
        storage.worktarget = MagicMock(return_value='/tmp/backup.qcow2')
        vm_plugin.RemoteStorageFactory.get_remote_storage = MagicMock(return_value=storage)
        mock_vm = MagicMock()
        disk = MagicMock()
        disk.driver.type_ = 'qcow2'
        mock_vm._get_target_disk = MagicMock(return_value=(disk, None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-0')
        plugin.get_source_file_by_disk = MagicMock(return_value='/path/vol')
        plugin.do_take_volume_backup = MagicMock(return_value=('bitmap', 'parent'))

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {},
            'uploadDir': '/tmp',
            'backupPath': '/tmp/backup.qcow2',
            'threadContext': {'api': 'api'},
            'parent': 'parent',
        })
        result = plugin.take_volume_backup(req)
        rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestTakeVolumeCbtBackupHandler:
    def test_take_volume_cbt_backup(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.domain.jobStats = MagicMock(return_value={})
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        client = MagicMock()
        client.query_mirror_volumes = MagicMock(return_value=None)
        client.cbt_backup_volume = MagicMock(return_value=['info'])
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)
        vm_plugin.execute_qmp_command = MagicMock()

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volumeInfos': [],
            'bitmapTimestamp': '',
            'portRange': '6000-6001',
        })
        result = plugin.take_volume_cbt_backup(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['volumeInfos'] == ['info']


@pytest.mark.kvmagent
class TestTakeVolumeMirrorHandler:
    def test_take_volume_mirror(self):
        plugin = _make_vm_plugin()
        mock_vm = MagicMock()
        mock_vm.domain.jobStats = MagicMock(return_value={})
        target_disk = MagicMock()
        target_disk.alias.name_ = 'virtio-disk0'
        mock_vm._get_target_disk = MagicMock(return_value=(target_disk, None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
        plugin.get_disk_device_name = MagicMock(return_value='drive-0')
        client = MagicMock()
        client.query_mirror_volumes = MagicMock(return_value={})
        client.mirror_volume = MagicMock()
        vm_plugin.ImageStoreClient = MagicMock(return_value=client)
        vm_plugin.qmp.execute_qmp_command = MagicMock()

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volume': {'installPath': '/path/vol'},
            'mirrorTarget': 'target',
            'lastMirrorVolume': 'last',
            'mode': 'full',
            'speed': 0,
        })
        result = plugin.take_volume_mirror(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        client.mirror_volume.assert_called_once()


@pytest.mark.kvmagent
class TestTakeVolumeSnapshotHandler:
    def test_take_volume_snapshot(self):
        plugin = _make_vm_plugin()
        vm_plugin.Vm.ensure_no_internal_snapshot = MagicMock()
        vm_plugin.Vm.ensure_delta_snapshot_not_exceed = MagicMock()
        vm_plugin.linux.qcow2_clone_with_cmd = MagicMock()
        vm_plugin.linux.sync_file = MagicMock()
        vm_plugin.VmPlugin._get_snapshot_size = MagicMock(return_value=123)
        vm_plugin.touchQmpSocketWhenExists = MagicMock()
        vm_plugin.uuidhelper.uuid = MagicMock(return_value='snap-uuid')
        with patch('os.path.exists', return_value=True):
            req = _make_req({
                'vmUuid': None,
                'volumeUuid': 'vol-uuid',
                'volume': {},
                'installPath': '/path/snap',
                'volumeInstallPath': '/path/vol',
                'newVolumeInstallPath': '/path/new',
                'fullSnapshot': False,
                'online': False,
                'isBaremetal2InstanceOnlineSnapshot': False,
            })
            result = plugin.take_volume_snapshot(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['size'] == 123


@pytest.mark.kvmagent
class TestTakeVolumesBackupsHandler:
    def test_take_volumes_backups(self):
        plugin = _make_vm_plugin()
        storage = MagicMock()
        storage.workspace = MagicMock(return_value='/tmp/work')
        vm_plugin.RemoteStorageFactory.get_remote_storage = MagicMock(return_value=storage)
        mock_vm = MagicMock()
        disk = MagicMock()
        mock_vm._get_target_disk = MagicMock(return_value=(disk, None))
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)

        class _BackupInfo(object):
            def __init__(self, device_id, backup_file):
                self.deviceId: int = device_id
                self.backupFile: str = backup_file

        plugin.getBitmap = MagicMock(return_value=None)
        plugin.do_take_volumes_backup = MagicMock(return_value=[
            _BackupInfo(1, 'file1'),
            _BackupInfo(2, 'file2'),
        ])

        req = _make_req({
            'vmUuid': 'vm-uuid',
            'volumes': [{'deviceId': 1}, {'deviceId': 2}],
            'backupInfos': [],
            'backupPaths': ['fallback1', 'fallback2'],
            'uploadDir': '/tmp',
        })
        result = plugin.take_volumes_backups(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert len(rsp['backupInfos']) == 2


@pytest.mark.kvmagent
class TestTakeVolumesSnapshotsHandler:
    def test_take_volumes_snapshots(self):
        plugin = _make_vm_plugin()
        vm_plugin.Vm.ensure_no_internal_snapshot = MagicMock()
        vm_plugin.Vm.ensure_delta_snapshot_not_exceed = MagicMock()
        vm_plugin.linux.qcow2_clone_with_cmd = MagicMock()
        vm_plugin.VmPlugin._get_snapshot_size = MagicMock(return_value=123)
        vm_plugin.touchQmpSocketWhenExists = MagicMock()
        vm_plugin.get_vm_by_uuid = MagicMock(return_value=None)
        with patch('os.path.exists', return_value=True):
            vm_plugin.uuidhelper.uuid = MagicMock(return_value='uuid')
            req = _make_req({
                'snapshotJobs': [{
                    'vmInstanceUuid': 'vm-uuid',
                    'live': False,
                    'full': False,
                    'memory': False,
                    'previousInstallPath': '/path/prev',
                    'installPath': '/path/snap',
                    'newVolumeInstallPath': '/path/new',
                    'volumeUuid': 'vol-uuid',
                    'deviceId': 0,
                    'volume': {'installPath': '/path/vol'},
                }]
            })
            result = plugin.take_volumes_snapshots(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        assert len(rsp['snapshots']) == 1


@pytest.mark.kvmagent
class TestUnexportNbdVolumesHandler:
    def test_unexport_nbd_volumes(self):
        plugin = _make_vm_plugin()
        plugin.get_cbt_volume_actual_install_path = MagicMock(return_value='/path/vol')
        vm_plugin.qemu_nbd.kill_nbd_process_by_flag = MagicMock()
        plugin.deactive_volume_if_need = MagicMock()

        volume = MagicMock(installPath='/path/vol')
        cmd = MagicMock(volumes=[volume])
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.unexport_nbd_volumes(req)
            rsp = json.loads(result)

        assert rsp['success'] is True
        vm_plugin.qemu_nbd.kill_nbd_process_by_flag.assert_called_once_with('/path/vol')


@pytest.mark.kvmagent
class TestUploadVmFileHandler:
    def test_upload_vm_file(self):
        plugin = _make_vm_plugin()
        qga = MagicMock()
        qga.os = 'linux'
        qga.guest_exec_bash = MagicMock(return_value=(0, '', ''))
        qga.guest_file_open = MagicMock(return_value=1)
        qga.call_qga_command = MagicMock(return_value={'count': 3})
        qga.guest_file_close = MagicMock()
        vm_plugin.VmQga = MagicMock(return_value=qga)
        def _fake_reconnect(_func):
            def _wrapper(*_args, **_kwargs):
                return MagicMock()
            return _wrapper
        vm_plugin.LibvirtAutoReconnect = _fake_reconnect

        cmd = MagicMock(
            vmUuid='vm-uuid',
            fileType='Script',
            scriptType='Shell',
            fileContent='echo',
            dstPath='/tmp/file',
            param='',
        )
        with patch.object(vm_plugin.jsonobject, 'loads', return_value=cmd):
            req = _make_req({})
            result = plugin.upload_vm_file(req)
            rsp = json.loads(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestWaitSecondaryVmReadyHandler:
    def test_wait_secondary_vm_ready(self):
        plugin = _make_vm_plugin()
        vm_plugin.linux.wait_callback_success = MagicMock(return_value=True)

        req = _make_req({'vmInstanceUuid': 'vm-uuid', 'coloCheckTimeout': 10})
        result = plugin.wait_secondary_vm_ready(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
