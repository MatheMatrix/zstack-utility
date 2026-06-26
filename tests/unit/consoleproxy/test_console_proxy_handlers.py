from __future__ import annotations

import importlib
import json
import pytest
import os
import sys
import time
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock, patch, mock_open


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _ConsoleProxyModule(Protocol):
    ConsoleProxyAgent: type
    ConsoleProxyDaemon: type
    ConsoleTokenFile: type
    ConsoleTokenFileController: type
    AgentResponse: type
    CheckAvailabilityRsp: type
    EstablishProxyRsp: type
    ConsoleProxyError: type


def _setup_lock_passthrough():
    """Make lock.lock a passthrough decorator so decorated methods work."""
    from tests.conftest import passthrough_lock
    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))
    setattr(lock_mod, "lock", passthrough_lock)
    setattr(lock_mod, "file_lock", passthrough_lock)


try:
    _setup_lock_passthrough()
    module = cast(
        _ConsoleProxyModule,
        cast(object, importlib.reload(importlib.import_module("consoleproxy.console_proxy_agent"))),
    )
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import console_proxy_agent: {e}", allow_module_level=True)


def _make_req(body_dict=None):
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_agent():
    """Create a ConsoleProxyAgent via __new__ (skip __init__ side effects).

    __init__ creates directories, instantiates FileDB and
    ConsoleTokenFileController — all of which require a real filesystem.
    """
    agent = module.ConsoleProxyAgent.__new__(module.ConsoleProxyAgent)
    agent.db = MagicMock()
    agent.token_ctrl = MagicMock()
    return agent


def _load_rsp(result):
    return json.loads(result)


