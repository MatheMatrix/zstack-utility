# -*- coding: utf-8 -*-
import json
import socket
import sys
import types

import pytest


def _install_module_stub(name):
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


simplejson = _install_module_stub('simplejson')
simplejson.dumps = json.dumps
simplejson.loads = json.loads

configobj = _install_module_stub('configobj')
configobj.ConfigObj = dict

termcolor = _install_module_stub('termcolor')
termcolor.colored = lambda value, *args, **kwargs: value

yaml = _install_module_stub('yaml')
yaml.load = lambda *args, **kwargs: {}
yaml.dump = lambda *args, **kwargs: ''

for module_name in ('OpenSSL', 'jinja2'):
    _install_module_stub(module_name)

for module_name in ('Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES', 'Crypto.Util', 'Crypto.Util.py3compat'):
    _install_module_stub(module_name)
sys.modules['Crypto.Cipher'].AES = sys.modules['Crypto.Cipher.AES']
sys.modules['Crypto.Util.py3compat'].__all__ = []

for module_name in (
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.serialization',
        'cryptography.hazmat.primitives.serialization.pkcs12'):
    _install_module_stub(module_name)
sys.modules['cryptography.hazmat.primitives'].serialization = sys.modules[
    'cryptography.hazmat.primitives.serialization']
sys.modules['cryptography.hazmat.primitives.serialization'].pkcs12 = sys.modules[
    'cryptography.hazmat.primitives.serialization.pkcs12']

from zstackctl import ctl


def test_split_host_port_endpoint_supports_bracketed_ipv6():
    assert ctl.split_host_port_endpoint('[2001:db8::10]:3307', '3306') == ('2001:db8::10', '3307')
    assert ctl.split_host_port_endpoint('[2001:db8::10]', '3306') == ('2001:db8::10', '3306')
    assert ctl.split_host_port_endpoint('192.168.10.10:3307', '3306') == ('192.168.10.10', '3307')
    assert ctl.split_host_port_endpoint('2001:db8::10', '22') == ('2001:db8::10', '22')


def test_check_host_info_format_accepts_ipv6_with_port():
    assert ctl.check_host_info_format('root:password@[2001:db8::10]:2222') == (
        'root', 'password', '2001:db8::10', '2222')
    assert ctl.check_host_info_format('root:password@2001:db8::10') == (
        'root', 'password', '2001:db8::10', ctl.DEFAULT_SSH_PORT)


def test_check_ip_port_uses_ipv6_socket_for_ipv6(monkeypatch):
    calls = []

    class FakeSocket(object):
        def __init__(self, family, socket_type):
            calls.append((family, socket_type))

        def connect_ex(self, address):
            calls.append(address)
            return 0

        def close(self):
            calls.append('closed')

    monkeypatch.setattr(ctl.socket, 'socket', FakeSocket)

    assert ctl.check_ip_port('[2001:db8::10]', 3306)
    assert calls == [
        (socket.AF_INET6, socket.SOCK_STREAM),
        ('2001:db8::10', 3306),
        'closed',
    ]


def test_validate_ip_versions_rejects_invalid_ip(monkeypatch):
    errors = []
    monkeypatch.setattr(ctl, 'error', lambda message: errors.append(message))

    zsha = ctl.Zsha2Utils.__new__(ctl.Zsha2Utils)
    zsha.config = {
        'nodeip': '2001:db8::10',
        'peerip': 'invalid-peer',
        'dbvip': '2001:db8::20',
    }

    zsha.validate_ip_versions()

    assert errors == [
        'zsha2 nodeip, peerip and dbvip must be valid IP addresses: peerip=invalid-peer'
    ]


def test_management_server_ip_stack_opts_enable_dual_stack_for_ip6():
    opts = ctl.build_management_server_ip_stack_opts({
        'management.server.ip': '172.24.196.95',
        'management.server.ip6': 'fd00:172:24:249::95',
    })

    assert '-Djava.net.preferIPv4Stack=false' in opts
    assert '-Djava.net.preferIPv6Addresses=true' in opts


def test_management_server_ip_stack_opts_enable_dual_stack_for_ipv4_primary():
    opts = ctl.build_management_server_ip_stack_opts({
        'management.server.ip': '172.24.196.95',
    })

    assert opts == ['-Djava.net.preferIPv4Stack=false']


def test_ui_ipv6_listen_helpers_update_nginx_conf(tmp_path):
    conf = tmp_path / 'extend.server.nginx.conf'
    conf.write_text('        listen 5000;\n        add_header zs-version 5.5.16;\n')

    assert ctl.ui_should_listen_ipv6('::')
    assert ctl.ensure_ui_nginx_ipv6_listen_conf(str(conf), '5000')
    assert 'listen [::]:5000;' in conf.read_text()

    assert not ctl.ensure_ui_nginx_ipv6_listen_conf(str(conf), '5000')


