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


def test_build_java_ip_stack_opts_keeps_ipv4_defaults_for_ipv4_mn():
    opts = [
        '-Djava.net.preferIPv4Stack=true',
        '-Xmx12288M',
    ]

    assert management_network_ipv6.build_java_ip_stack_opts('172.24.246.247', opts) == opts
