# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
# pyright: reportAny=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportAttributeAccessIssue=false
from __future__ import annotations
"""Handler-level unit tests for kvmagent.plugins.ai_model_plugin.

ZSTAC-83157: Unit tests for AI Model Mount Plugin handlers.
Tests use mocks to simulate VM, QEMU Guest Agent, and file system operations.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from zstacklib.utils import http, jsonobject
from kvmagent.plugins import ai_model_plugin


def _make_req(body_dict=None):
    """Create a mock HTTP request with JSON body."""
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_ai_model_plugin():
    """Create an AI Model Plugin instance without initialization."""
    plugin = ai_model_plugin.AIModelMountPlugin.__new__(
        ai_model_plugin.AIModelMountPlugin
    )
    plugin.config = {}
    return plugin


def _mock_qga(state="Running"):
    """Create a mock QGA with specified state."""
    mock_qga = MagicMock()
    mock_qga.state = state
    # Set default return value for guest_exec_cmd_no_exitcode (exitcode, output)
    mock_qga.guest_exec_cmd_no_exitcode.return_value = (0, "")
    return mock_qga


class MockVmQga:
    """Mock VmQga class that returns configured mock instances."""

    QGA_STATE_RUNNING = "Running"
    QGA_STATE_NOT_RUNNING = "NotRunning"

    def __init__(self, mock_qga_instance):
        self.mock_qga = mock_qga_instance

    def __call__(self, domain):
        return self.mock_qga


# Mock the modules that the plugin imports
ai_model_plugin.http = http
ai_model_plugin.jsonobject = jsonobject


@pytest.mark.kvmagent
class TestAttachModelHandler:
    """Test /aimodel/attach handler."""

    def test_attach_model_success(self):
        """Test successful model mount to VM."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")

        # Replace VmQga class with a factory that returns our mock
        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "zdfsUrl": "redis://:password@192.168.1.100:6379/1",
                    "juicefsSubdir": "models/Qwen/2.5b",
                    "mountPath": "/mnt/models/qwen"
                })

                result = plugin.attach_model(req)
                rsp = json.loads(result)

                # Debug: print response if failed
                if not rsp.get("success"):
                    print(f"Response: {rsp}")
                    print(f"Error: {rsp.get('error')}")

                assert rsp["success"] is True
                # error field is empty string on success (from AgentResponse base class)
                assert rsp.get("error") == ""
                # Verify the optimized implementation calls guest_exec_cmd_no_exitcode
                mock_qga.guest_exec_cmd_no_exitcode.assert_called_once()
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_attach_model_vm_not_found(self):
        """Test attach model when VM does not exist."""
        plugin = _make_ai_model_plugin()

        with patch.object(
            ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=None
        ):
            req = _make_req({
                "vmInstanceUuid": "non-existent-vm",
                "zdfsUrl": "redis://127.0.0.1:6379/1",
                "juicefsSubdir": "models/test",
                "mountPath": "/mnt/test"
            })

            result = plugin.attach_model(req)
            rsp = json.loads(result)

            assert rsp["success"] is False
            assert "VM not found" in rsp["error"]
            assert "non-existent-vm" in rsp["error"]

    def test_attach_model_qga_not_running(self):
        """Test attach model when QEMU Guest Agent is not running."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="NotRunning")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "zdfsUrl": "redis://127.0.0.1:6379/1",
                    "juicefsSubdir": "models/test",
                    "mountPath": "/mnt/test"
                })

                result = plugin.attach_model(req)
                rsp = json.loads(result)

                assert rsp["success"] is False
                assert "Qemu Guest Agent is not running" in rsp["error"]
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_attach_model_mount_command_generation(self):
        """Test that mount command is generated correctly."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "zdfsUrl": "redis://:password@192.168.1.100:6379/1",
                    "juicefsSubdir": "models/Qwen/2.5b",
                    "mountPath": "/mnt/models/qwen"
                })

                plugin.attach_model(req)

                # Verify the mount command contains all required components
                call_args = mock_qga.guest_exec_cmd_no_exitcode.call_args[0][0]
                assert "mkdir -p" in call_args
                assert "juicefs mount" in call_args
                assert "--subdir" in call_args
                assert "--read-only" in call_args
                assert "mountpoint -q" in call_args
                assert "/mnt/models/qwen" in call_args
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_attach_model_mount_command_fails(self):
        """Test attach model when mount command execution fails."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")
        mock_qga.guest_exec_cmd_no_exitcode.return_value = (1, "Mount failed")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "zdfsUrl": "redis://127.0.0.1:6379/1",
                    "juicefsSubdir": "models/test",
                    "mountPath": "/mnt/test"
                })

                result = plugin.attach_model(req)
                rsp = json.loads(result)

                assert rsp["success"] is False
                assert "Failed to mount JuiceFS" in rsp["error"]
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_attach_model_mount_command_fails_with_error(self):
        """Test attach model when mount command execution fails with error output."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")
        mock_qga.guest_exec_cmd_no_exitcode.return_value = (1, "Device or resource busy")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "zdfsUrl": "redis://127.0.0.1:6379/1",
                    "juicefsSubdir": "models/test",
                    "mountPath": "/mnt/test"
                })

                result = plugin.attach_model(req)
                rsp = json.loads(result)

                assert rsp["success"] is False
                assert "Failed to mount JuiceFS" in rsp["error"]
                assert "Device or resource busy" in rsp["error"]
        finally:
            ai_model_plugin.VmQga = original_vmqga



