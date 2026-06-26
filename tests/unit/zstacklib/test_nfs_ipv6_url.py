from __future__ import annotations

import socket

import pytest

from zstacklib.storage.nfs import operations
from zstacklib.storage.nfs.exceptions import InvalidNfsUrlError
from tests.unit.zstacklib.real_linux import load_real_linux

IPV4_NFS_URL = '192.168.10.10:/export/nfs'
HOSTNAME_NFS_URL = 'nfs.example.com:/export/nfs'
IPV6_NFS_URL = '[fd00:172:24:249::182]:/export/zstack-nfs-ps'
RAW_IPV6_NFS_URL = 'fd00:172:24:249::182:/export/zstack-nfs-ps'

linux = load_real_linux()


def test_parse_nfs_url_supports_ipv4_hostname_and_bracketed_ipv6():
    assert operations.parse_nfs_url(IPV4_NFS_URL) == ('192.168.10.10', '/export/nfs')
    assert operations.parse_nfs_url(HOSTNAME_NFS_URL) == ('nfs.example.com', '/export/nfs')
    assert operations.parse_nfs_url(IPV6_NFS_URL) == (
        'fd00:172:24:249::182',
        '/export/zstack-nfs-ps',
    )


def test_parse_nfs_url_rejects_raw_ipv6():
    with pytest.raises(InvalidNfsUrlError):
        operations.parse_nfs_url(RAW_IPV6_NFS_URL)


def test_validate_nfs_url_uses_ipv6_capable_resolver(monkeypatch):
    resolved_hosts = []

    def fake_getaddrinfo(host, port):
        resolved_hosts.append((host, port))
        return [(socket.AF_INET6, socket.SOCK_STREAM, 0, '', (host, 0))]

    monkeypatch.setattr(operations.socket, 'getaddrinfo', fake_getaddrinfo)

    assert operations.validate_nfs_url(IPV6_NFS_URL)
    assert resolved_hosts == [('fd00:172:24:249::182', None)]


def test_legacy_linux_nfs_url_parser_supports_bracketed_ipv6(monkeypatch):
    resolved_hosts = []

    def fake_getaddrinfo(host, port):
        resolved_hosts.append((host, port))
        return [(socket.AF_INET6, socket.SOCK_STREAM, 0, '', (host, 0))]

    monkeypatch.setattr(linux.socket, 'getaddrinfo', fake_getaddrinfo)

    assert linux.parse_nfs_url(IPV6_NFS_URL) == (
        'fd00:172:24:249::182',
        '/export/zstack-nfs-ps',
    )
    assert linux.is_valid_nfs_url(IPV6_NFS_URL)
    assert resolved_hosts == [('fd00:172:24:249::182', None)]


def test_legacy_linux_is_mounted_uses_fixed_string_match_for_ipv6_url(monkeypatch):
    commands = []

    def fake_run(command):
        commands.append(command)
        return 0

    monkeypatch.setattr(linux.shell, 'run', fake_run)

    assert linux.is_mounted('/mnt/nfs', IPV6_NFS_URL)
    assert commands == [
        "mount | grep -F '[fd00:172:24:249::182]:/export/zstack-nfs-ps on ' | grep -F '/mnt/nfs ' "
    ]


def test_nfs_operations_is_mounted_uses_fixed_string_match_for_ipv6_url(monkeypatch):
    commands = []

    def fake_run(command):
        commands.append(command)
        return 0

    monkeypatch.setattr(operations.shell, 'run', fake_run)

    assert operations.is_mounted('/mnt/nfs', IPV6_NFS_URL)
    assert commands == [
        "mount | grep -F '[fd00:172:24:249::182]:/export/zstack-nfs-ps on ' | grep -F '/mnt/nfs ' "
    ]


def test_legacy_linux_get_host_by_name_returns_ipv6_literal_without_dns(monkeypatch):
    def fake_getaddrinfo(host, port):
        raise AssertionError('literal IP must not be resolved by getaddrinfo')

    monkeypatch.setattr(linux.socket, 'getaddrinfo', fake_getaddrinfo)

    assert linux.get_host_by_name('fd00:172:24:249::182') == 'fd00:172:24:249::182'


def test_legacy_linux_get_host_by_name_resolves_hostname(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 0, '', ('fd00:172:24:249::182', 0))]

    monkeypatch.setattr(linux.socket, 'getaddrinfo', fake_getaddrinfo)

    assert linux.get_host_by_name('host.example.com') == 'fd00:172:24:249::182'