def test_ui_ipv6_listen_helpers_accept_literal_ipv6(tmp_path):
    conf = tmp_path / 'extend.server.nginx.conf'
    conf.write_text('        listen 5000;\n        add_header zs-version 5.5.16;\n')

    assert ctl.ui_should_listen_ipv6('2001:db8::10')
    assert ctl.ui_should_listen_ipv6('[2001:db8::10]')
    assert ctl.ensure_ui_nginx_ipv6_listen_conf(str(conf), '5000', False, False, '2001:db8::10')
    assert 'listen [2001:db8::10]:5000;' in conf.read_text()

    assert not ctl.ensure_ui_nginx_ipv6_listen_conf(str(conf), '5000', False, False, '2001:db8::10')


def test_ui_ipv6_listen_helpers_replace_obsolete_ipv6_listen(tmp_path):
    conf = tmp_path / 'extend.server.nginx.conf'
    conf.write_text(
        '        listen 5000;\n'
        '        listen [::]:5000;\n'
        '        add_header zs-version 5.5.16;\n'
    )

    assert ctl.ensure_ui_nginx_ipv6_listen_conf(str(conf), '5000', False, False, '2001:db8::10')

    content = conf.read_text()
    assert 'listen [2001:db8::10]:5000;' in content
    assert 'listen [::]:5000;' not in content


def test_ui_ipv6_ssl_listen_line_includes_http2():
    assert ctl.build_ui_nginx_ipv6_listen_line('5443', True, 'true') == \
        '        listen [::]:5443 ssl http2;'


def test_ui_ipv6_ssl_listen_line_accepts_literal_ipv6():
    assert ctl.build_ui_nginx_ipv6_listen_line('5443', True, 'true', '2001:db8::10') == \
        '        listen [2001:db8::10]:5443 ssl http2;'


def test_change_ip_firewall_commands_keep_ipv4_iptables():
    assert ctl.build_change_ip_ipv4_firewall_delete_commands('172.24.246.1', {'3306'}) == [
        'iptables -D INPUT -p tcp --dport 3306 -d 172.24.246.1 -j ACCEPT',
        'iptables -D INPUT -p tcp --dport 3306 -d 127.0.0.1 -j ACCEPT',
    ]
    assert ctl.build_change_ip_ipv4_firewall_accept_commands('172.24.246.247', {'3306'}) == [
        'iptables -A INPUT -p tcp --dport 3306 -j REJECT',
        'iptables -I INPUT -p tcp --dport 3306 -d 172.24.246.247 -j ACCEPT',
        'iptables -I INPUT -p tcp --dport 3306 -d 127.0.0.1 -j ACCEPT',
    ]


def test_change_ip_firewall_commands_use_ip6tables_for_ipv6():
    assert ctl.build_change_ip_ipv6_firewall_delete_commands('fd00:172:24:246::1', {'3306'}) == [
        'ip6tables -D INPUT -p tcp --dport 3306 -d fd00:172:24:246::1 -j ACCEPT',
        'ip6tables -D INPUT -p tcp --dport 3306 -d ::1 -j ACCEPT',
    ]
    assert ctl.build_change_ip_ipv6_firewall_accept_commands('fd00:172:24:246::247', {'3306'}) == [
        'ip6tables -A INPUT -p tcp --dport 3306 -j REJECT',
        'ip6tables -I INPUT -p tcp --dport 3306 -d fd00:172:24:246::247 -j ACCEPT',
        'ip6tables -I INPUT -p tcp --dport 3306 -d ::1 -j ACCEPT',
    ]


def test_change_ip_ipv4_path_cleans_old_ipv6_rules(monkeypatch):
    calls = []
    monkeypatch.setattr(ctl, 'shell_return', lambda command: calls.append(command))
    monkeypatch.setattr(ctl, 'shell', lambda command: calls.append(command))

    ctl.update_change_ip_ipv4_firewall_rules(
        '172.24.246.247', '172.24.246.247', 'fd00:172:24:246::247', {'3306'})

    assert calls == [
        'ip6tables -D INPUT -p tcp --dport 3306 -d fd00:172:24:246::247 -j ACCEPT',
        'ip6tables -D INPUT -p tcp --dport 3306 -d ::1 -j ACCEPT',
        'iptables -A INPUT -p tcp --dport 3306 -j REJECT',
        'iptables -I INPUT -p tcp --dport 3306 -d 172.24.246.247 -j ACCEPT',
        'iptables -I INPUT -p tcp --dport 3306 -d 127.0.0.1 -j ACCEPT',
    ]
