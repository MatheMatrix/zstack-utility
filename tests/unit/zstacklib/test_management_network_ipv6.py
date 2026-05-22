# -*- coding: utf-8 -*-
import socket

from zstacklib.utils import network_ipv6

TEST_IPV4_ADDRESS = '192.168.10.10'
TEST_IPV6_ADDRESS = '2001:db8::10'
TEST_HOSTNAME = 'zstack-mn.example.com'
TEST_PORT = 7070
TEST_POOL_SIZE = '32'


class FakeAddress(object):
    def __init__(self, address, ifname):
        self.address = address
        self.ifname = ifname


class FakeSocket(object):
    def __init__(self):
        self.options = []
        self.bind_address = None

    def setsockopt(self, level, option, value):
        self.options.append((level, option, value))

    def bind(self, address):
        self.bind_address = address


class FakeIpRoute(object):
    def __init__(self):
        self.versions = []

    def query_addresses(self, ip_version=None):
        self.versions.append(ip_version)
        return {
            4: [
                FakeAddress('127.0.0.1', 'lo'),
                FakeAddress('192.168.10.10', 'eth0'),
                FakeAddress('192.168.20.10', 'eth1zs'),
            ],
            6: [
                FakeAddress('::1', 'lo'),
                FakeAddress('fe80::1', 'eth0'),
                FakeAddress('2001:db8::10', 'eth0'),
                FakeAddress('2001:db8::20', 'eth2zs'),
            ],
        }[ip_version]


def test_format_url_host_wraps_ipv6_only_once():
    assert network_ipv6.format_url_host(TEST_IPV4_ADDRESS) == TEST_IPV4_ADDRESS
    assert network_ipv6.format_url_host(TEST_IPV6_ADDRESS) == '[2001:db8::10]'
    assert network_ipv6.format_url_host('[2001:db8::10]') == '[2001:db8::10]'
    assert network_ipv6.format_url_host(None) is None


def test_extract_url_host_supports_ipv4_ipv6_and_hostnames():
    assert network_ipv6.extract_url_host('http://192.168.10.10:8080/callback') == TEST_IPV4_ADDRESS
    assert network_ipv6.extract_url_host('http://[2001:db8::10]:8080/callback') == TEST_IPV6_ADDRESS
    assert network_ipv6.extract_url_host('http://zstack-mn.example.com:8080/callback') == TEST_HOSTNAME


def test_get_agent_bind_ip_defaults_to_dual_stack_and_allows_override():
    assert network_ipv6.get_agent_bind_ip({}) == network_ipv6.DUAL_STACK_BIND_ADDRESS
    assert network_ipv6.get_agent_bind_ip({network_ipv6.AGENT_BIND_IP_ENV: '0.0.0.0'}) == '0.0.0.0'
    assert network_ipv6.get_agent_bind_ip({network_ipv6.AGENT_BIND_IP_ENV: TEST_IPV6_ADDRESS}) == TEST_IPV6_ADDRESS


def test_get_socket_family_uses_ipv6_for_literal_ipv6_only():
    assert network_ipv6.get_socket_family(TEST_IPV6_ADDRESS) == socket.AF_INET6
    assert network_ipv6.get_socket_family(TEST_IPV4_ADDRESS) == socket.AF_INET
    assert network_ipv6.get_socket_family(TEST_HOSTNAME) == socket.AF_INET


def test_create_tcp_socket_for_host_uses_matching_address_family():
    created = []
    original_socket = network_ipv6.socket.socket

    def fake_socket(family, sock_type):
        created.append((family, sock_type))
        return FakeSocket()

    network_ipv6.socket.socket = fake_socket
    try:
        network_ipv6.create_tcp_socket_for_host(TEST_IPV6_ADDRESS)
        network_ipv6.create_tcp_socket_for_host(TEST_HOSTNAME)
    finally:
        network_ipv6.socket.socket = original_socket

    assert created == [
        (socket.AF_INET6, socket.SOCK_STREAM),
        (socket.AF_INET, socket.SOCK_STREAM),
    ]


def test_bind_dual_stack_probe_socket_disables_ipv6_only_and_binds_any_address():
    fake_socket = FakeSocket()

    network_ipv6.bind_dual_stack_probe_socket(fake_socket, TEST_PORT)

    assert fake_socket.options == [
        (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, network_ipv6.IPV6_V6ONLY_DISABLED)
    ]
    assert fake_socket.bind_address == (network_ipv6.DUAL_STACK_BIND_ADDRESS, TEST_PORT)


def test_bind_ipv4_probe_socket_uses_ipv4_any_address():
    fake_socket = FakeSocket()

    network_ipv6.bind_ipv4_probe_socket(fake_socket, TEST_PORT)

    assert fake_socket.bind_address == (network_ipv6.IPV4_BIND_ADDRESS, TEST_PORT)


def test_build_cherrypy_socket_config_defaults_to_dual_stack_and_reads_env():
    assert network_ipv6.build_cherrypy_socket_config(TEST_PORT, {}) == {
        network_ipv6.CHERRYPY_SOCKET_HOST_KEY: network_ipv6.DUAL_STACK_BIND_ADDRESS,
        network_ipv6.CHERRYPY_SOCKET_PORT_KEY: TEST_PORT,
        network_ipv6.CHERRYPY_THREAD_POOL_KEY: int(network_ipv6.DEFAULT_AGENT_THREAD_POOL),
    }
    assert network_ipv6.build_cherrypy_socket_config(
        TEST_PORT,
        {
            network_ipv6.AGENT_BIND_IP_ENV: TEST_IPV6_ADDRESS,
            network_ipv6.POOLSIZE_ENV: TEST_POOL_SIZE,
        },
    ) == {
        network_ipv6.CHERRYPY_SOCKET_HOST_KEY: TEST_IPV6_ADDRESS,
        network_ipv6.CHERRYPY_SOCKET_PORT_KEY: TEST_PORT,
        network_ipv6.CHERRYPY_THREAD_POOL_KEY: int(TEST_POOL_SIZE),
    }


def test_extract_route_source_address_accepts_ipv4_and_ipv6_src_tokens():
    assert network_ipv6.extract_route_source_address(
        '10.0.0.1 via 10.0.0.254 dev eth0 src 10.0.0.10 uid 0'
    ) == '10.0.0.10'
    assert network_ipv6.extract_route_source_address(
        '2001:db8::1 from :: dev eth0 src 2001:db8::10 metric 100'
    ) == TEST_IPV6_ADDRESS
    assert network_ipv6.extract_route_source_address(
        '2001:db8::1 from :: dev eth0 src not-an-ip metric 100'
    ) is None
    assert network_ipv6.extract_route_source_address('default via 10.0.0.1 dev eth0') is None


def test_reportable_agent_address_filter_rejects_loopback_link_local_and_zs():
    assert not network_ipv6.is_reportable_agent_address('127.0.0.1', 'lo')
    assert not network_ipv6.is_reportable_agent_address('::1', 'lo')
    assert not network_ipv6.is_reportable_agent_address('fe80::1', 'eth0')
    assert not network_ipv6.is_reportable_agent_address('192.168.10.10', 'eth0zs')
    assert network_ipv6.is_reportable_agent_address('192.168.10.10', 'eth0')
    assert network_ipv6.is_reportable_agent_address('2001:db8::10', 'eth0')


def test_collect_reportable_agent_addresses_queries_ipv4_and_ipv6():
    fake_iproute = FakeIpRoute()

    addresses = network_ipv6.collect_reportable_agent_addresses(fake_iproute)

    assert fake_iproute.versions == [4, 6]
    assert addresses == ['192.168.10.10', '2001:db8::10']
