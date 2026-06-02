# -*- coding: utf-8 -*-
from zstackctl import management_network_ipv6


def test_validate_ip_accepts_ipv4_and_ipv6():
    assert management_network_ipv6.validate_ip('192.168.10.10')
    assert management_network_ipv6.validate_ip('2001:db8::10')
    assert not management_network_ipv6.validate_ip('not-an-ip')


def test_ip_to_hostname_builds_stable_hostname_from_ipv6():
    assert management_network_ipv6.ip_to_hostname('192.168.10.10') == '192-168-10-10'
    assert management_network_ipv6.ip_to_hostname('[2001:db8::10]') == '2001-db8--10'
    assert management_network_ipv6.ip_to_hostname(None) == ''
    assert management_network_ipv6.ip_to_hostname(b'2001:db8::10') == '2001-db8--10'


def test_format_hosts_bracket_ipv6_and_keep_ipv4_unchanged():
    assert management_network_ipv6.format_host_for_url_or_jdbc('192.168.10.10') == '192.168.10.10'
    assert management_network_ipv6.format_host_for_url_or_jdbc('2001:db8::10') == '[2001:db8::10]'
    assert management_network_ipv6.format_host_for_url_or_jdbc('[2001:db8::10]') == '[2001:db8::10]'
    assert management_network_ipv6.format_host_for_url_or_jdbc(None) is None


def test_build_mysql_jdbc_url_brackets_ipv6_host():
    assert management_network_ipv6.build_mysql_jdbc_url('192.168.10.10', 3306) == 'jdbc:mysql://192.168.10.10:3306'
    assert management_network_ipv6.build_mysql_jdbc_url('2001:db8::10', 3306) == 'jdbc:mysql://[2001:db8::10]:3306'


def test_get_ip_version_accepts_bracketed_ipv6():
    assert management_network_ipv6.get_ip_version('192.168.10.10') == management_network_ipv6.IPV4_VERSION
    assert management_network_ipv6.get_ip_version('[2001:db8::10]') == management_network_ipv6.IPV6_VERSION
    assert management_network_ipv6.get_ip_version('invalid') is None


def test_has_mixed_ip_versions_detects_ha_node_mismatch():
    assert management_network_ipv6.has_mixed_ip_versions([
        '192.168.10.10',
        '2001:db8::10',
        '192.168.10.20',
    ])
    assert not management_network_ipv6.has_mixed_ip_versions([
        '2001:db8::10',
        '[2001:db8::11]',
        'ha-node-name',
    ])


def test_same_ip_version_transition_rejects_family_switch():
    assert management_network_ipv6.is_same_ip_version_transition('192.168.10.10', '192.168.10.20')
    assert management_network_ipv6.is_same_ip_version_transition('2001:db8::10', '[2001:db8::20]')
    assert not management_network_ipv6.is_same_ip_version_transition('192.168.10.10', '2001:db8::20')
    assert not management_network_ipv6.is_same_ip_version_transition('2001:db8::10', '192.168.10.20')
    assert not management_network_ipv6.is_same_ip_version_transition('192.168.10.10', 'not-an-ip')


def test_extract_db_url_host_reads_ipv4_ipv6_and_localhost():
    assert management_network_ipv6.extract_db_url_host('jdbc:mysql://192.168.10.10:3306/zstack') == '192.168.10.10'
    assert management_network_ipv6.extract_db_url_host('jdbc:mysql://[2001:db8::10]:3306/zstack') == '2001:db8::10'
    assert management_network_ipv6.extract_db_url_host('jdbc:mysql://localhost:3306/zstack') == 'localhost'
    assert management_network_ipv6.extract_db_url_host('jdbc:mysql://12345.0.0.1:3306/zstack') is None


def test_replace_db_url_host_formats_new_host_by_ip_version():
    assert management_network_ipv6.replace_db_url_host(
        'jdbc:mysql://192.168.10.10:3306/zstack',
        '2001:db8::20',
    ) == 'jdbc:mysql://[2001:db8::20]:3306/zstack'
    assert management_network_ipv6.replace_db_url_host(
        'jdbc:mysql://[2001:db8::10]:3306/zstack',
        '192.168.10.20',
    ) == 'jdbc:mysql://192.168.10.20:3306/zstack'


