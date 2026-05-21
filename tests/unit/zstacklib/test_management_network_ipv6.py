# -*- coding: utf-8 -*-
import socket

from zstacklib.utils import network_ipv6


class FakeAddress(object):
    def __init__(self, address, ifname):
        self.address = address
        self.ifname = ifname


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
    assert network_ipv6.format_url_host('192.168.10.10') == '192.168.10.10'
    assert network_ipv6.format_url_host('2001:db8::10') == '[2001:db8::10]'
    assert network_ipv6.format_url_host('[2001:db8::10]') == '[2001:db8::10]'
    assert network_ipv6.format_url_host(None) is None


def test_get_agent_bind_ip_defaults_to_dual_stack_and_allows_override():
    assert network_ipv6.get_agent_bind_ip({}) == '::'
    assert network_ipv6.get_agent_bind_ip({'AGENT_BIND_IP': '0.0.0.0'}) == '0.0.0.0'
    assert network_ipv6.get_agent_bind_ip({'AGENT_BIND_IP': '2001:db8::10'}) == '2001:db8::10'


def test_get_socket_family_uses_ipv6_for_literal_ipv6_only():
    assert network_ipv6.get_socket_family('2001:db8::10') == socket.AF_INET6
    assert network_ipv6.get_socket_family('192.168.10.10') == socket.AF_INET
    assert network_ipv6.get_socket_family('zstack-mn.example.com') == socket.AF_INET


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
