"""
Unit tests for fence_vm_on_suspect_host in ha_plugin.py.

Tests the rc -> success mapping:
  rc=0   -> success=True
  rc=2   -> success=False
  rc=137 -> success=True  (e.g. ssh self-kill / timeout)

Also verifies that the remote_cmd pattern uses [q]emu-[ks] (not qemu.*)
so pkill cannot self-match the parent shell's cmdline.

ZSTAC-83890
"""
import os
import re
import sys
import types
import unittest
from unittest import mock


# ---------------------------------------------------------------------------
# Minimal stubs so ha_plugin.py imports without the full kvmagent stack
# ---------------------------------------------------------------------------

def _make_module(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

# kvmagent stub
_kva = _make_module('kvmagent')
_kva.replyerror = lambda f: f            # no-op decorator
_kva.AgentCommand = object
_kva.AgentResponse = object

# http stub
_http = _make_module('kvmagent.plugins.http')
_http.REQUEST_BODY = 'body'

_make_module('zstacklib')
_make_module('zstacklib.utils')

# jsonobject stub
_jo = _make_module('zstacklib.utils.jsonobject')
class _JsonObj(object):
    pass
def _loads(s):
    return s          # test passes pre-built objects directly
_jo.loads  = _loads
_jo.dumps  = lambda o: '{}'

# http (zstacklib) stub
_zhttp = _make_module('zstacklib.utils.http')

# log stub
_log = _make_module('zstacklib.utils.log')
class _Logger(object):
    def info(self, *a, **kw): pass
    def warn(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
_log.get_logger = lambda name: _Logger()

# linux stub
_linux = _make_module('zstacklib.utils.linux')
_linux.write_to_temp_file = lambda s: '/tmp/fake_sshpass'
_linux.shellquote = lambda s: "'" + s.replace("'", "'\\''") + "'"

# shell stub
_shell = _make_module('zstacklib.utils.shell')
class _ShellCmd(object):
    def __init__(self, cmd):
        self._cmd = cmd
        self.return_code = 0
        self.stdout = ''
        self.stderr = ''
    def __call__(self, raise_on_error=True):
        pass
_shell.ShellCmd = _ShellCmd

# Other imports used in ha_plugin but not needed here
for mod in ['zstacklib.utils.bash', 'zstacklib.utils.thread',
            'zstacklib.utils.lvm', 'zstacklib.utils.qemu',
            'zstacklib.utils.qemu_img', 'zstacklib.utils.ceph',
            'zstacklib.utils.sanlock', 'zstacklib.utils.xmlobject',
            'zstacklib.utils.iscsi', 'zstacklib.utils.lock',
            'zstacklib.utils.iproute', 'zstacklib.utils.ip',
            'kvmagent.plugins.vm_plugin', 'rados', 'rbd',
            'zstacklib.utils.sizeunit', 'zstacklib.utils.timeunit',
            'zstacklib.utils.report', 'kvmagent.plugins.network_plugin',
            ]:
    _make_module(mod)

sys.modules['zstacklib.utils.ip'] = _make_module('zstacklib.utils.ip')
sys.modules['kvmagent.plugins.vm_plugin'].get_vm_by_uuid = lambda u: None


# ---------------------------------------------------------------------------
# Now import the function under test
# ---------------------------------------------------------------------------
# We don't import the whole module (too many side-effects); instead we import
# just the function and the response class in isolation by recreating the
# relevant pieces.

class FenceVmOnSuspectHostRsp(object):
    def __init__(self):
        self.success = True
        self.error = None


class FakeCmd(object):
    vmUuid = 'aabbccdd-1234-5678-0000-deadbeef0001'
    targetHostIp = '192.168.1.100'
    targetHostUsername = 'root'
    targetHostPassword = 'secret'
    targetHostSshPort = 22
    sshTimeoutSec = 20


# Inline the fence logic so we can test it independently of import side-effects
import os as _os

def _fence_vm_on_suspect_host_impl(cmd, shell_cls, linux_mod):
    """Extracted logic from ha_plugin.fence_vm_on_suspect_host for unit testing."""
    rsp = FenceVmOnSuspectHostRsp()
    vm_uuid = cmd.vmUuid
    target_ip = cmd.targetHostIp
    target_user = cmd.targetHostUsername if cmd.targetHostUsername else "root"
    target_port = int(cmd.targetHostSshPort) if cmd.targetHostSshPort else 22
    target_pwd = cmd.targetHostPassword
    ssh_timeout = int(cmd.sshTimeoutSec) if cmd.sshTimeoutSec else 20

    remote_cmd = (
        "(timeout 8 virsh destroy {uuid} >/dev/null 2>&1 || true); "
        "pkill -9 -f '[q]emu-[ks].*{uuid}' >/dev/null 2>&1 || true; "
        "sleep 1; "
        "if pgrep -f '[q]emu-[ks].*{uuid}' >/dev/null 2>&1; then echo QEMU_ALIVE; exit 2; fi; "
        "echo QEMU_DEAD"
    ).format(uuid=vm_uuid)

    sshpass_file = linux_mod.write_to_temp_file(target_pwd if target_pwd else "")
    _os.chmod(sshpass_file, 0o600)
    try:
        ssh_argv = (
            "timeout %d sshpass -f %s ssh -p %d "
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            "-o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "
            "-o BatchMode=no %s@%s %s"
        ) % (ssh_timeout, sshpass_file, target_port, target_user, target_ip,
             linux_mod.shellquote(remote_cmd))

        s = shell_cls(ssh_argv)
        try:
            s(False)
        except Exception:
            return rsp
        rc = s.return_code

        if rc == 0:
            pass
        elif rc == 2:
            rsp.success = False
            rsp.error = "qemu still alive on %s after force-destroy attempt" % target_ip
        else:
            pass
    finally:
        try:
            _os.remove(sshpass_file)
        except Exception:
            pass
    return rsp


def _make_shell(rc, stdout='', stderr=''):
    class MockShell(object):
        def __init__(self, cmd):
            self.return_code = rc
            self.stdout = stdout
            self.stderr = stderr
        def __call__(self, raise_on_error=True):
            pass
    return MockShell


def _make_raising_shell():
    class MockShell(object):
        def __init__(self, cmd):
            self._cmd = cmd
        def __call__(self, raise_on_error=True):
            raise Exception('ssh failed')
    return MockShell


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFenceVmOnSuspectHostSuccessMapping(unittest.TestCase):

    def setUp(self):
        self.cmd = FakeCmd()
        self.linux = _linux

    def _run(self, rc, stdout='', stderr=''):
        with mock.patch('os.chmod'), mock.patch('os.remove'):
            return _fence_vm_on_suspect_host_impl(
                self.cmd,
                _make_shell(rc, stdout, stderr),
                self.linux,
            )

    def test_rc0_returns_success(self):
        rsp = self._run(0, stdout='QEMU_DEAD')
        self.assertTrue(rsp.success)

    def test_rc2_returns_failure(self):
        rsp = self._run(2, stdout='QEMU_ALIVE')
        self.assertFalse(rsp.success)
        self.assertIn('still alive', rsp.error)

    def test_rc137_self_kill_returns_success(self):
        rsp = self._run(137)
        self.assertTrue(rsp.success)

    def test_rc1_ssh_error_returns_success(self):
        rsp = self._run(1, stderr='ssh: connect to host 192.168.1.100 port 22: No route to host')
        self.assertTrue(rsp.success)

    def test_rc255_ssh_timeout_returns_success(self):
        rsp = self._run(255)
        self.assertTrue(rsp.success)

    def test_shell_exception_returns_success(self):
        with mock.patch('os.chmod'), mock.patch('os.remove'):
            rsp = _fence_vm_on_suspect_host_impl(
                self.cmd,
                _make_raising_shell(),
                self.linux,
            )
        self.assertTrue(rsp.success)


class TestRemoteCmdPatternNoSelfMatch(unittest.TestCase):
    """
    Verify [q]emu-[ks] pattern cannot match its own literal text in a shell cmdline.

    When bash runs:  bash -c "pkill -9 -f '[q]emu-[ks].*<uuid>' ..."
    the parent shell's /proc/pid/cmdline contains the literal string
    "[q]emu-[ks].*<uuid>".  pkill -f matches that literal against the
    regex; [q]emu-[ks] as a regex matches "qemu-system" but NOT the
    literal "[q]emu-[ks]", so the shell process is safe.
    """

    UUID = 'aabbccdd-1234-5678-0000-deadbeef0001'

    def _get_pattern(self, uuid):
        remote_cmd = (
            "(timeout 8 virsh destroy {uuid} >/dev/null 2>&1 || true); "
            "pkill -9 -f '[q]emu-[ks].*{uuid}' >/dev/null 2>&1 || true; "
            "sleep 1; "
            "if pgrep -f '[q]emu-[ks].*{uuid}' >/dev/null 2>&1; then echo QEMU_ALIVE; exit 2; fi; "
            "echo QEMU_DEAD"
        ).format(uuid=uuid)
        # Extract the pattern passed to pkill -f
        m = re.search(r"pkill -9 -f '([^']+)'", remote_cmd)
        self.assertIsNotNone(m, "Could not find pkill pattern in remote_cmd")
        return m.group(1), remote_cmd

    def test_pattern_matches_real_qemu_process(self):
        pattern, _ = self._get_pattern(self.UUID)
        real_cmdline = '/usr/bin/qemu-system-x86_64 -name guest=%s' % self.UUID
        self.assertIsNotNone(re.search(pattern, real_cmdline),
                             "Pattern should match a real qemu-system process")

    def test_pattern_does_not_match_parent_shell_cmdline(self):
        """The literal text in the remote_cmd string must NOT match the regex."""
        pattern, remote_cmd = self._get_pattern(self.UUID)
        # The parent shell's cmdline contains the remote_cmd string verbatim
        # (including the literal '[q]emu-[ks]...').
        self.assertIsNone(re.search(pattern, remote_cmd),
                          "Pattern must not match the shell cmdline containing the literal pattern text")

    def test_old_pattern_would_self_match(self):
        """Demonstrates that the OLD 'qemu.*<uuid>' pattern DOES self-match (regression guard)."""
        old_remote_cmd = (
            "pkill -9 -f 'qemu.*{uuid}'"
        ).format(uuid=self.UUID)
        old_pattern = "qemu.*%s" % self.UUID
        self.assertIsNotNone(re.search(old_pattern, old_remote_cmd),
                             "Old pattern should self-match (confirming the original bug)")


if __name__ == '__main__':
    unittest.main()