def test_ip_addr_output_has_ip_accepts_ipv4_and_ipv6_addresses():
    addr_output = '''
2: br_eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 172.24.246.247/16 brd 172.24.255.255 scope global br_eth0
       valid_lft forever preferred_lft forever
    inet6 fd00:172:24:246::247/64 scope global
       valid_lft forever preferred_lft forever
'''
    assert management_network_ipv6.ip_addr_output_has_ip('172.24.246.247', addr_output)
    assert management_network_ipv6.ip_addr_output_has_ip('fd00:172:24:246::247', addr_output)
    assert management_network_ipv6.ip_addr_output_has_ip('[fd00:172:24:246::247]', addr_output)
    assert not management_network_ipv6.ip_addr_output_has_ip('fd00:172:24:246::248', addr_output)
    assert not management_network_ipv6.ip_addr_output_has_ip('not-an-ip', addr_output)


def test_build_java_ip_stack_opts_switches_to_ipv6_stack_for_ipv6_mn():
    opts = management_network_ipv6.build_java_ip_stack_opts('fd00:172:24:246::247', [
        '-Djdk.tls.trustNameService=true',
        '-Djava.net.preferIPv4Stack=true',
        '-Djava.net.preferIPv6Addresses=false',
        '-Xmx12288M',
    ])

    assert '-Djava.net.preferIPv4Stack=true' not in opts
    assert '-Djava.net.preferIPv6Addresses=false' not in opts
    assert '-Djava.net.preferIPv4Stack=false' in opts
    assert '-Djava.net.preferIPv6Addresses=true' in opts
    assert '-Xmx12288M' in opts


def test_build_java_ip_stack_opts_keeps_ipv4_preference_but_enables_dual_stack():
    opts = [
        '-Djava.net.preferIPv4Stack=true',
        '-Djava.net.preferIPv6Addresses=true',
        '-Xmx12288M',
    ]

    actual = management_network_ipv6.build_java_ip_stack_opts('172.24.246.247', opts)

    assert '-Djava.net.preferIPv4Stack=true' not in actual
    assert '-Djava.net.preferIPv6Addresses=true' not in actual
    assert '-Djava.net.preferIPv4Stack=false' in actual
    assert '-Xmx12288M' in actual


def test_add_ip6_accepts_ipv6_without_nic():
    addr_output = '''
2: br_eth0    inet 172.24.249.182/16 brd 172.24.255.255 scope global br_eth0
3: eth1    inet 10.10.10.10/24 brd 10.10.10.255 scope global eth1
'''
    route_output = 'default via 172.24.0.1 dev eth1 proto static metric 100'

    nic = management_network_ipv6.select_add_ip6_interface(
        None,
        '172.24.249.182',
        route_output,
        addr_output,
    )

    assert nic == 'br_eth0'
    assert management_network_ipv6.build_add_ip6_command(
        'fd00:172:24:249::182',
        '64',
        nic,
    ) == ['ip', '-6', 'addr', 'add', 'fd00:172:24:249::182/64', 'dev', 'br_eth0']


def test_add_ip6_selects_interface_from_ipv6_management_ip():
    addr_output = '''
2: br_eth0    inet6 fd00:172:24:249::182/64 scope global
3: eth1    inet6 fd00:10:10::10/64 scope global
'''

    nic = management_network_ipv6.select_add_ip6_interface(
        None,
        'fd00:172:24:249::182',
        '',
        addr_output,
    )

    assert nic == 'br_eth0'


def test_add_ip6_falls_back_to_default_route_interface():
    assert management_network_ipv6.select_add_ip6_interface(
        None,
        None,
        'default via 172.24.0.1 dev br_eth0 proto static metric 100',
        '',
    ) == 'br_eth0'


def test_add_ip6_falls_back_to_ipv6_default_route_interface():
    assert management_network_ipv6.select_add_ip6_interface(
        None,
        None,
        'default via fd00:172:24::1 dev br_eth0 proto ra metric 100',
        '',
    ) == 'br_eth0'


