# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Protocol

from zstacklib.virtualization.qga.constants import (
    GuestOS,
    QGA_EXEC_WAIT_INTERVAL,
    QGA_EXEC_WAIT_RETRY,
    QgaState,
    ZS_TOOLS_PATH_WIN,
    ZS_TOOLS_WAIT_RETRY,
)
from zstacklib.virtualization.qga.exceptions import (
    QgaCommandDisabledError,
    QgaCommandError,
    QgaCommandNotSupportedError,
    QgaReturnValueError,
    QgaTimeoutError,
)
from zstacklib.virtualization.qga.utils import is_qga_connected

LOG = logging.getLogger(__name__)


class LibvirtDomain(Protocol):
    def name(self) -> str: ...
    def XMLDesc(self) -> str: ...
    def isActive(self) -> bool: ...


class LibvirtQemu(Protocol):
    @staticmethod
    def qemuAgentCommand(domain: Any, cmd: str, timeout: int, flags: int) -> str: ...


class VmQga:
    def __init__(
        self,
        domain: LibvirtDomain,
        libvirt_qemu: LibvirtQemu,
    ) -> None:
        self.domain = domain
        self.libvirt_qemu = libvirt_qemu
        self.vm_uuid = domain.name()
        self.state = QgaState.NOT_RUNNING
        self.version: str | None = None
        self.supported_commands: dict[str, bool] = {}
        self.os: str | None = None
        self.os_version: str | None = None
        self.os_id_like: str | None = None
        self._init_qga()

    def _init_qga(self) -> None:
        self.state = QgaState.NOT_RUNNING
        if not is_qga_connected(self.domain.XMLDesc()):
            return

        if self.domain.isActive() and self.is_agent_available():
            self.state = QgaState.RUNNING
        else:
            return

        ret = self._guest_info()
        if ret:
            self.version = ret.get("version")
            supported_commands = ret.get("supported_commands", [])
            self.supported_commands = {
                cmd["name"]: cmd["enabled"] for cmd in supported_commands
            }

        try:
            if self.supported_commands.get('guest-get-osinfo'):
                self.os, self.os_version = self._get_os_info_via_command()
                if self.os == GuestOS.WINDOWS:
                    self.os_id_like = "windows"
                else:
                    self.os_id_like = self._get_os_id_like()
            else:
                self.os, self.os_version, self.os_id_like = self._get_os_info_via_file()
        except Exception as e:
            LOG.debug(f"qga init failed: {e}")

    def call_qga_command(
        self,
        command: str,
        args: dict[str, Any] | None = None,
        timeout: int = 3,
    ) -> Any:
        if self.supported_commands:
            if command not in self.supported_commands:
                raise QgaCommandNotSupportedError(command, self.version)
            if not self.supported_commands[command]:
                raise QgaCommandDisabledError(command)

        cmd_dict: dict[str, Any] = {'execute': command}
        if args:
            processed_args = args.copy()
            if 'buf-b64' in processed_args:
                processed_args['buf-b64'] = base64.b64encode(
                    processed_args['buf-b64']
                ).decode('ascii')
            cmd_dict['arguments'] = processed_args

        cmd_json = json.dumps(cmd_dict)
        try:
            ret = self.libvirt_qemu.qemuAgentCommand(
                self.domain, cmd_json, timeout, 0
            )
        except Exception as e:
            raise QgaCommandError(command, str(e)) from e

        LOG.debug(f"vm {self.vm_uuid} run qga command {cmd_json}")

        try:
            parsed = json.loads(ret)
        except ValueError as e:
            raise QgaReturnValueError(f"JSON parsing error: {ret}") from e

        if 'return' not in parsed:
            raise QgaReturnValueError(f"Missing 'return' in response: {ret}")

        result = parsed['return']
        if isinstance(result, dict):
            for key in ('out-data', 'err-data', 'buf-b64'):
                if key in result and isinstance(result[key], str):
                    result[key] = base64.b64decode(result[key])

        return result

    def _guest_info(self) -> dict[str, Any]:
        return self.call_qga_command("guest-info")

    def ping(self) -> Any:
        return self.call_qga_command("guest-ping")

    def is_agent_available(self) -> bool:
        try:
            ret = self.ping()
            return ret is not None or ret == {}
        except Exception:
            return False

    def _get_os_info_via_command(self) -> tuple[str, str]:
        ret = self.call_qga_command("guest-get-osinfo")
        if ret and "id" in ret and "version-id" in ret:
            vm_os = ret["id"].lower()
            version = ret["version-id"].lower().split(".")[0]
            return vm_os, version
        raise QgaReturnValueError(f"Failed to get OS info for vm {self.vm_uuid}")

    def _get_os_id_like(self) -> str | None:
        ret = self.exec_bash("cat /etc/os-release | grep ID_LIKE", raise_on_error=False)
        if ret:
            info = ret.split("=")
            return info[1].strip().strip('"') if len(info) > 1 else None
        return None

    def _get_os_info_via_file(self) -> tuple[str | None, str | None, str | None]:
        ret = self.exec_bash('cat /etc/os-release')
        if not ret:
            raise QgaReturnValueError("Failed to read /etc/os-release")

        config: dict[str, str] = {}
        for line in ret.split('\n'):
            if not line or line.startswith('#'):
                continue
            parts = line.split('=', 1)
            if len(parts) == 2:
                config[parts[0].strip()] = parts[1].strip().strip('"')

        vm_os = config.get('ID')
        version = config.get('VERSION_ID')
        if vm_os and version and vm_os == GuestOS.LINUX_UBUNTU:
            version = version.split(".")[0]

        return vm_os, version, config.get('ID_LIKE')

    def _exec_status(self, pid: int) -> dict[str, Any]:
        ret = self.call_qga_command("guest-exec-status", args={'pid': pid})
        if not ret or 'exited' not in ret:
            raise QgaReturnValueError("guest-exec-status returned invalid response")
        return ret

    def _exec(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.call_qga_command("guest-exec", args=args)

    def exec_bash(
        self,
        cmd: str,
        raise_on_error: bool = True,
        capture_output: bool = True,
        wait_interval: float = QGA_EXEC_WAIT_INTERVAL,
        max_retries: int = QGA_EXEC_WAIT_RETRY,
    ) -> str | None:
        ret = self._exec({
            "path": "bash",
            "arg": ["-c", cmd],
            "capture-output": capture_output,
        })
        if not ret or "pid" not in ret:
            raise QgaCommandError("guest-exec", f"No PID returned for cmd: {cmd}")

        pid = ret["pid"]
        if not capture_output:
            return None

        result = self._wait_for_exec(pid, wait_interval, max_retries)
        exit_code = result.get('exitcode', -1)
        output = result.get('out-data') or result.get('err-data')
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')

        if exit_code != 0:
            LOG.debug(f"qga exec command: {cmd}, exitcode {exit_code}, ret {output}")
            if raise_on_error:
                raise QgaCommandError("bash", f"exitcode={exit_code}, output={output}")
            return None

        return output

    def exec_powershell(
        self,
        cmd: str,
        raise_on_error: bool = True,
        capture_output: bool = True,
        wait_interval: float = QGA_EXEC_WAIT_INTERVAL,
        max_retries: int = QGA_EXEC_WAIT_RETRY,
    ) -> str | None:
        cmd_parts = cmd.split('|')
        formatted_cmd = "& '{}'".format("' '".join(cmd_parts))

        ret = self._exec({
            "path": "powershell.exe",
            "arg": ["-Command", formatted_cmd],
            "capture-output": capture_output,
        })
        if not ret or "pid" not in ret:
            raise QgaCommandError("guest-exec", f"No PID returned for cmd: {cmd}")

        pid = ret["pid"]
        if not capture_output:
            return None

        result = self._wait_for_exec(pid, wait_interval, max_retries)
        exit_code = result.get('exitcode', -1)
        output = result.get('out-data') or result.get('err-data')
        if isinstance(output, bytes):
            output = output.decode('GB2312', errors='replace')

        if exit_code != 0:
            if raise_on_error:
                raise QgaCommandError("powershell", f"exitcode={exit_code}, output={output}")
            return None

        return output

    def exec_command(
        self,
        cmd: str,
        raise_on_error: bool = True,
        capture_output: bool = True,
    ) -> str | None:
        if self.os and GuestOS.WINDOWS in self.os:
            return self.exec_powershell(cmd, raise_on_error, capture_output)
        return self.exec_bash(cmd, raise_on_error, capture_output)

    def exec_zs_tools(
        self,
        operate: str,
        config: str,
        capture_output: bool = True,
        wait_interval: float = QGA_EXEC_WAIT_INTERVAL,
        max_retries: int = ZS_TOOLS_WAIT_RETRY,
    ) -> tuple[int, str | None]:
        if operate == 'net':
            args = [operate, "--config", config]
        elif operate == 'host':
            args = [operate, "--name", config]
        else:
            raise ValueError(f"Unknown zs-tools operate: {operate}")

        ret = self._exec({
            "path": ZS_TOOLS_PATH_WIN,
            "arg": args,
            "capture-output": capture_output,
        })
        if not ret or "pid" not in ret:
            raise QgaCommandError(
                "guest-exec",
                f"zs-tools {operate} {config} failed"
            )

        pid = ret["pid"]
        result = self._wait_for_exec(pid, wait_interval, max_retries)

        exit_code = result.get('exitcode', -1)
        output = result.get('out-data') or result.get('err-data')
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace').replace('\r\n', '')

        return exit_code, output

    def _wait_for_exec(
        self,
        pid: int,
        wait_interval: float,
        max_retries: int,
    ) -> dict[str, Any]:
        for _ in range(max_retries):
            time.sleep(wait_interval)
            result = self._exec_status(pid)
            if result.get('exited'):
                return result

        raise QgaTimeoutError("guest-exec", int(wait_interval * max_retries))

    def file_open(self, path: str, create: bool = False) -> int:
        mode = "w+" if create else "r"
        return self.call_qga_command("guest-file-open", args={"path": path, "mode": mode})

    def file_close(self, handle: int) -> None:
        self.call_qga_command("guest-file-close", args={"handle": handle})

    def file_flush(self, handle: int) -> None:
        self.call_qga_command("guest-file-flush", args={"handle": handle})

    def file_read(self, path: str, raise_if_not_exists: bool = False) -> tuple[int, bytes | None]:
        try:
            handle = self.call_qga_command(
                "guest-file-open",
                args={"path": path, "mode": 'r'}
            )
        except Exception as e:
            if 'No such file' in str(e) and not raise_if_not_exists:
                return 0, None
            raise

        data = b''
        total_count = 0

        try:
            while True:
                ret = self.call_qga_command("guest-file-read", args={"handle": handle})
                chunk = ret.get('buf-b64', b'')
                if isinstance(chunk, str):
                    chunk = chunk.encode('utf-8')
                data += chunk
                count = ret.get('count', 0)
                total_count += count
                if count == 0:
                    break
        finally:
            self.file_close(handle)

        return total_count, data

    def file_exists(self, path: str) -> bool:
        try:
            handle = self.call_qga_command(
                "guest-file-open",
                args={"path": path, "mode": 'r'}
            )
            self.file_close(handle)
            return True
        except Exception as e:
            if 'No such file' in str(e):
                return False
            raise

    def file_write(self, path: str, contents: bytes) -> int:
        handle = self.file_open(path, create=True)
        try:
            ret = self.call_qga_command(
                "guest-file-write",
                args={"handle": handle, "buf-b64": contents}
            )
            return ret.get('count', 0)
        finally:
            self.file_close(handle)
