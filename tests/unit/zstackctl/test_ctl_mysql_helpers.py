import importlib
import json
import sys
import types

import pytest


def _install_ctl_import_stubs():
    if 'simplejson' not in sys.modules:
        simplejson = types.ModuleType('simplejson')
        simplejson.dumps = json.dumps
        simplejson.loads = json.loads
        sys.modules['simplejson'] = simplejson

    if 'termcolor' not in sys.modules:
        termcolor = types.ModuleType('termcolor')
        termcolor.colored = lambda value, *args, **kwargs: value
        sys.modules['termcolor'] = termcolor

    if 'OpenSSL' not in sys.modules:
        sys.modules['OpenSSL'] = types.ModuleType('OpenSSL')

    if 'Crypto' not in sys.modules:
        crypto = types.ModuleType('Crypto')
        crypto_cipher = types.ModuleType('Crypto.Cipher')
        crypto_cipher.AES = object()
        crypto_util = types.ModuleType('Crypto.Util')
        crypto_py3compat = types.ModuleType('Crypto.Util.py3compat')

        sys.modules['Crypto'] = crypto
        sys.modules['Crypto.Cipher'] = crypto_cipher
        sys.modules['Crypto.Util'] = crypto_util
        sys.modules['Crypto.Util.py3compat'] = crypto_py3compat


@pytest.fixture(scope='module')
def ctl_module():
    _install_ctl_import_stubs()
    sys.modules.pop('zstackctl.ctl', None)
    return importlib.import_module('zstackctl.ctl')


def test_shell_join_quotes_special_characters_and_skips_none(ctl_module):
    got = ctl_module.shell_join('mysql', '--password=Tmp@&123', None, '-e', "select 'a b'")
    assert got == "'mysql' '--password=Tmp@&123' '-e' 'select '\\''a b'\\'''"


def test_mysql_sql_escape_escapes_quotes_backslashes_and_none(ctl_module):
    assert ctl_module.mysql_sql_escape("Ab'\\12") == "Ab\\'\\\\12"
    assert ctl_module.mysql_sql_escape(None) == 'None'


@pytest.mark.parametrize(
    'password, expected',
    [
        (None, None),
        ('', None),
        ('Tmp@&123', '--password=Tmp@&123'),
    ],
)
def test_mysql_password_arg(ctl_module, password, expected):
    assert ctl_module.mysql_password_arg(password) == expected


def test_redact_cmd_args_masks_supported_password_forms(ctl_module):
    cmd_args = [
        'mysql',
        '--password=Tmp@&123',
        '--root-password',
        'Root#123',
        '--new-password',
        'New#123',
        '-pTmp@&123',
        'password=plain',
    ]
    assert ctl_module.redact_cmd_args(cmd_args) == [
        'mysql',
        '--password=******',
        '--root-password',
        '******',
        '--new-password',
        '******',
        '-p******',
        'password=******',
    ]


def test_redact_sensitive_cmd_masks_shell_password_strings(ctl_module):
    cmd = (
        "mysql --password=Tmp@&123 --root-password Root#123 "
        "--new-password New#123 -pTmp@&123 password=plain"
    )
    assert ctl_module.redact_sensitive_cmd(cmd) == (
        "mysql --password=****** --root-password ****** "
        "--new-password ****** -p****** password=******"
    )


def test_redact_mysql_sql_masks_identified_by_and_password_function(ctl_module):
    sql = (
        "GRANT USAGE ON *.* TO 'user'@'%' IDENTIFIED BY 'Tmp@&123'; "
        "SET PASSWORD FOR 'user'@'%' = PASSWORD('Next#123');"
    )
    assert ctl_module.redact_mysql_sql(sql) == (
        "GRANT USAGE ON *.* TO 'user'@'%' IDENTIFIED BY '******'; "
        "SET PASSWORD FOR 'user'@'%' = PASSWORD('******');"
    )


def test_mysql_cmd_args_builds_expected_argument_list(ctl_module):
    got = ctl_module.mysql_cmd_args(
        'root',
        password='Tmp@&123',
        host='172.26.21.158',
        port='3306',
        database='zstack',
        sql='select 1',
        extra_args=['-N'],
    )
    assert got == [
        'mysql',
        '-N',
        '-u',
        'root',
        '--password=Tmp@&123',
        '--host',
        '172.26.21.158',
        '--port',
        '3306',
        'zstack',
        '-e',
        'select 1',
    ]


def test_mysql_shell_display_cmd_redacts_password_and_sql_secrets(ctl_module):
    got = ctl_module.mysql_shell_display_cmd(
        'root',
        password='Tmp@&123',
        sql="GRANT USAGE ON *.* TO 'user'@'%' IDENTIFIED BY 'Tmp@&123';",
        extra_args=['-N'],
    )
    assert got == (
        "'mysql' '-N' '-u' 'root' '--password=******' '-e' "
        "'GRANT USAGE ON *.* TO '\\''user'\\''@'\\''%'\\'' IDENTIFIED BY '\\''******'\\'';'"
    )


def test_run_flyway_precheck_uses_shell_join_and_redacted_display(ctl_module, monkeypatch):
    captured = {}

    def fake_shell(cmd, is_exception=True, display_cmd=None):
        captured['cmd'] = cmd
        captured['display_cmd'] = display_cmd
        return '| Success |\n'

    monkeypatch.setattr(ctl_module, 'shell', fake_shell)
    monkeypatch.setattr(ctl_module, 'info', lambda *args, **kwargs: None)

    ctl_module.run_flyway_precheck(
        '/tmp/flyway',
        'zstack',
        'Tmp@&123',
        'jdbc:mysql://127.0.0.1:3306/zstack',
        '/tmp/upgrade dir',
    )

    expected_args = [
        'bash',
        '/tmp/flyway',
        'info',
        '-outOfOrder=true',
        '-user=zstack',
        '-password=Tmp@&123',
        '-url=jdbc:mysql://127.0.0.1:3306/zstack',
        '-locations=filesystem:/tmp/upgrade dir',
    ]
    assert captured['cmd'] == ctl_module.shell_join(*expected_args)
    assert captured['display_cmd'] == ctl_module.shell_join_redacted(*expected_args)
    assert "'-password=******'" in captured['display_cmd']


def test_run_mysqlcheck_zstack_uses_shell_join_and_redacted_display(ctl_module, monkeypatch):
    captured = {}

    monkeypatch.setattr(ctl_module, 'error_if_tool_is_missing', lambda tool: captured.setdefault('tool', tool))

    def fake_shell(cmd, is_exception=True, display_cmd=None):
        captured['cmd'] = cmd
        captured['display_cmd'] = display_cmd
        return ''

    monkeypatch.setattr(ctl_module, 'shell', fake_shell)

    ctl_module.run_mysqlcheck_zstack('root', "Ab'\\\\12", '172.26.21.158', 3306)

    expected_args = [
        'mysqlcheck',
        '-u',
        'root',
        "--password=Ab'\\\\12",
        '--host',
        '172.26.21.158',
        '--port',
        '3306',
        'zstack',
    ]
    assert captured['tool'] == 'mysqlcheck'
    assert captured['cmd'] == ctl_module.shell_join(*expected_args)
    assert captured['display_cmd'] == ctl_module.shell_join_redacted(*expected_args)
    assert "'--password=******'" in captured['display_cmd']
