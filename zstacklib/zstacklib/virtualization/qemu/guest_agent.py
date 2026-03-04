# Copyright (c) ZStack.io, Inc.

"""
QEMU Guest Agent (QGA) interface.

Provides the VmQga class for communicating with QEMU Guest Agent
running inside virtual machines.
"""

import base64
import json
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import (
    QgaException,
    QgaNotRunningError,
    QgaCommandError,
    QgaCommandDisabledError,
    QgaCommandNotSupportedError,
)
from .models import (
    QGA_STATE_RUNNING,
    QGA_STATE_NOT_RUNNING,
    QGA_CHANNEL_STATE_CONNECTED,
    QGA_EXEC_WAIT_INTERVAL,
    QGA_EXEC_WAIT_RETRY,
    ZS_TOOLS_WAIT_RETRY,
    ZS_TOOLS_PATH_WIN,
    VM_OS_WINDOWS,
    VM_OS_LINUX_UBUNTU,
)


logger = logging.getLogger(__name__)


def get_qga_channel_state(vm_dom):
    # type: (Any) -> Optional[str]
    """Get the QGA channel state from VM domain XML.
    
    Args:
        vm_dom: libvirt domain object.
        
    Returns:
        Channel state string ('connected' or 'disconnected'), or None if not found.
    """
    xml_tree = ET.fromstring(vm_dom.XMLDesc())
    channel = xml_tree.find("./devices/channel/target[@name='org.qemu.guest_agent.0']")
    if channel is not None:
        return channel.get('state')
    return None


def is_qga_connected(vm_dom):
    # type: (Any) -> bool
    """Check if QGA is connected to the VM.
    
    Args:
        vm_dom: libvirt domain object.
        
    Returns:
        True if QGA channel is connected, False otherwise.
    """
    try:
        return get_qga_channel_state(vm_dom) == QGA_CHANNEL_STATE_CONNECTED
    except Exception:
        return False