def test_add_ip6_rejects_invalid_input():
    assert not management_network_ipv6.validate_ipv6('172.24.249.182')
    assert not management_network_ipv6.validate_ipv6('not-an-ip')
    assert management_network_ipv6.normalize_ipv6_prefix('129') is None
    assert management_network_ipv6.normalize_ipv6_prefix('-1') is None
    assert management_network_ipv6.normalize_ipv6_prefix('64') == 64
    assert management_network_ipv6.build_add_ip6_command('172.24.249.182', '64', 'br_eth0') is None
    assert management_network_ipv6.build_add_ip6_command('fd00:172:24:249::182', '129', 'br_eth0') is None
    assert management_network_ipv6.build_add_ip6_command('fd00:172:24:249::182', '64', 'br eth0') is None


def test_management_server_requires_ipv6_stack_only_for_ipv6_management_config():
    assert management_network_ipv6.management_server_requires_ipv6_stack({
        'management.server.ip': '172.24.249.182',
    }) is False
    assert management_network_ipv6.management_server_requires_ipv6_stack({
        'management.server.ip': 'fd00:172:24:249::182',
    }) is True
    assert management_network_ipv6.management_server_requires_ipv6_stack({
        'management.server.ip': '172.24.249.182',
        'management.server.ip6': 'fd00:172:24:249::182',
    }) is True
    assert management_network_ipv6.management_server_requires_ipv6_stack({
        'management.server.ip': '172.24.249.182',
        'management.server.vip6': 'fd00:172:24:249::180',
    }) is True


def test_prepare_ipv6_system_parameters_sets_required_sysctls():
    commands = []

    management_network_ipv6.prepare_ipv6_system_parameters(
        commands.append,
        proc_exists_func=lambda path: path == management_network_ipv6.IPV6_SYSCTL_PROC_DIR,
        read_file_func=lambda path: 'BOOT_IMAGE=/vmlinuz root=/dev/mapper/root ro',
        read_sysctl_func=lambda name: '1',
    )

    assert commands == [
        ['sysctl', '-w', 'net.ipv6.conf.all.disable_ipv6=0'],
        ['sysctl', '-w', 'net.ipv6.conf.default.disable_ipv6=0'],
        ['sysctl', '-w', 'net.ipv6.bindv6only=0'],
    ]


def test_prepare_ipv6_system_parameters_fails_when_kernel_disables_ipv6():
    try:
        management_network_ipv6.prepare_ipv6_system_parameters(
            lambda command: None,
            proc_exists_func=lambda path: True,
            read_file_func=lambda path: 'BOOT_IMAGE=/vmlinuz ipv6.disable=1',
        )
    except management_network_ipv6.IPv6SystemParameterError as e:
        assert 'ipv6.disable=1' in str(e)
    else:
        raise AssertionError('expected IPv6SystemParameterError')


def test_prepare_ipv6_system_parameters_rolls_back_applied_sysctls_on_failure():
    commands = []
    logs = []

    def shell_func(command):
        commands.append(command)
        if command == ['sysctl', '-w', 'net.ipv6.conf.default.disable_ipv6=0']:
            raise RuntimeError('sysctl failed')

    try:
        management_network_ipv6.prepare_ipv6_system_parameters(
            shell_func,
            proc_exists_func=lambda path: path == management_network_ipv6.IPV6_SYSCTL_PROC_DIR,
            read_file_func=lambda path: 'BOOT_IMAGE=/vmlinuz root=/dev/mapper/root ro',
            read_sysctl_func=lambda name: {
                'net.ipv6.conf.all.disable_ipv6': '1',
                'net.ipv6.conf.default.disable_ipv6': '1',
                'net.ipv6.bindv6only': '1',
            }[name],
            logger_func=logs.append,
        )
    except management_network_ipv6.IPv6SystemParameterError as e:
        assert 'net.ipv6.conf.default.disable_ipv6' in str(e)
    else:
        raise AssertionError('expected IPv6SystemParameterError')

    assert commands == [
        ['sysctl', '-w', 'net.ipv6.conf.all.disable_ipv6=0'],
        ['sysctl', '-w', 'net.ipv6.conf.default.disable_ipv6=0'],
        ['sysctl', '-w', 'net.ipv6.conf.all.disable_ipv6=1'],
    ]
    assert 'rollback sysctl net.ipv6.conf.all.disable_ipv6 to 1' in logs