@pytest.mark.consoleproxy
class TestIpv6HostPortFormatting:
    def test_format_host_port_for_url_brackets_ipv6(self):
        assert module.format_host_port_for_url("192.168.10.10", 5900) == "192.168.10.10:5900"
        assert module.format_host_port_for_url("console-proxy.example.com", 5900) == "console-proxy.example.com:5900"
        assert module.format_host_port_for_url("2001:db8::10", 5900) == "[2001:db8::10]:5900"

    def test_format_host_port_for_websockify_target_uses_socket_host(self):
        assert module.format_host_port_for_websockify_target("192.168.10.10", 5900) == "192.168.10.10:5900"
        assert module.format_host_port_for_websockify_target("2001:db8::10", 5900) == "2001:db8::10:5900"
        assert module.format_host_port_for_websockify_target("[2001:db8::10]", 5900) == "2001:db8::10:5900"

    @patch.object(module, "is_ipv6_stack_available", return_value=True)
    def test_websockify_bind_uses_ipv6_wildcard_when_dual_stack_supported(self, mock_stack):
        with patch("builtins.open", mock_open(read_data="0\n")):
            assert module.format_host_port_for_websockify_bind("0.0.0.0", 6800) == "[::]:6800"
        assert module.format_host_port_for_websockify_bind("192.168.10.10", 6800) == "192.168.10.10:6800"

    @patch.object(module, "is_ipv6_stack_available", return_value=True)
    def test_websockify_bind_keeps_ipv4_wildcard_when_v6only_enabled(self, mock_stack):
        with patch("builtins.open", mock_open(read_data="1\n")):
            assert module.format_host_port_for_websockify_bind("0.0.0.0", 6800) == "0.0.0.0:6800"

    @patch.object(module, "is_ipv6_stack_available", return_value=True)
    def test_websockify_bind_keeps_ipv4_wildcard_when_v6only_unknown(self, mock_stack):
        with patch("builtins.open", side_effect=OSError):
            assert module.format_host_port_for_websockify_bind("0.0.0.0", 6800) == "0.0.0.0:6800"

    @patch.object(module, "is_ipv6_stack_available", return_value=False)
    def test_websockify_bind_keeps_ipv4_wildcard_without_ipv6_stack(self, mock_stack):
        assert module.format_host_port_for_websockify_bind("0.0.0.0", 6800) == "0.0.0.0:6800"
        assert module.format_host_port_for_websockify_bind("192.168.10.10", 6800) == "192.168.10.10:6800"

    @patch.object(module, "bash_roe")
    def test_get_websockify_processes_filters_ps_output_in_python(self, mock_bash):
        mock_bash.return_value = (0, "\n".join([
            "  PID COMMAND",
            " 123 python -c from zstacklib.utils import log; websockify.websocketproxy.websockify_init() [::]:6800",
            " abc invalid pid zstack websockify_init",
            " 456 grep zstack websockify_init",
            " 789 python unrelated",
        ]), "")

        assert module.get_websockify_processes() == [
            (123, "python -c from zstacklib.utils import log; websockify.websocketproxy.websockify_init() [::]:6800"),
        ]
        mock_bash.assert_called_once_with("ps -eo pid,args")


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestPing:
    def test_ping_returns_success(self):
        agent = _make_agent()
        result = agent.ping(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# check_proxy_availability — VNC path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestCheckProxyAvailabilityVnc:
    def test_vnc_available_when_websockify_running_and_db_matches(self):
        agent = _make_agent()
        token = "vm_abc_123"
        target_host = "10.0.0.1"
        target_port = 5900
        proxy_port = 6800

        # _get_pid_on_port returns a valid pid
        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = "tcp  0  0  0.0.0.0:6800  0.0.0.0:*  LISTEN  12345/python\n"
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        # /proc/<pid>/cmdline contains websockify
        cmdline_content = "python\x00websockify_init\x00"

        # db.get returns matching info
        db_info = json.dumps({
            "token": token,
            "targetPort": target_port,
            "targetHostname": target_host,
        })
        agent.db.get.return_value = db_info

        with patch("builtins.open", mock_open(read_data=cmdline_content)):
            result = agent.check_proxy_availability(_make_req({
                "proxyPort": proxy_port,
                "targetSchema": "vnc",
                "targetHostname": target_host,
                "targetPort": target_port,
                "token": token,
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is True

    def test_vnc_unavailable_when_no_process_on_port(self):
        agent = _make_agent()

        # _get_pid_on_port returns None (empty output)
        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = ""
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        result = agent.check_proxy_availability(_make_req({
            "proxyPort": 6800,
            "targetSchema": "vnc",
            "targetHostname": "10.0.0.1",
            "targetPort": 5900,
            "token": "vm_abc_123",
        }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False

    def test_vnc_unavailable_when_not_websockify_process(self):
        agent = _make_agent()

        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = "tcp  0  0  0.0.0.0:6800  0.0.0.0:*  LISTEN  12345/nginx\n"
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        # cmdline does NOT contain websockify
        with patch("builtins.open", mock_open(read_data="nginx\x00worker\x00")):
            result = agent.check_proxy_availability(_make_req({
                "proxyPort": 6800,
                "targetSchema": "vnc",
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False

    def test_vnc_unavailable_when_db_has_no_entry(self):
        agent = _make_agent()

        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = "tcp  0  0  0.0.0.0:6800  0.0.0.0:*  LISTEN  12345/python\n"
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        agent.db.get.return_value = None

        with patch("builtins.open", mock_open(read_data="python\x00websockify_init\x00")):
            result = agent.check_proxy_availability(_make_req({
                "proxyPort": 6800,
                "targetSchema": "vnc",
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False

    def test_vnc_unavailable_when_db_token_mismatch(self):
        agent = _make_agent()

        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = "tcp  0  0  0.0.0.0:6800  0.0.0.0:*  LISTEN  12345/python\n"
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        db_info = json.dumps({
            "token": "different_token",
            "targetPort": 5900,
            "targetHostname": "10.0.0.1",
        })
        agent.db.get.return_value = db_info

        with patch("builtins.open", mock_open(read_data="python\x00websockify_init\x00")):
            result = agent.check_proxy_availability(_make_req({
                "proxyPort": 6800,
                "targetSchema": "vnc",
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False


# ---------------------------------------------------------------------------
# check_proxy_availability — HTTP path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestCheckProxyAvailabilityHttp:
    @patch.object(module, "bash_roe", return_value=(0, "active (running)", ""))
    def test_http_available_when_nginx_running(self, mock_bash):
        agent = _make_agent()
        result = agent.check_proxy_availability(_make_req({
            "targetSchema": "http",
            "proxyPort": 80,
            "targetHostname": "10.0.0.1",
            "targetPort": 8080,
            "token": "bm_token",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is True

    @patch.object(module, "bash_roe", return_value=(1, "", "service not found"))
    def test_http_unavailable_when_nginx_not_running(self, mock_bash):
        agent = _make_agent()
        result = agent.check_proxy_availability(_make_req({
            "targetSchema": "http",
            "proxyPort": 80,
            "targetHostname": "10.0.0.1",
            "targetPort": 8080,
            "token": "bm_token",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False

    def test_unknown_schema_returns_unavailable(self):
        agent = _make_agent()
        result = agent.check_proxy_availability(_make_req({
            "targetSchema": "unknown",
            "proxyPort": 80,
            "targetHostname": "10.0.0.1",
            "targetPort": 8080,
            "token": "tok",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["available"] is False


# ---------------------------------------------------------------------------
# establish_new_proxy — parameter validation
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestEstablishNewProxyValidation:
    def test_null_target_hostname_returns_error(self):
        agent = _make_agent()
        result = agent.establish_new_proxy(_make_req({
            "targetHostname": None,
            "targetPort": 5900,
            "token": "tok",
            "proxyHostname": "proxy1",
            "proxyPort": 6800,
            "expiredDate": str(int(time.time() * 1000) + 60000),
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "targetHostname" in rsp["error"]

    def test_null_token_returns_error(self):
        agent = _make_agent()
        result = agent.establish_new_proxy(_make_req({
            "targetHostname": "10.0.0.1",
            "targetPort": 5900,
            "token": None,
            "proxyHostname": "proxy1",
            "proxyPort": 6800,
            "expiredDate": str(int(time.time() * 1000) + 60000),
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "token" in rsp["error"]

    def test_null_proxy_hostname_returns_error(self):
        agent = _make_agent()
        result = agent.establish_new_proxy(_make_req({
            "targetHostname": "10.0.0.1",
            "targetPort": 5900,
            "token": "tok",
            "proxyHostname": None,
            "proxyPort": 6800,
            "expiredDate": str(int(time.time() * 1000) + 60000),
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "proxyHostname" in rsp["error"]


# ---------------------------------------------------------------------------
# establish_new_proxy — VNC path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestEstablishNewVncProxy:
    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    def test_establish_vnc_proxy_success(self, mock_bash):
        agent = _make_agent()
        token_file_mock = MagicMock()
        token_file_mock.get_absolute_path.return_value = "/var/lib/zstack/consoleProxy/vm_abc_123"

        future_expired = str(int(time.time() * 1000) + 600000)

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
                "proxyHostname": "proxy1",
                "proxyPort": 6800,
                "expiredDate": future_expired,
                "targetSchema": "vnc",
                "sslCertFile": None,
                "idleTimeout": 600,
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["proxyPort"] == 6800

        # verify token file was written and db was updated
        token_file_mock.flush_write.assert_called_once()
        agent.token_ctrl.submit_delete_token_task.assert_called_once()
        agent.db.set.assert_called_once()

    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    def test_establish_vnc_proxy_uses_socket_ipv6_token_target(self, mock_bash):
        agent = _make_agent()
        token_file_mock = MagicMock()
        token_file_mock.get_absolute_path.return_value = "/var/lib/zstack/consoleProxy/vm_ipv6_123"

        future_expired = str(int(time.time() * 1000) + 600000)

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "2001:db8::11",
                "targetPort": 5900,
                "token": "vm_ipv6_123",
                "proxyHostname": "2001:db8::10",
                "proxyPort": 6800,
                "expiredDate": future_expired,
                "targetSchema": "vnc",
                "sslCertFile": None,
                "idleTimeout": 600,
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        token_file_mock.flush_write.assert_called_once_with("vm_ipv6_123: 2001:db8::11:5900")
        assert mock_bash.called

    @patch.object(module, "is_dual_stack_wildcard_supported", return_value=True)
    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    def test_establish_vnc_proxy_binds_ipv6_wildcard_for_dual_stack(self, mock_bash, mock_dual_stack):
        agent = _make_agent()
        token_file_mock = MagicMock()
        token_file_mock.get_absolute_path.return_value = "/var/lib/zstack/consoleProxy/vm_dual_stack_123"

        future_expired = str(int(time.time() * 1000) + 600000)

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "2001:db8::11",
                "targetPort": 5900,
                "token": "vm_dual_stack_123",
                "proxyHostname": "0.0.0.0",
                "proxyPort": 6800,
                "expiredDate": future_expired,
                "targetSchema": "vnc",
                "sslCertFile": None,
                "idleTimeout": 600,
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        token_file_mock.flush_write.assert_called_once_with("vm_dual_stack_123: 2001:db8::11:5900")
        assert mock_bash.called

    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    @patch.object(module, "get_websockify_processes")
    @patch.object(module.os, "kill")
    def test_establish_vnc_proxy_kills_garbage_process_without_shell_grep(
            self, mock_kill, mock_processes, mock_bash):
        agent = _make_agent()
        token_file_mock = MagicMock()
        token_file_mock.get_absolute_path.return_value = "/var/lib/zstack/consoleProxy/vm_cert_123"
        mock_processes.side_effect = [
            [
                (123, "python -c zstacklib websockify.websocketproxy.websockify_init() proxy1:6800 --cert=/old.pem"),
                (124, "python -c zstacklib websockify.websocketproxy.websockify_init() proxy1:6800 --cert=/keep.pem"),
            ],
            [],
        ]

        future_expired = str(int(time.time() * 1000) + 600000)

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_cert_123",
                "proxyHostname": "proxy1",
                "proxyPort": 6800,
                "expiredDate": future_expired,
                "targetSchema": "vnc",
                "sslCertFile": "/keep.pem",
                "idleTimeout": 600,
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_kill.assert_called_once_with(123, 15)
        assert all("ps aux | grep" not in call_args[0][0] for call_args in mock_bash.call_args_list)


# ---------------------------------------------------------------------------
# establish_new_proxy — HTTP path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestEstablishNewHttpProxy:
    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    @patch("os.path.exists", return_value=True)
    def test_establish_http_proxy_success(self, mock_exists, mock_bash):
        agent = _make_agent()
        future_expired = str(int(time.time() * 1000) + 600000)

        with patch("builtins.open", mock_open()):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "10.0.0.1",
                "targetPort": 8080,
                "token": "bm_token_123",
                "proxyHostname": "proxy1",
                "proxyPort": 80,
                "expiredDate": future_expired,
                "targetSchema": "http",
                "vmUuid": "vm-uuid-001",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["proxyPort"] == 80
        assert rsp["token"] == "bm_token_123"

    @patch.object(module, "bash_roe", return_value=(0, "", ""))
    @patch("os.path.exists", return_value=True)
    def test_establish_http_proxy_uses_bracketed_ipv6_upstream(self, mock_exists, mock_bash):
        agent = _make_agent()
        future_expired = str(int(time.time() * 1000) + 600000)
        mocked_open = mock_open()

        with patch("builtins.open", mocked_open):
            result = agent.establish_new_proxy(_make_req({
                "targetHostname": "2001:db8::20",
                "targetPort": 8080,
                "token": "bm_token_ipv6",
                "proxyHostname": "proxy1",
                "proxyPort": 80,
                "expiredDate": future_expired,
                "targetSchema": "http",
                "vmUuid": "vm-uuid-ipv6",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mocked_open().write.assert_called_once_with(
            "location ^~/bm_token_ipv6/ { proxy_set_header Host $host; proxy_pass http://[2001:db8::20]:8080; }")


# ---------------------------------------------------------------------------
# delete — VNC path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestDeleteVncProxy:
    def test_delete_vnc_proxy_success(self):
        agent = _make_agent()
        token_file_mock = MagicMock()

        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = ""
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.delete(_make_req({
                "targetSchema": "vnc",
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True

        agent.token_ctrl.cancel_delete_token_task.assert_called_once_with(token_file_mock)
        agent.token_ctrl.delete_token_file.assert_called_once_with(token_file_mock)

    def test_delete_vnc_default_schema(self):
        """When targetSchema is not set, defaults to VNC."""
        agent = _make_agent()
        token_file_mock = MagicMock()

        shell_cmd_instance = MagicMock()
        shell_cmd_instance.stdout = ""
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd.return_value = shell_cmd_instance

        with patch.object(module, "ConsoleTokenFile", return_value=token_file_mock):
            result = agent.delete(_make_req({
                "targetHostname": "10.0.0.1",
                "targetPort": 5900,
                "token": "vm_abc_123",
            }))

        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# delete — HTTP path
# ---------------------------------------------------------------------------
@pytest.mark.consoleproxy
class TestDeleteHttpProxy:
    @patch.object(module, "bash_roe", return_value=(0, "active", ""))
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_delete_http_proxy_success(self, mock_remove, mock_exists, mock_bash):
        agent = _make_agent()
        result = agent.delete(_make_req({
            "targetSchema": "http",
            "vmUuid": "vm-uuid-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_remove.assert_called_once()

    @patch.object(module, "bash_roe", return_value=(1, "", "not found"))
    def test_delete_http_proxy_nginx_not_running_fails_start(self, mock_bash):
        agent = _make_agent()
        # bash_roe returns failure for both status and start
        result = agent.delete(_make_req({
            "targetSchema": "http",
            "vmUuid": "vm-uuid-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "failed to start" in rsp["error"]
