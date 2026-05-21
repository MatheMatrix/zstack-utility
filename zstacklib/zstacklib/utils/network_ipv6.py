# -*- coding: utf-8 -*-
import os
import socket


AGENT_BIND_IP_ENV = 'AGENT_BIND_IP'
POOLSIZE_ENV = 'POOLSIZE'
DUAL_STACK_BIND_ADDRESS = '::'
IPV4_BIND_ADDRESS = ''
IPV6_SEPARATOR = ':'
IPV6_BRACKET_PREFIX = '['
IPV6_BRACKET_SUFFIX = ']'
URL_IPV6_HOST_FORMAT = '[%s]'
LOOPBACK_IPV4 = '127.0.0.1'
LOOPBACK_IPV6 = '::1'
LINK_LOCAL_IPV6_PREFIX = 'fe80:'
ZSTACK_RESERVED_INTERFACE_SUFFIX = 'zs'
IPV6_V6ONLY_DISABLED = 0
DEFAULT_AGENT_THREAD_POOL = '10'
CHERRYPY_SOCKET_HOST_KEY = 'server.socket_host'
CHERRYPY_SOCKET_PORT_KEY = 'server.socket_port'
CHERRYPY_THREAD_POOL_KEY = 'server.thread_pool'


def get_agent_bind_ip(env=None):
    env = os.environ if env is None else env
    return env.get(AGENT_BIND_IP_ENV, DUAL_STACK_BIND_ADDRESS)


def format_url_host(host):
    if host is None:
        return host
    if host.startswith(IPV6_BRACKET_PREFIX) and host.endswith(IPV6_BRACKET_SUFFIX):
        return host
    return URL_IPV6_HOST_FORMAT % host if IPV6_SEPARATOR in host else host


def get_socket_family(host):
    return socket.AF_INET6 if host and IPV6_SEPARATOR in host else socket.AF_INET


def create_tcp_socket_for_host(host):
    return socket.socket(get_socket_family(host), socket.SOCK_STREAM)


def configure_dual_stack_socket(sock):
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, IPV6_V6ONLY_DISABLED)


def bind_dual_stack_probe_socket(sock, port):
    configure_dual_stack_socket(sock)
    sock.bind((DUAL_STACK_BIND_ADDRESS, int(port)))


def bind_ipv4_probe_socket(sock, port):
    sock.bind((IPV4_BIND_ADDRESS, int(port)))


def build_cherrypy_socket_config(port, env=None):
    env = os.environ if env is None else env
    return {
        CHERRYPY_SOCKET_HOST_KEY: get_agent_bind_ip(env),
        CHERRYPY_SOCKET_PORT_KEY: port,
        CHERRYPY_THREAD_POOL_KEY: int(env.get(POOLSIZE_ENV, DEFAULT_AGENT_THREAD_POOL)),
    }


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