@pytest.mark.kvmagent
class TestDetachModelHandler:
    """Test /aimodel/detach handler."""

    def test_detach_model_success(self):
        """Test successful model unmount from VM."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")
        mock_qga.guest_exec_cmd_no_exitcode.return_value = (0, "")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "mountPath": "/mnt/models/qwen"
                })

                result = plugin.detach_model(req)
                rsp = json.loads(result)

                assert rsp["success"] is True
                mock_qga.guest_exec_cmd_no_exitcode.assert_called()
                call_args = mock_qga.guest_exec_cmd_no_exitcode.call_args[0][0]
                assert "umount" in call_args
                assert "/mnt/models/qwen" in call_args
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_detach_model_vm_not_found(self):
        """Test detach model when VM does not exist."""
        plugin = _make_ai_model_plugin()

        with patch.object(
            ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=None
        ):
            req = _make_req({
                "vmInstanceUuid": "non-existent-vm",
                "mountPath": "/mnt/test"
            })

            result = plugin.detach_model(req)
            rsp = json.loads(result)

            assert rsp["success"] is False
            assert "VM not found" in rsp["error"]
            assert "non-existent-vm" in rsp["error"]

    def test_detach_model_qga_not_running(self):
        """Test detach model when QEMU Guest Agent is not running."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="NotRunning")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "mountPath": "/mnt/test"
                })

                result = plugin.detach_model(req)
                rsp = json.loads(result)

                assert rsp["success"] is False
                assert "Qemu Guest Agent is not running" in rsp["error"]
        finally:
            ai_model_plugin.VmQga = original_vmqga

    def test_detach_model_unmount_fails_gracefully(self):
        """Test detach model handles unmount failure gracefully."""
        plugin = _make_ai_model_plugin()
        mock_vm = MagicMock()
        mock_vm.domain = MagicMock()
        mock_qga = _mock_qga(state="Running")
        mock_qga.guest_exec_cmd_no_exitcode.return_value = (1, "Device is busy")

        original_vmqga = ai_model_plugin.VmQga
        ai_model_plugin.VmQga = MockVmQga(mock_qga)

        try:
            with patch.object(
                ai_model_plugin.vm_plugin, "get_vm_by_uuid", return_value=mock_vm
            ):
                req = _make_req({
                    "vmInstanceUuid": "test-vm-uuid",
                    "mountPath": "/mnt/test"
                })

                result = plugin.detach_model(req)
                rsp = json.loads(result)

                # Unmount failure is non-blocking, still returns success
                assert rsp["success"] is True
        finally:
            ai_model_plugin.VmQga = original_vmqga


@pytest.mark.kvmagent
class TestPluginLifecycle:
    """Test plugin lifecycle methods."""

    def test_plugin_start(self):
        """Test plugin registers HTTP handlers on start."""
        plugin = _make_ai_model_plugin()
        mock_http_server = MagicMock()

        with patch.object(
            ai_model_plugin.kvmagent, "get_http_server", return_value=mock_http_server
        ):
            plugin.start()

            mock_http_server.register_async_uri.assert_any_call(
                plugin.ATTACH_MODEL_PATH, plugin.attach_model
            )
            mock_http_server.register_async_uri.assert_any_call(
                plugin.DETACH_MODEL_PATH, plugin.detach_model
            )

    def test_plugin_configure(self):
        """Test plugin configuration."""
        plugin = _make_ai_model_plugin()
        config = {"test": "config"}

        plugin.configure(config)

        assert plugin.config == config

    def test_plugin_stop(self):
        """Test plugin stop is a no-op."""
        plugin = _make_ai_model_plugin()
        plugin.stop()  # Should not raise any exception


@pytest.mark.kvmagent
class TestMessageClasses:
    """Test message and reply classes."""

    def test_attach_model_msg_initialization(self):
        """Test KvmAttachModelMsg initialization."""
        msg = ai_model_plugin.KvmAttachModelMsg()

        assert msg.vmInstanceUuid is None
        assert msg.zdfsUrl is None
        assert msg.juicefsSubdir is None
        assert msg.mountPath is None

    def test_attach_model_reply_initialization(self):
        """Test KvmAttachModelReply initialization."""
        reply = ai_model_plugin.KvmAttachModelReply()

        # AgentResponse base class defaults success=True
        assert reply.success is True

    def test_detach_model_msg_initialization(self):
        """Test KvmDetachModelMsg initialization."""
        msg = ai_model_plugin.KvmDetachModelMsg()

        assert msg.vmInstanceUuid is None
        assert msg.mountPath is None

    def test_detach_model_reply_initialization(self):
        """Test KvmDetachModelReply initialization."""
        reply = ai_model_plugin.KvmDetachModelReply()

        # AgentResponse base class defaults success=True
        assert reply.success is True
