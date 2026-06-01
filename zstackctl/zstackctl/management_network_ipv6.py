# -*- coding: utf-8 -*-
import re
import socket
import os


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
JAVA_PREFER_IPV4_STACK_PREFIX = '-Djava.net.preferIPv4Stack='
JAVA_PREFER_IPV6_ADDRESSES_PREFIX = '-Djava.net.preferIPv6Addresses='
MIN_IPV6_PREFIX_LENGTH = 0
MAX_IPV6_PREFIX_LENGTH = 128
IP_COMMAND = 'ip'
IPV6_ADDR_ADD_ARGUMENTS = ('-6', 'addr', 'add')
IPV6_DEVICE_ARGUMENT = 'dev'
INTERFACE_NAME_PATTERN = r'^[0-9A-Za-z_.:-]+$'
DEFAULT_ROUTE_INTERFACE_PATTERN = r'\bdev\s+([0-9A-Za-z_.:-]+)'
IPV6_SYSCTL_PROC_DIR = '/proc/sys/net/ipv6'
PROC_CMDLINE_PATH = '/proc/cmdline'
KERNEL_IPV6_DISABLED_ARGUMENT = 'ipv6.disable=1'
MANAGEMENT_IPV6_PROPERTY_KEYS = (
    'management.server.ip6',
    'management.server.vip6',
)
MANAGEMENT_IP_PROPERTY_KEY = 'management.server.ip'
MN_IPV6_SYSCTL_SETTINGS = (
    ('net.ipv6.conf.all.disable_ipv6', '0'),
    ('net.ipv6.conf.default.disable_ipv6', '0'),
    ('net.ipv6.bindv6only', '0'),
)


class IPv6SystemParameterError(RuntimeError):
    pass


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


def build_java_ip_stack_opts(management_ip, catalina_opts):
    opts = [
        opt for opt in catalina_opts
        if not opt.startswith(JAVA_PREFER_IPV4_STACK_PREFIX)
        and not opt.startswith(JAVA_PREFER_IPV6_ADDRESSES_PREFIX)
    ]
    opts.append(JAVA_PREFER_IPV4_STACK_PREFIX + 'false')
    if get_ip_version(management_ip) == IPV6_VERSION:
        opts.append(JAVA_PREFER_IPV6_ADDRESSES_PREFIX + 'true')
    return opts


def validate_ipv6(value):
    return get_ip_version(value) == IPV6_VERSION


def normalize_ipv6_prefix(prefix):
    try:
        prefix_length = int(prefix)
    except (TypeError, ValueError):
        return None

    if MIN_IPV6_PREFIX_LENGTH <= prefix_length <= MAX_IPV6_PREFIX_LENGTH:
        return prefix_length
    return None


def validate_interface_name(nic):
    return isinstance(nic, STRING_TYPES) and re.match(INTERFACE_NAME_PATTERN, nic) is not None


def strip_interface_suffix(nic):
    return nic.split('@', 1)[0] if nic else nic


def find_interface_by_ip(ip, addr_output):
    if not validate_ip(ip) or not addr_output:
        return None

    ip = ip.strip('[]')
    for line in addr_output.splitlines():
        match = re.match(r'^\d+:\s+([^:\s]+).*?\s+inet6?\s+%s(?:/|\s)' % re.escape(ip), line.strip())
        if match:
            return strip_interface_suffix(match.group(1))

    return None


def find_default_route_interface(route_output):
    if not route_output:
        return None

    for line in route_output.splitlines():
        if not line.startswith('default '):
            continue
        match = re.search(DEFAULT_ROUTE_INTERFACE_PATTERN, line)
        if match:
            return strip_interface_suffix(match.group(1))

    return None


def select_add_ip6_interface(explicit_nic, management_ip, route_output, addr_output):
    if explicit_nic:
        return explicit_nic if validate_interface_name(explicit_nic) else None

    if management_ip:
        nic = find_interface_by_ip(management_ip, addr_output)
        if nic:
            return nic

    nic = find_default_route_interface(route_output)
    return nic if validate_interface_name(nic) else None


def build_add_ip6_command(ip, prefix, nic):
    prefix_length = normalize_ipv6_prefix(prefix)
    if not validate_ipv6(ip) or prefix_length is None or not validate_interface_name(nic):
        return None

    return [IP_COMMAND] + list(IPV6_ADDR_ADD_ARGUMENTS) + [
        '%s/%s' % (ip.strip('[]'), prefix_length),
        IPV6_DEVICE_ARGUMENT,
        nic,
    ]


def management_server_requires_ipv6_stack(properties):
    for key in MANAGEMENT_IPV6_PROPERTY_KEYS:
        if properties.get(key):
            return True

    return get_ip_version(properties.get(MANAGEMENT_IP_PROPERTY_KEY)) == IPV6_VERSION


def kernel_cmdline_disables_ipv6(cmdline):
    return KERNEL_IPV6_DISABLED_ARGUMENT in (cmdline or '').split()


def build_sysctl_set_command(name, value):
    return ['sysctl', '-w', '%s=%s' % (name, value)]


def build_ipv6_sysctl_set_commands(settings=MN_IPV6_SYSCTL_SETTINGS):
    return [build_sysctl_set_command(name, value) for name, value in settings]


def prepare_ipv6_system_parameters(shell_func, proc_exists_func=os.path.exists,
                                   read_file_func=None, settings=MN_IPV6_SYSCTL_SETTINGS):
    if read_file_func is None:
        def read_file_func(path):
            with open(path, 'r') as fd:
                return fd.read()

    if not proc_exists_func(IPV6_SYSCTL_PROC_DIR):
        raise IPv6SystemParameterError(
            'IPv6 sysctl path %s is missing; please make sure IPv6 is enabled in the kernel'
            % IPV6_SYSCTL_PROC_DIR
        )

    try:
        cmdline = read_file_func(PROC_CMDLINE_PATH)
    except (IOError, OSError):
        cmdline = ''

    if kernel_cmdline_disables_ipv6(cmdline):
        raise IPv6SystemParameterError(
            'kernel argument %s disables IPv6; please remove it and reboot before starting IPv6 management node'
            % KERNEL_IPV6_DISABLED_ARGUMENT
        )

    for command in build_ipv6_sysctl_set_commands(settings):
        shell_func(command)
