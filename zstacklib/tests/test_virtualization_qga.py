"""Tests for virtualization.qga module."""

import pytest

from zstacklib.virtualization.qga import (
    QgaError,
    QgaNotRunningError,
    QgaCommandError,
    QgaCommandDisabledError,
    QgaCommandNotSupportedError,
    QgaTimeoutError,
    QgaReturnValueError,
    QgaState,
    GuestOS,
    QGA_EXEC_WAIT_INTERVAL,
    QGA_EXEC_WAIT_RETRY,
)


class TestQgaExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(QgaNotRunningError, QgaError)
        assert issubclass(QgaCommandError, QgaError)
        assert issubclass(QgaCommandDisabledError, QgaError)
        assert issubclass(QgaCommandNotSupportedError, QgaError)
        assert issubclass(QgaTimeoutError, QgaError)
        assert issubclass(QgaReturnValueError, QgaError)

    def test_command_error_message(self):
        err = QgaCommandError("guest-exec", "command failed")
        assert "guest-exec" in str(err)
        assert "failed" in str(err)
        assert err.command == "guest-exec"

    def test_command_disabled_error(self):
        err = QgaCommandDisabledError("guest-exec")
        assert "guest-exec" in str(err)
        assert "disabled" in str(err)
        assert err.command == "guest-exec"

    def test_command_not_supported_error(self):
        err = QgaCommandNotSupportedError("guest-exec", "2.0")
        assert "guest-exec" in str(err)
        assert "not supported" in str(err)
        assert err.command == "guest-exec"
        assert err.version == "2.0"

    def test_timeout_error(self):
        err = QgaTimeoutError("guest-exec", 30)
        assert "guest-exec" in str(err)
        assert "30" in str(err)
        assert err.command == "guest-exec"
        assert err.timeout == 30


class TestQgaState:
    def test_state_values(self):
        assert QgaState.RUNNING.value == "Running"
        assert QgaState.NOT_RUNNING.value == "NotRunning"

    def test_state_comparison(self):
        assert QgaState.RUNNING != QgaState.NOT_RUNNING

    def test_state_is_string_enum(self):
        assert isinstance(QgaState.RUNNING, str)
        assert QgaState.RUNNING == "Running"


class TestGuestOS:
    def test_guest_os_values(self):
        assert GuestOS.WINDOWS.value == "mswindows"
        assert GuestOS.LINUX_CENTOS.value == "centos"
        assert GuestOS.LINUX_UBUNTU.value == "ubuntu"

    def test_guest_os_is_string_enum(self):
        assert isinstance(GuestOS.WINDOWS, str)


class TestConstants:
    def test_exec_wait_constants(self):
        assert QGA_EXEC_WAIT_INTERVAL > 0
        assert QGA_EXEC_WAIT_RETRY > 0
        assert isinstance(QGA_EXEC_WAIT_INTERVAL, int)
        assert isinstance(QGA_EXEC_WAIT_RETRY, int)