class VmQga(object):
    """QEMU Guest Agent interface for a virtual machine.
    
    Provides methods to execute commands and manage files inside
    a virtual machine through the QEMU Guest Agent.
    
    Attributes:
        domain: libvirt domain object.
        vm_uuid: UUID of the virtual machine.
        state: QGA state (Running or NotRunning).
        version: QGA version string.
        supported_commands: Dict of command name to enabled status.
        os: Guest operating system ID.
        os_version: Guest OS version.
        os_id_like: ID_LIKE field from /etc/os-release.
    """

    def __init__(self, domain):
        # type: (Any) -> None
        """Initialize VmQga for a domain.
        
        Args:
            domain: libvirt domain object.
        """
        self.domain = domain
        self.vm_uuid = domain.name()
        self.state = QGA_STATE_NOT_RUNNING
        self.version = None  # type: Optional[str]
        self.supported_commands = {}  # type: Dict[str, bool]
        self.os = None  # type: Optional[str]
        self.os_version = None  # type: Optional[str]
        self.os_id_like = None  # type: Optional[str]
        self._qga_init()

    def _qga_init(self):
        # type: () -> None
        """Initialize QGA state and capabilities."""
        self.state = QGA_STATE_NOT_RUNNING
        
        if not is_qga_connected(self.domain):
            return
        
        if self.domain.isActive() and self.guest_agent_available():
            self.state = QGA_STATE_RUNNING
        else:
            return
        
        # Get QGA info
        ret = self.guest_info()
        if ret:
            self.version = ret.get('version')
            supported_commands = ret.get('supported_commands', [])
            self.supported_commands = {
                cmd['name']: cmd['enabled'] for cmd in supported_commands
            }
        
        # Get OS info
        try:
            if self.supports_command('guest-get-osinfo'):
                self.os, self.os_version = self._guest_exec_get_os_info()
                if self.os == VM_OS_WINDOWS:
                    self.os_id_like = 'windows'
                else:
                    self.os_id_like = self._guest_get_os_id_like()
            else:
                self.os, self.os_version, self.os_id_like = self._guest_get_os_info()
        except Exception as e:
            logger.debug('QGA init failed: %s', e)

    def is_running(self):
        # type: () -> bool
        """Check if QGA is running."""
        return self.state == QGA_STATE_RUNNING

    def is_windows(self):
        # type: () -> bool
        """Check if guest OS is Windows."""
        return self.os is not None and VM_OS_WINDOWS in self.os

    def supports_command(self, command):
        # type: (str) -> bool
        """Check if a command is supported and enabled."""
        return self.supported_commands.get(command, False)

    def call_qga_command(self, command, args=None, timeout=3):
        # type: (str, Optional[Dict], int) -> Any
        """Execute a QEMU-GA command.
        
        Args:
            command: The command to execute.
            args: Arguments to the command.
            timeout: Timeout in seconds.
            
        Returns:
            Command result as dict.
            
        Raises:
            QgaCommandNotSupportedError: If command is not supported.
            QgaCommandDisabledError: If command is disabled.
            QgaCommandError: If command execution fails.
        """
        import libvirt
        import libvirt_qemu
        
        # Check if command is supported
        if self.supported_commands:
            if command not in self.supported_commands:
                raise QgaCommandNotSupportedError(
                    command, self.version or 'unknown', self.vm_uuid
                )
            if not self.supported_commands[command]:
                raise QgaCommandDisabledError(command, self.vm_uuid)
        
        # Build command
        cmd = {'execute': command}
        if args:
            # Encode binary data
            if 'buf-b64' in args:
                args['buf-b64'] = base64.b64encode(args['buf-b64'].encode() 
                    if isinstance(args['buf-b64'], str) else args['buf-b64']).decode()
            cmd['arguments'] = args
        
        cmd_str = json.dumps(cmd)
        
        try:
            ret = libvirt_qemu.qemuAgentCommand(self.domain, cmd_str, timeout, 0)
        except libvirt.libvirtError as e:
            raise QgaCommandError(
                command, self.vm_uuid,
                'exec QGA command [{}] error: {}'.format(cmd_str, str(e))
            )
        
        logger.debug('VM %s run QGA command %s', self.vm_uuid, cmd_str)
        
        try:
            parsed = json.loads(ret)
        except ValueError:
            raise QgaCommandError(
                command, self.vm_uuid,
                'QGA command return value parsing error: {}'.format(ret)
            )
        
        if 'return' not in parsed:
            raise QgaCommandError(
                command, self.vm_uuid,
                'QGA command return value format error: {}'.format(ret)
            )
        
        parsed_ret = parsed['return']
        
        # Decode binary data
        if isinstance(parsed_ret, dict):
            for key in ['out-data', 'err-data', 'buf-b64']:
                if key in parsed_ret:
                    parsed_ret[key] = base64.b64decode(parsed_ret[key])
        
        return parsed_ret

    # =========================================================================
    # Basic QGA commands
    # =========================================================================

    def guest_info(self):
        # type: () -> Dict
        """Get QGA information including version and supported commands."""
        return self.call_qga_command('guest-info')

    def guest_ping(self):
        # type: () -> Dict
        """Ping the guest agent."""
        return self.call_qga_command('guest-ping')

    def guest_agent_available(self):
        # type: () -> bool
        """Check if guest agent is available and responding."""
        try:
            ret = self.guest_ping()
            return ret is not None
        except Exception:
            return False

    def guest_exec_status(self, pid):
        # type: (int) -> Dict
        """Get the status of an executed command.
        
        Args:
            pid: Process ID from guest-exec.
            
        Returns:
            Dict with 'exited', 'exitcode', 'out-data', 'err-data'.
        """
        ret = self.call_qga_command('guest-exec-status', args={'pid': pid})
        if not ret or 'exited' not in ret:
            raise QgaCommandError(
                'guest-exec-status', self.vm_uuid, 'guest-exec-status exception'
            )
        return ret

    def guest_exec(self, args):
        # type: (Dict) -> Dict
        """Execute a command in the guest.
        
        Args:
            args: Dict with 'path', 'arg', 'capture-output', etc.
            
        Returns:
            Dict with 'pid'.
        """
        return self.call_qga_command('guest-exec', args=args)

    # =========================================================================
    # Shell execution helpers
    # =========================================================================

    def guest_exec_bash(self, cmd, output=True, 
                        wait=QGA_EXEC_WAIT_INTERVAL, 
                        retry=QGA_EXEC_WAIT_RETRY):
        # type: (str, bool, int, int) -> Tuple[int, Optional[bytes]]
        """Execute a bash command in the guest.
        
        Args:
            cmd: Command string to execute.
            output: Whether to capture output.
            wait: Seconds between status checks.
            retry: Maximum number of retries.
            
        Returns:
            Tuple of (exit_code, output_data).
        """
        ret = self.guest_exec({
            'path': 'bash',
            'arg': ['-c', cmd],
            'capture-output': output
        })
        
        if not ret or 'pid' not in ret:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec cmd {} failed'.format(cmd)
            )
        
        pid = ret['pid']
        
        if not output:
            logger.debug('Run QGA bash: %s (no output)', cmd)
            return 0, None
        
        # Wait for completion
        result = None
        for _ in range(retry):
            time.sleep(wait)
            result = self.guest_exec_status(pid)
            if result.get('exited'):
                break
        
        if not result or not result.get('exited'):
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec cmd {} timeout'.format(cmd)
            )
        
        exit_code = result.get('exitcode', 0)
        ret_data = result.get('out-data') or result.get('err-data')
        
        return exit_code, ret_data

    def guest_exec_bash_no_exitcode(self, cmd, exception=True, output=True):
        # type: (str, bool, bool) -> Optional[bytes]
        """Execute bash command and return output only.
        
        Args:
            cmd: Command to execute.
            exception: Whether to raise exception on non-zero exit.
            output: Whether to capture output.
            
        Returns:
            Output data or None.
        """
        exitcode, ret_data = self.guest_exec_bash(cmd, output)
        if exitcode != 0:
            logger.debug('QGA exec command: %s, exitcode %d, ret %s', 
                        cmd, exitcode, ret_data)
            if exception:
                raise QgaCommandError(
                    'guest-exec', self.vm_uuid,
                    'cmd {}, exitcode {}, ret {}'.format(cmd, exitcode, ret_data)
                )
            return None
        return ret_data

    def guest_exec_powershell(self, cmd, output=True,
                              wait=QGA_EXEC_WAIT_INTERVAL,
                              retry=QGA_EXEC_WAIT_RETRY):
        # type: (str, bool, int, int) -> Tuple[int, Optional[str]]
        """Execute a PowerShell command in Windows guest.
        
        Args:
            cmd: PowerShell command string.
            output: Whether to capture output.
            wait: Seconds between status checks.
            retry: Maximum number of retries.
            
        Returns:
            Tuple of (exit_code, output_string).
        """
        # Format command for PowerShell
        cmd_parts = cmd.split('|')
        formatted_cmd = "& '{}'".format("' '".join(part for part in cmd_parts))
        
        ret = self.guest_exec({
            'path': 'powershell.exe',
            'arg': ['-Command', formatted_cmd],
            'capture-output': output
        })
        
        if not ret or 'pid' not in ret:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec cmd {} failed'.format(cmd)
            )
        
        pid = ret['pid']
        
        if not output:
            logger.debug('Run QGA PowerShell: %s (no output)', cmd)
            return 0, None
        
        # Wait for completion
        result = None
        for _ in range(retry):
            time.sleep(wait)
            result = self.guest_exec_status(pid)
            if result.get('exited'):
                break
        
        if not result or not result.get('exited'):
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec cmd {} timeout'.format(cmd)
            )
        
        exit_code = result.get('exitcode', 0)
        ret_data = None
        
        if 'out-data' in result:
            ret_data = result['out-data'].decode('GB2312', errors='replace')
        elif 'err-data' in result:
            ret_data = result['err-data'].decode('GB2312', errors='replace')
        
        return exit_code, ret_data

    def guest_exec_powershell_no_exitcode(self, cmd, exception=True, output=True):
        # type: (str, bool, bool) -> Optional[str]
        """Execute PowerShell command and return output only."""
        exitcode, ret_data = self.guest_exec_powershell(cmd, output)
        if exitcode != 0:
            if exception:
                raise QgaCommandError(
                    'guest-exec', self.vm_uuid,
                    'cmd {}, exitcode {}, ret {}'.format(cmd, exitcode, ret_data)
                )
            return None
        return ret_data

    def guest_exec_cmd_no_exitcode(self, cmd, exception=True, output=True):
        # type: (str, bool, bool) -> Optional[Any]
        """Execute command using appropriate shell for the OS."""
        if self.is_windows():
            return self.guest_exec_powershell_no_exitcode(cmd, exception, output)
        else:
            return self.guest_exec_bash_no_exitcode(cmd, exception, output)

    def guest_exec_python(self, file, params=None, output=True,
                          wait=QGA_EXEC_WAIT_INTERVAL,
                          retry=QGA_EXEC_WAIT_RETRY):
        # type: (str, Optional[List[str]], bool, int, int) -> Tuple[int, Optional[bytes]]
        """Execute a Python script in the guest.
        
        Args:
            file: Path to the Python script.
            params: List of parameters to pass.
            output: Whether to capture output.
            wait: Seconds between status checks.
            retry: Maximum number of retries.
            
        Returns:
            Tuple of (exit_code, output_data).
        """
        # Find Python interpreter
        path = self.guest_exec_bash_no_exitcode('which python2', exception=False)
        if not path:
            path = self.guest_exec_bash_no_exitcode('which python3', exception=False)
        
        if not path:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'Python not installed in VM'
            )
        
        args = [file]
        if params:
            args.extend(params)
        
        ret = self.guest_exec({
            'path': path.decode().strip() if isinstance(path, bytes) else path.strip(),
            'arg': args,
            'capture-output': output
        })
        
        if not ret or 'pid' not in ret:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec Python {} failed'.format(file)
            )
        
        pid = ret['pid']
        
        if not output:
            return 0, None
        
        # Wait for completion
        result = None
        for _ in range(retry):
            time.sleep(wait)
            result = self.guest_exec_status(pid)
            if result.get('exited'):
                break
        
        if not result or not result.get('exited'):
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec Python {} timeout'.format(file)
            )
        
        exit_code = result.get('exitcode', 0)
        ret_data = result.get('out-data') or result.get('err-data')
        
        return exit_code, ret_data

    def guest_exec_zs_tools(self, operate, config, output=True,
                            wait=QGA_EXEC_WAIT_INTERVAL,
                            retry=ZS_TOOLS_WAIT_RETRY):
        # type: (str, str, bool, int, int) -> Tuple[int, Optional[str]]
        """Execute ZStack tools on Windows guest.
        
        Args:
            operate: Operation type ('net' or 'host').
            config: Configuration string.
            output: Whether to capture output.
            wait: Seconds between status checks.
            retry: Maximum number of retries.
            
        Returns:
            Tuple of (exit_code, output_string).
        """
        if operate == 'net':
            args = [operate, '--config', config]
        elif operate == 'host':
            args = [operate, '--name', config]
        else:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'Unknown zs-tools operate: {}'.format(operate)
            )
        
        ret = self.guest_exec({
            'path': ZS_TOOLS_PATH_WIN,
            'arg': args,
            'capture-output': output
        })
        
        if not ret or 'pid' not in ret:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec zs-tools {} {} failed'.format(operate, config)
            )
        
        pid = ret['pid']
        
        # Wait for completion
        result = None
        for _ in range(retry):
            time.sleep(wait)
            result = self.guest_exec_status(pid)
            if result.get('exited'):
                break
        
        if not result or not result.get('exited'):
            raise QgaCommandError(
                'guest-exec', self.vm_uuid,
                'QGA exec zs-tools {} {} timeout'.format(operate, config)
            )
        
        exit_code = result.get('exitcode', 0)
        ret_data = None
        
        if 'out-data' in result:
            ret_data = result['out-data'].decode('utf-8', errors='replace').replace('\r\n', '')
        elif 'err-data' in result:
            ret_data = result['err-data'].decode('utf-8', errors='replace').replace('\r\n', '')
        
        return exit_code, ret_data

    # =========================================================================
    # OS information
    # =========================================================================

    def _guest_exec_get_os_info(self):
        # type: () -> Tuple[str, str]
        """Get OS info using guest-get-osinfo command."""
        ret = self.call_qga_command('guest-get-osinfo')
        if ret and 'id' in ret and 'version-id' in ret:
            vm_os = ret['id'].lower()
            version = ret['version-id'].lower().split('.')[0]
            return vm_os, version
        raise QgaCommandError(
            'guest-get-osinfo', self.vm_uuid, 'Get VM OS info failed'
        )

    def _guest_get_os_id_like(self):
        # type: () -> Optional[str]
        """Get ID_LIKE from /etc/os-release."""
        ret = self.guest_exec_bash_no_exitcode(
            'cat /etc/os-release | grep ID_LIKE', exception=False
        )
        if ret:
            decoded = ret.decode() if isinstance(ret, bytes) else ret
            info = decoded.split('=')
            return info[1].strip().strip('"') if len(info) > 1 else None
        return None

    def _guest_get_os_info(self):
        # type: () -> Tuple[Optional[str], Optional[str], Optional[str]]
        """Get OS info from /etc/os-release file."""
        ret = self.guest_exec_bash_no_exitcode('cat /etc/os-release')
        if not ret:
            raise QgaCommandError(
                'guest-exec', self.vm_uuid, 'Get OS info failed'
            )
        
        decoded = ret.decode() if isinstance(ret, bytes) else ret
        lines = [line for line in decoded.split('\n') if line]
        config = {}
        
        for line in lines:
            if line.startswith('#'):
                continue
            info = line.split('=')
            if len(info) == 2:
                config[info[0].strip()] = info[1].strip().strip('"')
        
        vm_os = config.get('ID')
        version = config.get('VERSION_ID')
        
        if vm_os and version and vm_os == VM_OS_LINUX_UBUNTU:
            version = version.split('.')[0]
        
        return vm_os, version, config.get('ID_LIKE')

    # =========================================================================
    # File operations
    # =========================================================================

    def guest_file_open(self, path, create=False):
        # type: (str, bool) -> int
        """Open a file in the guest.
        
        Args:
            path: File path.
            create: Whether to create the file.
            
        Returns:
            File handle.
        """
        mode = 'w+' if create else 'r'
        return self.call_qga_command('guest-file-open', args={'path': path, 'mode': mode})

    def guest_file_close(self, handle):
        # type: (int) -> None
        """Close a file handle."""
        self.call_qga_command('guest-file-close', args={'handle': handle})

    def guest_file_flush(self, handle):
        # type: (int) -> None
        """Flush a file handle."""
        self.call_qga_command('guest-file-flush', args={'handle': handle})

    def guest_file_read(self, path, not_exist_exception=False):
        # type: (str, bool) -> Tuple[int, Optional[bytes]]
        """Read a file from the guest.
        
        Args:
            path: File path.
            not_exist_exception: Whether to raise exception if file doesn't exist.
            
        Returns:
            Tuple of (total_bytes, file_contents).
        """
        try:
            handle = self.call_qga_command(
                'guest-file-open', args={'path': path, 'mode': 'r'}
            )
        except Exception as e:
            if 'No such file' in str(e) and not not_exist_exception:
                return 0, None
            raise
        
        data_parts = []
        total_count = 0
        
        try:
            while True:
                ret = self.call_qga_command('guest-file-read', args={'handle': handle})
                if ret.get('buf-b64'):
                    data_parts.append(ret['buf-b64'])
                total_count += ret.get('count', 0)
                if ret.get('count', 0) == 0:
                    break
        finally:
            self.guest_file_close(handle)
        
        return total_count, b''.join(data_parts) if data_parts else None

    def guest_file_is_exist(self, path):
        # type: (str) -> bool
        """Check if a file exists in the guest."""
        try:
            handle = self.call_qga_command(
                'guest-file-open', args={'path': path, 'mode': 'r'}
            )
        except Exception as e:
            if 'No such file' in str(e):
                return False
            raise
        
        self.guest_file_close(handle)
        return True

    def guest_file_write(self, path, contents):
        # type: (str, bytes) -> int
        """Write contents to a file in the guest.
        
        Args:
            path: File path.
            contents: File contents as bytes.
            
        Returns:
            Number of bytes written.
        """
        handle = self.guest_file_open(path, create=True)
        try:
            ret = self.call_qga_command(
                'guest-file-write', args={'handle': handle, 'buf-b64': contents}
            )
        finally:
            self.guest_file_close(handle)
        
        return ret.get('count', 0)
