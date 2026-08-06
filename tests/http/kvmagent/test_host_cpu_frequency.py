# -*- coding: utf-8 -*-
"""HTTP integration coverage for stable CPU frequency host facts."""

from unittest.mock import patch

import pytest

from kvmagent.plugins import host_plugin
from zstacklib.test.utils.http_test_client import HttpTestClient


def _host_plugin():
    plugin = host_plugin.HostPlugin()
    plugin.config = {}
    plugin.host_uuid = 'integration-test-host'
    plugin.IS_YUM = False
    return plugin


def _shell_call(model_name, processor_frequencies):
    def call(command, *args, **kwargs):
        if 'qemu-img --version' in command:
            return '6.2.0'
        if 'model name|cpu MHz' in command:
            return '%s\n3100.000' % model_name
        if command == 'dmidecode -s processor-frequency':
            return processor_frequencies
        if "'/per socket/" in command or "'/per cluster/" in command:
            return '8'
        if "'/per core/" in command:
            return '2'
        if command == 'uptime -s':
            return '2026-08-06 00:00:00'
        if 'ipmitool mc info' in command:
            return ''
        if command.startswith('dmidecode'):
            return 'unknown'
        return ''

    return call


def _shell_run(command, *args, **kwargs):
    if command == 'dmidecode':
        return 0
    if command in ('grep vmx /proc/cpuinfo',
                   'grep -w ept /proc/cpuinfo'):
        return 0
    return 1


@pytest.mark.http
@pytest.mark.integration
@pytest.mark.parametrize('model_name, processor_frequencies, expected_cpu_ghz', [
    ('Intel(R) Xeon(R) CPU E5-2620 v4 @ 2.10GHz',
     '3100 MHz\n3100 MHz', '2.10'),
    ('Hygon C86-4G (OPN:7490)', '2700 MHz\n2700 MHz', '2.70'),
    ('Invalid CPU @ 0GHz', '2700 MHz\n2700 MHz', '2.70'),
    ('Hygon C86-4G (OPN:7490)', 'Unknown', None),
    ('Hygon C86-4G (OPN:7490)', '2700 MHz\nUnknown', None),
    ('Hygon C86-4G (OPN:7490)', '2700 MHz\n3100 MHz', None),
])
def test_host_fact_reports_static_cpu_frequency_over_http(
        model_name, processor_frequencies, expected_cpu_ghz):
    plugin = _host_plugin()
    client = HttpTestClient()
    client.register_async_uri(plugin.FACT_PATH, plugin.fact)
    client.start()

    try:
        with patch.object(
                host_plugin.shell, 'call',
                side_effect=_shell_call(model_name, processor_frequencies)), \
                patch.object(host_plugin.shell, 'run', side_effect=_shell_run), \
                patch.object(
                    host_plugin.network_ipv6,
                    'collect_reportable_agent_addresses', return_value=[]), \
                patch.object(
                    host_plugin.misc, 'isHyperConvergedHost',
                    return_value=False), \
                patch.object(
                    host_plugin.linux, 'get_libvirt_version',
                    return_value='6.0.0'), \
                patch.object(
                    host_plugin.linux, 'get_libvirt_package_version',
                    return_value='6.0.0'), \
                patch.object(
                    host_plugin.linux, 'get_iscsi_initiator_name',
                    return_value='iqn.integration-test'), \
                patch.object(
                    host_plugin.linux, 'get_socket_num', return_value=2), \
                patch.object(
                    host_plugin.qemu, 'get_path',
                    return_value='/usr/bin/qemu-system-x86_64'), \
                patch.object(
                    host_plugin.qemu, 'get_version_from_exe_file',
                    return_value='6.2.0'), \
                patch.object(
                    plugin, '_get_features_in_libvirt', return_value=None), \
                patch.object(
                    plugin, '_get_host_cpu_model', return_value='Skylake'), \
                patch.object(
                    plugin, '_get_cpu_cache', return_value=[64, 1024, 16384]):
            rsp = client.post_async(plugin.FACT_PATH, {})

        assert rsp.success is True
        assert rsp.hostCpuModelName == model_name
        assert rsp.cpuGHz == expected_cpu_ghz
    finally:
        client.stop()
