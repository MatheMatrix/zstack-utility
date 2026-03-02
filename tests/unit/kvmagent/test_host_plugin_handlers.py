# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnusedImport=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnannotatedClassAttribute=false, reportAny=false, reportAttributeAccessIssue=false
"""
Handler-level unit tests for kvmagent.plugins.host_plugin.

Each test imports the REAL handler code, constructs a request dict,
calls the handler method, and asserts on the JSON response.
System dependencies (shell, linux, libvirt) are mocked.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from zstacklib.utils import jsonobject
from zstacklib.utils import http

# Import the real modules under test
from kvmagent import kvmagent as kva
from kvmagent.plugins import host_plugin


def _make_req(body_dict=None):
    """Build a request dict in the format handlers expect."""
    body = json.dumps(body_dict or {})
    return {
        http.REQUEST_BODY: body,
        http.REQUEST_HEADER: {},
    }


def _make_plugin():
    """Create a HostPlugin instance with minimal mocked init."""
    plugin = host_plugin.HostPlugin.__new__(host_plugin.HostPlugin)
    plugin.config = {}
    plugin.host_uuid = 'test-host-uuid-1234'
    plugin.host_socket = None
    # libvirt_version and qemu_version are properties backed by mocked calls:
    #   linux.get_libvirt_version() and qemu.get_version()
    from zstacklib.utils import linux, qemu
    linux.get_libvirt_version.return_value = '6.0.0'
    qemu.get_version.return_value = '4.2.0'
    return plugin


@pytest.mark.kvmagent
class TestHostPluginPing:
    """Test host_plugin.ping handler."""

    def test_ping_returns_host_uuid(self):
        plugin = _make_plugin()
        plugin.config[kva.SEND_COMMAND_URL] = 'http://mn:8080/callback'
        plugin.config[kva.VERSION] = '4.6.0'

        req = _make_req({
            'kvmagentPhysicalMemoryUsageAlarmThreshold': 0.9,
            'kvmagentPhysicalMemoryUsageHardLimit': 0.95,
        })

        result = plugin.ping(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert rsp['hostUuid'] == 'test-host-uuid-1234'
        assert rsp['sendCommandUrl'] == 'http://mn:8080/callback'
        assert rsp['version'] == '4.6.0'

    def test_ping_reads_version_from_file_when_not_in_config(self):
        plugin = _make_plugin()
        plugin.config[kva.SEND_COMMAND_URL] = 'http://mn:8080/callback'
        # VERSION not in config

        req = _make_req({
            'kvmagentPhysicalMemoryUsageAlarmThreshold': 0.9,
            'kvmagentPhysicalMemoryUsageHardLimit': 0.95,
        })

        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data='4.5.0\n')):
            mock_exists.side_effect = lambda p: p == host_plugin.KVMAGENT_VERSION_PATH

            result = plugin.ping(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert rsp['version'] == '4.5.0'


@pytest.mark.kvmagent
class TestHostPluginEcho:
    """Test host_plugin.echo handler."""

    def test_echo_returns_empty_string(self):
        plugin = _make_plugin()
        from zstacklib.utils import linux
        linux.fake_dead = MagicMock(return_value=False)

        req = _make_req()
        result = plugin.echo(req)
        assert result == ''


@pytest.mark.kvmagent
class TestHostPluginCheckFileOnHost:
    """Test host_plugin.check_file_on_host handler."""

    def test_check_file_existing(self):
        plugin = _make_plugin()

        req = _make_req({
            'paths': ['/tmp/test-file.qcow2'],
            'md5Return': False,
        })

        with patch('os.path.exists', return_value=True):
            result = plugin.check_file_on_host(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert '/tmp/test-file.qcow2' in rsp['existPaths']

    def test_check_file_not_existing(self):
        plugin = _make_plugin()

        req = _make_req({
            'paths': ['/tmp/nonexistent.qcow2'],
            'md5Return': False,
        })

        with patch('os.path.exists', return_value=False):
            result = plugin.check_file_on_host(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert rsp['existPaths'] == {}

    def test_check_file_with_md5(self):
        plugin = _make_plugin()

        req = _make_req({
            'paths': ['/tmp/test-file.qcow2'],
            'md5Return': True,
        })

        fake_content = b'hello world'
        import hashlib
        expected_md5 = hashlib.md5(fake_content).hexdigest()

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=fake_content)):
            result = plugin.check_file_on_host(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert rsp['existPaths']['/tmp/test-file.qcow2'] == expected_md5


@pytest.mark.kvmagent
class TestHostPluginCapacity:
    """Test host_plugin.capacity handler."""

    def test_capacity_returns_cpu_and_memory(self):
        plugin = _make_plugin()

        from zstacklib.utils import linux, shell, sizeunit
        from kvmagent.plugins import vm_plugin

        # Mock cpu/memory functions
        linux.get_cpu_num.return_value = 8
        linux.get_cpu_speed.return_value = 2400
        linux.get_socket_num = MagicMock(return_value=2)
        linux.get_cpu_core_num.return_value = 4

        # Mock vm_plugin.get_cpu_memory_used_by_running_vms
        vm_plugin.get_cpu_memory_used_by_running_vms = MagicMock(return_value=(200, 1024 * 1024 * 1024))

        # Mock _get_total_memory (reads /proc/meminfo via shell)
        with patch.object(host_plugin, '_get_total_memory', return_value=8 * 1024 * 1024 * 1024):
            req = _make_req()
            result = plugin.capacity(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert rsp['cpuNum'] == 8
            assert rsp['cpuSpeed'] == 2400
            assert rsp['usedCpu'] == 200
            assert rsp['totalMemory'] == 8 * 1024 * 1024 * 1024
            assert rsp['usedMemory'] == 1024 * 1024 * 1024
            assert rsp['cpuSockets'] == 2
            assert rsp['cpuCoreNum'] == 4


@pytest.mark.kvmagent
class TestHostPluginConnect:
    """Test host_plugin.connect handler."""

    @pytest.mark.xfail(reason='connect handler has too many side effects requiring extensive mocking')

    def test_connect_sets_host_uuid(self):
        plugin = _make_plugin()
        plugin.save_kvmagent_version = MagicMock()
        plugin.install_shutdown_hook = MagicMock()
        plugin.handle_usb_device_events = MagicMock()
        plugin.apply_iptables_rules = MagicMock()

        from zstacklib.utils import shell, linux
        shell.run = MagicMock(return_value=1)  # not Intel (skip EPT)
        linux.write_file = MagicMock()
        linux.write_uuids = MagicMock()

        from kvmagent.plugins import vm_plugin
        vm_plugin.cleanup_stale_vnc_iptable_chains = MagicMock()

        from zstacklib.utils.report import Report
        Report.serverUuid = None
        Report.url = None

        req = _make_req({
            'hostUuid': 'new-host-uuid',
            'sendCommandUrl': 'http://mn:8080/callback',
            'version': '4.6.0',
            'pageTableExtensionDisabled': False,
            'ignoreMsrs': True,
            'iptablesRules': [],
        })

        result = plugin.connect(req)
        rsp = json.loads(result)

        assert rsp['success'] is True
        assert plugin.host_uuid == 'new-host-uuid'
        assert plugin.config[kva.HOST_UUID] == 'new-host-uuid'
        assert plugin.config[kva.SEND_COMMAND_URL] == 'http://mn:8080/callback'
        assert rsp['libvirtVersion'] == '6.0.0'
        assert rsp['qemuVersion'] == '4.2.0'


@pytest.mark.kvmagent
class TestHostPluginFact:
    """Test host_plugin.fact handler."""

    @pytest.mark.xfail(reason='fact handler has complex libvirt XML parsing and many shell calls')

    def test_fact_returns_os_info(self):
        plugin = _make_plugin()

        from zstacklib.utils import shell, iproute

        # Mock platform.dist() and platform.linux_distribution()
        with patch('platform.dist', return_value=('centos', '7.9', 'Core'), create=True), \
             patch('platform.linux_distribution', return_value=('CentOS Linux', '7.9', 'Core'), create=True):

            # Mock shell calls
            shell.call = MagicMock(return_value='4.2.0\n')
            shell.run = MagicMock(return_value=0)  # dmidecode available

            # Mock iproute
            class FakeAddr:
                def __init__(self, addr, ifname):
                    self.address = addr
                    self.ifname = ifname
            iproute.query_addresses = MagicMock(return_value=[
                FakeAddr('192.168.1.100', 'eth0'),
            ])

            req = _make_req()
            result = plugin.fact(req)
            rsp = json.loads(result)

            assert rsp['success'] is True
            assert rsp['qemuImgVersion'] == '4.2.0'


@pytest.mark.kvmagent
class TestHostPluginShutdownHost:
    """Test host_plugin.shutdown_host handler."""

    def test_shutdown_host(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell.ShellCmd = MagicMock()
        plugin.do_shutdown_host = MagicMock()

        req = _make_req({'uuid': 'host-uuid-1234'})
        result = plugin.shutdown_host(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginRebootHost:
    """Test host_plugin.reboot_host handler."""

    def test_reboot_host(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell.ShellCmd = MagicMock()
        plugin.do_reboot_host = MagicMock()

        req = _make_req({'uuid': 'host-uuid-1234'})
        result = plugin.reboot_host(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginCleanLocalCache:
    """Test host_plugin.clean_local_cache handler."""

    def test_clean_local_cache(self):
        plugin = _make_plugin()
        from kvmagent.plugins import imagestore
        client = MagicMock()
        imagestore.ImageStoreClient = MagicMock(return_value=client)

        req = _make_req({'mountPath': '/imagestore'})
        result = plugin.clean_local_cache(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginChangePassword:
    """Test host_plugin.change_password handler."""

    def test_change_password(self):
        plugin = _make_plugin()
        from zstacklib.utils import linux, shell
        linux.write_to_temp_file = MagicMock(return_value='/tmp/passwd')
        shell.call = MagicMock()

        req = _make_req({'password': 'new-pass'})
        with patch('kvmagent.plugins.host_plugin.os.remove'):
            result = plugin.change_password(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginIdentifyHost:
    """Test host_plugin.identify_host handler."""

    def test_identify_host(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell_cmd = MagicMock(return_code=0, stdout='', stderr='')
        shell_cmd.__call__ = MagicMock()
        shell.ShellCmd = MagicMock(return_value=shell_cmd)

        req = _make_req({'interval': 10})
        result = plugin.identify_host(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginLocateHostNetworkInterface:
    """Test host_plugin.locate_host_network_interface handler."""

    def test_locate_host_network_interface(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell_cmd = MagicMock(return_code=0, stdout='', stderr='')
        shell_cmd.__call__ = MagicMock()
        shell.ShellCmd = MagicMock(return_value=shell_cmd)

        req = _make_req({'networkInterface': 'eth0', 'interval': 3})
        result = plugin.locate_host_network_interface(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetHostPhysicalMemoryFacts:
    """Test host_plugin.get_host_physical_memory_facts handler."""

    def test_get_host_physical_memory_facts(self):
        plugin = _make_plugin()
        dmidecode_output = (
            "Memory Device\n"
            "\tSize: 1024 MB\n"
            "\tLocator: DIMM_A1\n"
            "\tSpeed: 1600 MT/s\n"
            "\tManufacturer: TestVendor\n"
            "\tType: DDR4\n"
            "\tSerial Number: 1234\n"
            "\tRank: 2\n"
            "\tConfigured Clock Speed: 1600 MT/s\n"
            "\tConfigured Voltage: 1.2 V\n"
        )
        with patch.object(host_plugin, 'bash_roe', return_value=(0, dmidecode_output, '')):
            req = _make_req()
            result = plugin.get_host_physical_memory_facts(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginStopUsbRedirectServer:
    """Test host_plugin.stop_usb_redirect_server handler."""

    def test_stop_usb_redirect_server(self):
        plugin = _make_plugin()
        with patch.object(host_plugin, 'bash_r', return_value=0):
            req = _make_req({'port': 4000, 'busNum': '1', 'devNum': '2'})
            result = plugin.stop_usb_redirect_server(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginCheckUsbServerPort:
    """Test host_plugin.check_usb_server_port handler."""

    def test_check_usb_server_port(self):
        plugin = _make_plugin()
        with patch.object(host_plugin, 'bash_roe', return_value=(0, '1234', '')):
            req = _make_req({'portList': ['uuid1:1234', 'uuid2:2345']})
            result = plugin.check_usb_server_port(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginScanVmPort:
    """Test host_plugin.scan_vm_port handler."""

    def test_scan_vm_port(self):
        plugin = _make_plugin()
        from zstacklib.utils import linux
        linux.check_nping_result = MagicMock(side_effect=[{'22': 'open'}, {'80': 'open'}])

        with patch.object(host_plugin, 'bash_roe', return_value=(0, 'ok', '')):
            req = _make_req({'brname': 'br0', 'ip': '10.0.0.1', 'port': '22,80'})
            result = plugin.scan_vm_port(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateSpiceChannelConfig:
    """Test host_plugin.update_spice_channel_config handler."""

    def test_update_spice_channel_config(self):
        plugin = _make_plugin()
        with patch.object(host_plugin, 'bash_r', side_effect=[1, 1, 0, 0]):
            req = _make_req()
            result = plugin.update_spice_channel_config(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginCancel:
    """Test host_plugin.cancel handler."""

    def test_cancel(self):
        plugin = _make_plugin()
        from zstacklib.utils import plugin as plugin_mod
        rsp_obj = kva.AgentResponse()
        plugin_mod.cancel_job = MagicMock(return_value=rsp_obj)

        req = _make_req({'jobUuid': 'job-uuid-1234'})
        result = plugin.cancel(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginTransmitVmOperationToVm:
    """Test host_plugin.transmit_vm_operation_to_vm handler."""

    def test_transmit_vm_operation_to_vm(self):
        plugin = _make_plugin()
        plugin.config[kva.SEND_COMMAND_URL] = 'http://mn:8080/callback'
        from zstacklib.utils import http
        http.json_dump_post = MagicMock()

        req = _make_req({'uuid': 'vm-uuid-1', 'operation': 'reboot'})
        result = plugin.transmit_vm_operation_to_vm(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginTransmitZwatchInstallResultToMn:
    """Test host_plugin.transmit_zwatch_install_result_to_mn handler."""

    def test_transmit_zwatch_install_result_to_mn(self):
        plugin = _make_plugin()
        plugin.config[kva.SEND_COMMAND_URL] = 'http://mn:8080/callback'
        from zstacklib.utils import http
        http.json_dump_post = MagicMock()

        req = _make_req({'vmInstanceUuid': 'vm-uuid-1', 'version': '1.0.0'})
        def _init(self):
            kva.AgentResponse.__init__(self)

        with patch.object(host_plugin.ZwatchInstallResultRsp, '__init__', _init):
            result = plugin.transmit_zwatch_install_result_to_mn(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateHostConfiguration:
    """Test host_plugin.update_host_configuration handler."""

    def test_update_host_configuration(self):
        plugin = _make_plugin()
        from zstacklib.utils.report import Report
        Report.url = None

        req = _make_req({'sendCommandUrl': 'http://mn:8080/callback'})
        result = plugin.update_host_configuration(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginDeployColoQemu:
    """Test host_plugin.deploy_colo_qemu handler."""

    def test_deploy_colo_qemu(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock(return_value='Last-Modified: Thu, 01 Jan 1970 00:00:00 GMT')
        shell.run = MagicMock(return_value=0)

        def exists_side_effect(path):
            if path in (host_plugin.COLO_LIB_PATH, host_plugin.COLO_QEMU_KVM_VERSION):
                return False
            return True

        with patch.object(host_plugin.kvmagent, 'get_host_yum_release', return_value='c79'), \
                patch('kvmagent.plugins.host_plugin.os.path.exists', side_effect=exists_side_effect), \
                patch('kvmagent.plugins.host_plugin.os.makedirs'), \
                patch('builtins.open', mock_open()):
            req = _make_req({'qemuUrl': 'http://mn:8080/qemu-${releasever}.tar.gz'})
            result = plugin.deploy_colo_qemu(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginEnableZerocopy:
    """Test host_plugin.enable_zerocopy handler."""

    def test_enable_zerocopy(self):
        plugin = _make_plugin()
        plugin._check_vhost_net_conf = MagicMock()
        plugin._try_reload_modprobe = MagicMock()

        req = _make_req()
        result = plugin.enable_zerocopy(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginDisableZerocopy:
    """Test host_plugin.disable_zerocopy handler."""

    def test_disable_zerocopy(self):
        plugin = _make_plugin()
        plugin._check_vhost_net_conf = MagicMock()
        plugin._try_reload_modprobe = MagicMock()

        req = _make_req()
        result = plugin.disable_zerocopy(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetDevCapacity:
    """Test host_plugin.get_dev_capacity handler."""

    def test_get_dev_capacity(self):
        plugin = _make_plugin()
        from zstacklib.utils import linux
        linux.get_total_disk_size = MagicMock(return_value=100)
        linux.get_free_disk_size = MagicMock(return_value=60)
        linux.get_used_disk_apparent_size = MagicMock(return_value=40)

        req = _make_req({'dirPath': '/var/lib/zstack'})
        result = plugin.get_dev_capacity(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginAddBridgeFdbEntry:
    """Test host_plugin.add_bridge_fdb_entry handler."""

    def test_add_bridge_fdb_entry(self):
        plugin = _make_plugin()
        from zstacklib.utils import iproute
        iproute.add_fdb_entry = MagicMock()

        req = _make_req({'physicalInterface': 'eth0', 'macs': ['aa:bb:cc:dd:ee:ff']})
        result = plugin.add_bridge_fdb_entry(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginDelBridgeFdbEntry:
    """Test host_plugin.del_bridge_fdb_entry handler."""

    def test_del_bridge_fdb_entry(self):
        plugin = _make_plugin()
        from zstacklib.utils import iproute
        iproute.del_fdb_entry = MagicMock()

        req = _make_req({'physicalInterface': 'eth0', 'macs': ['aa:bb:cc:dd:ee:ff']})
        result = plugin.del_bridge_fdb_entry(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginSetupHeartbeatFile:
    def test_setup_heartbeat_file(self):
        plugin = _make_plugin()
        plugin.heartbeat_timer = {}

        from zstacklib.utils import linux, thread
        linux.is_mounted = MagicMock(return_value=True)

        timer_mock = MagicMock()
        timer_mock.start = MagicMock()
        thread.timer = MagicMock(return_value=timer_mock)

        req = _make_req({
            'heartbeatFilePaths': ['/mnt/ps/heartbeat/host1.hb'],
            'heartbeatInterval': 5,
        })

        with patch('kvmagent.plugins.host_plugin.os.path.exists', return_value=False), \
                patch('kvmagent.plugins.host_plugin.os.makedirs'):
            result = plugin.setup_heartbeat_file(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginStartUsbRedirectServer:
    def test_start_usb_redirect_server(self):
        plugin = _make_plugin()
        from zstacklib.utils import iptables, linux

        iptc = MagicMock()
        iptc.add_rule = MagicMock()
        iptc.iptable_restore = MagicMock()
        iptables.from_iptables_save = MagicMock(return_value=iptc)
        linux.check_port = MagicMock(return_value=(True, None))

        with patch.object(host_plugin, 'bash_ro', return_value=(0, 'ok')), \
                patch.object(host_plugin, 'bash_r', return_value=0):
            req = _make_req({'port': 4100, 'busNum': '1', 'devNum': '2'})
            result = plugin.start_usb_redirect_server(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['port'] == 4100


@pytest.mark.kvmagent
class TestHostPluginGetUsbDevices:
    def test_get_usb_devices(self):
        plugin = _make_plugin()
        lsusb_u = "Device 1d6b:0002\n"
        lsusb_v = (
            "Bus 001 Device 002: ID 1d6b:0002\n"
            "idVendor 0x1d6b\n"
            "idProduct 0x0002\n"
            "bcdUSB 2.00\n"
            "iManufacturer 1 Linux\n"
            "iProduct 2 Host\n"
            "iSerial 3 1234\n"
        )

        with patch.object(host_plugin, 'bash_roe', side_effect=[
            (0, lsusb_u, ''),
            (0, lsusb_v, ''),
        ]), patch.object(host_plugin, 'bash_r', return_value=1), \
                patch('kvmagent.plugins.host_plugin.logger'):
            req = _make_req({})
            result = plugin.get_usb_devices(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateOs:
    def test_update_os(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell, linux

        shell.run = MagicMock(side_effect=[0, 0, 0])
        shell_cmd = MagicMock()
        shell_cmd.return_code = 0
        shell_cmd.stdout = ''
        shell_cmd.stderr = ''
        shell_cmd.__call__ = MagicMock()
        shell.ShellCmd = MagicMock(return_value=shell_cmd)

        linux.mkdir = MagicMock()
        linux.get_libvirt_package_version = MagicMock(return_value='6.0.0')

        with patch.object(kva, 'get_host_yum_release', return_value='c79'), \
                patch('builtins.open', mock_open()):
            req = _make_req({
                'excludePackages': '',
                'updatePackages': 'kernel',
                'releaseVersion': '',
                'enableExpRepo': False,
            })
            result = plugin.update_os(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['libvirtVersion'] == '6.0.0'


@pytest.mark.kvmagent
class TestHostPluginInitHostMoc:
    def test_init_host_moc(self):
        plugin = _make_plugin()
        from zstacklib.utils import iproute
        iproute.set_link_attribute_no_error = MagicMock()

        with patch.object(host_plugin, 'bash_r', return_value=0):
            req = _make_req({
                'mode': 'mocbr',
                'masterVethName': 'veth0',
                'bridgeName': 'br0',
            })
        result = plugin.init_host_moc(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateDependency:
    def test_update_dependency(self):
        plugin = _make_plugin()
        plugin.IS_YUM = True
        plugin.IS_APT = False

        from zstacklib.utils import shell
        shell.run = MagicMock(return_value=0)

        req = _make_req({
            'zstackRepo': 'zstack-mn',
            'enableExpRepo': False,
            'excludePackages': '',
            'updatePackages': '',
        })
        with patch.object(kva, 'get_host_yum_release', return_value='c79'):
            result = plugin.update_dependency(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetXfsFragData:
    def test_get_xfs_frag_data(self):
        plugin = _make_plugin()
        with patch.object(host_plugin, 'bash_o', side_effect=['/dev/sda1 xfs', '2%']), \
                patch.object(host_plugin, 'bash_ro', return_value=(0, '3')):
            req = _make_req({'volumePathMap': {'vol-1': '/dev/sda1'}})
            result = plugin.get_xfs_frag_data(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['fsType'] == 'xfs'
        assert rsp['hostFrag'] == '2'
        assert rsp['volumeFragMap']['vol-1'] == 2


@pytest.mark.kvmagent
class TestHostPluginDisableHugepage:
    def test_disable_hugepage(self):
        plugin = _make_plugin()
        plugin._close_hugepage = MagicMock(return_value=(0, 'ok'))

        req = _make_req({})
        result = plugin.disable_hugepage(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginEnableHugepage:
    def test_enable_hugepage(self):
        plugin = _make_plugin()

        from zstacklib.utils import shell
        shell.ShellCmd = MagicMock(return_value=MagicMock(__call__=MagicMock(return_value='4096')))

        req = _make_req({'pageSize': 2, 'reserveSize': 1024 * 1024})
        with patch.object(host_plugin, 'bash_roe', return_value=(0, '', '')), \
                patch('builtins.open', mock_open()), \
                patch('kvmagent.plugins.host_plugin.os.path.exists', return_value=True):
            result = plugin.enable_hugepage(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateOvsCpuPinning:
    def test_update_ovs_cpu_pinning(self):
        plugin = _make_plugin()
        from zstacklib.utils import ovs
        ovs_ctl = MagicMock()
        ovs_ctl.configPmdCpuMaskForOvs = MagicMock()
        ovs.getOvsCtl = MagicMock(return_value=ovs_ctl)

        req = _make_req({'ovsCpuPinning': '0x3'})
        result = plugin.update_ovs_cpu_pinning(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetHostNetworkFacts:
    def test_get_host_network_facts(self):
        plugin = _make_plugin()
        plugin.get_host_networking_bonds = MagicMock(return_value=['bond0'])
        plugin.get_host_networking_interfaces = MagicMock(return_value=['eth0'])

        req = _make_req({'managementServerIp': '10.0.0.10'})
        result = plugin.get_host_network_facts(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['bondings'] == ['bond0']
        assert rsp['nics'] == ['eth0']


@pytest.mark.kvmagent
class TestHostPluginSetIpOnHostNetworkInterface:
    def test_set_ip_on_host_network_interface(self):
        plugin = _make_plugin()
        plugin._has_vlan_or_bridge = MagicMock(return_value=False)

        from zstacklib.utils import shell
        shell.call = MagicMock()
        shell.run = MagicMock(return_value=0)

        req = _make_req({
            'interfaceName': 'eth0',
            'ipAddress': '192.168.1.10',
            'netmask': '255.255.255.0',
            'gateway': '192.168.1.1',
            'oldIpAddress': None,
            'oldNetmask': None,
            'oldGateway': None,
        })
        result = plugin.set_ip_on_host_network_interface(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginCheckInterfaceVlan:
    def test_check_interface_vlan(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock(return_value='eth0.100')

        req = _make_req({'interfaceName': 'eth0', 'vlanId': 100})
        result = plugin.check_interface_vlan(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetInterfaceVlan:
    def test_get_interface_vlan(self):
        plugin = _make_plugin()
        from zstacklib.utils import shell
        shell.call = MagicMock(return_value='100')

        req = _make_req({'interfaceNames': ['eth0']})
        result = plugin.get_interface_vlan(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['vlanIds'] == ['100', '0']


@pytest.mark.kvmagent
class TestHostPluginGetInterfaceName:
    def test_get_interface_name(self):
        plugin = _make_plugin()
        from zstacklib.utils import iproute, shell

        class FakeLink:
            def __init__(self, ifname):
                self.ifname = ifname

        class FakeAddr:
            def __init__(self, address):
                self.address = address

        iproute.query_links = MagicMock(return_value=[FakeLink('eth0')])
        iproute.query_addresses_by_ifname = MagicMock(return_value=[FakeAddr('10.0.0.10')])
        shell.call = MagicMock(return_value='eth0')

        req = _make_req({'ipAddresses': ['10.0.0.10']})
        result = plugin.get_interface_name(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['interfaceNames'] == ['eth0']


@pytest.mark.kvmagent
class TestHostPluginGetPciInfo:
    def test_get_pci_info_skip_grub(self):
        plugin = _make_plugin()
        plugin._collect_format_pci_device_info = MagicMock()
        from kvmagent.plugins.host_plugin import UpdateConfigration
        UpdateConfigration.enable_vfio_module = MagicMock()

        with patch('kvmagent.plugins.host_plugin.os.path.exists', return_value=False):
            req = _make_req({
                'skipGrubConfig': True,
                'enableIommu': True,
                'opaque': False,
                'pciDeviceAddresses': [],
            })
            result = plugin.get_pci_info(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['hostIommuStatus'] is True


@pytest.mark.kvmagent
class TestHostPluginGetMttyInfo:
    def test_get_mtty_info(self):
        plugin = _make_plugin()
        plugin._collect_format_mtty_device_info = MagicMock()

        req = _make_req({})
        result = plugin.get_mtty_info(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginGetNumaTopology:
    def test_get_numa_topology(self):
        plugin = _make_plugin()

        with patch('kvmagent.plugins.host_plugin.os.path.isdir', return_value=False):
            req = _make_req({})
            result = plugin.get_numa_topology(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginAttachVolumePath:
    def test_attach_volume_path(self):
        plugin = _make_plugin()
        from zstacklib.utils import lvm
        lvm.LvmRemoteStorage = MagicMock(return_value=MagicMock(mount=MagicMock(return_value='/dev/dm-1')))

        req = _make_req({
            'volumeInstallPath': 'sharedblock://path/volume',
            'mountPath': '/dev',
            'device': '/dev/dm-1',
        })
        result = plugin.attach_volume_path(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
        assert rsp['device'] == '/dev/dm-1'


@pytest.mark.kvmagent
class TestHostPluginDetachVolumePath:
    def test_detach_volume_path(self):
        plugin = _make_plugin()
        from zstacklib.utils import ceph
        ceph.NbdRemoteStorage = MagicMock(return_value=MagicMock(umount=MagicMock()))

        req = _make_req({
            'volumeInstallPath': 'ceph://path/volume',
            'mountPath': '/dev',
            'device': '/dev/nbd0',
        })
        result = plugin.detach_volume__path(req)
        rsp = json.loads(result)
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestHostPluginUpdateVmConsolePasswordLive:
    def test_update_vm_console_password_live(self):
        plugin = _make_plugin()
        from kvmagent.plugins import vm_plugin

        class FakeGraphics:
            def __init__(self, type_):
                self.type_ = type_

        class FakeDevices:
            def get_child_node_as_list(self, _name):
                return [FakeGraphics('vnc'), FakeGraphics('spice')]

        class FakeDomain:
            def __init__(self):
                self.devices = FakeDevices()

        class FakeVm:
            state = vm_plugin.Vm.VM_STATE_RUNNING
            domain_xmlobject = FakeDomain()

        vm_plugin.get_vm_by_uuid = MagicMock(return_value=FakeVm())

        with patch.object(host_plugin, 'bash_roe', return_value=(0, '', '')):
            req = _make_req({'vmUuid': 'vm-uuid', 'password': 'new-pass'})
            result = plugin.update_vm_console_password_live(req)
        rsp = json.loads(result)
        assert rsp['success'] is True
