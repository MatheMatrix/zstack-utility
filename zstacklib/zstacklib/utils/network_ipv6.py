# -*- coding: utf-8 -*-
import os
import socket


AGENT_BIND_IP_ENV = 'AGENT_BIND_IP'
DUAL_STACK_BIND_ADDRESS = '::'
IPV6_SEPARATOR = ':'
IPV6_BRACKET_PREFIX = '['
IPV6_BRACKET_SUFFIX = ']'
URL_IPV6_HOST_FORMAT = '[%s]'
LOOPBACK_IPV4 = '127.0.0.1'
LOOPBACK_IPV6 = '::1'
LINK_LOCAL_IPV6_PREFIX = 'fe80:'
ZSTACK_RESERVED_INTERFACE_SUFFIX = 'zs'
IPV6_V6ONLY_DISABLED = 0


def get_agent_bind_ip(env=None):
    env = env or os.environ
    return env.get(AGENT_BIND_IP_ENV, DUAL_STACK_BIND_ADDRESS)


def format_url_host(host):
    if host is None:
        return host
    if host.startswith(IPV6_BRACKET_PREFIX) and host.endswith(IPV6_BRACKET_SUFFIX):
        return host
    return URL_IPV6_HOST_FORMAT % host if IPV6_SEPARATOR in host else host


def get_socket_family(host):
    return socket.AF_INET6 if host and IPV6_SEPARATOR in host else socket.AF_INET


def configure_dual_stack_socket(sock):
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, IPV6_V6ONLY_DISABLED)


def is_reportable_agent_address(address, ifname):
    if ifname and ifname.endswith(ZSTACK_RESERVED_INTERFACE_SUFFIX):
        return False
    if address in (LOOPBACK_IPV4, LOOPBACK_IPV6):
        return False
    if address and address.startswith(LINK_LOCAL_IPV6_PREFIX):
        return False
    return True


def collect_reportable_agent_addresses(iproute_module):
    addresses = []
    for ip_version in (4, 6):
        for chunk in iproute_module.query_addresses(ip_version=ip_version):
            if is_reportable_agent_address(chunk.address, chunk.ifname):
                addresses.append(chunk.address)
    return addresses
