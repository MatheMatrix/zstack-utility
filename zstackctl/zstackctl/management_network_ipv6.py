# -*- coding: utf-8 -*-
import re
import socket


try:
    STRING_TYPES = (str, unicode)
except NameError:
    STRING_TYPES = (str,)

IPV6_SEPARATOR = ':'
IPV6_BRACKET_PREFIX = '['
IPV6_BRACKET_SUFFIX = ']'
HOSTNAME_SEPARATOR = '-'
IPV4_SEPARATOR = '.'
IPV4_VERSION = 4
IPV6_VERSION = 6
JDBC_IPV6_HOST_FORMAT = '[%s]'
IPV6_DB_HOST_PATTERN = r'\[([0-9a-fA-F:]+)\]'
IPV4_OR_LOCALHOST_DB_HOST_PATTERN = r'(?<![0-9A-Za-z_.-])(?:[0-9]{1,3}(?:\.[0-9]{1,3}){3}|localhost)(?![0-9A-Za-z_.-])'


def validate_ip(value):
    for address_family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(address_family, value)
            return True
        except socket.error:
            pass

    return False


def ip_to_hostname(ip):
    if ip is None:
        return ''
    if isinstance(ip, bytes) and bytes not in STRING_TYPES:
        ip = ip.decode('utf-8')
    if not isinstance(ip, STRING_TYPES):
        raise TypeError('ip must be a string')
    return ip.strip('[]').replace(IPV6_SEPARATOR, HOSTNAME_SEPARATOR).replace(IPV4_SEPARATOR, HOSTNAME_SEPARATOR)


def format_host_for_url_or_jdbc(ip):
    if ip is None:
        return ip
    return JDBC_IPV6_HOST_FORMAT % ip if IPV6_SEPARATOR in ip and not ip.startswith(IPV6_BRACKET_PREFIX) else ip


def get_ip_version(ip):
    if not ip:
        return None
    ip = ip.strip('[]')
    if not validate_ip(ip):
        return None
    return IPV6_VERSION if IPV6_SEPARATOR in ip else IPV4_VERSION


def has_mixed_ip_versions(ips):
    versions = set()
    for ip in ips:
        version = get_ip_version(ip)
        if version is not None:
            versions.add(version)

    return len(versions) > 1


def extract_db_url_host(db_url):
    ipv6_hosts = re.findall(IPV6_DB_HOST_PATTERN, db_url)
    if ipv6_hosts:
        return ipv6_hosts[0]

    ipv4_hosts = re.findall(IPV4_OR_LOCALHOST_DB_HOST_PATTERN, db_url)
    return ipv4_hosts[0] if ipv4_hosts else None


def replace_db_url_host(db_url, new_host):
    old_host = extract_db_url_host(db_url)
    if old_host is None:
        return db_url

    if IPV6_SEPARATOR in old_host:
        return db_url.replace(JDBC_IPV6_HOST_FORMAT % old_host, format_host_for_url_or_jdbc(new_host), 1)

    return db_url.replace(old_host, format_host_for_url_or_jdbc(new_host), 1)


def ip_addr_output_has_ip(ip, addr_output):
    if ip is None or addr_output is None:
        return False
    if isinstance(ip, bytes) and bytes not in STRING_TYPES:
        ip = ip.decode('utf-8')
    if not isinstance(ip, STRING_TYPES):
        return False

    ip = ip.strip('[]')
    if not validate_ip(ip):
        return False

    return re.search(r'\binet6?\s+%s(?:/|\s)' % re.escape(ip), addr_output) is not None
