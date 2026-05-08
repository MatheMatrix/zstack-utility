# -*- coding: utf-8 -*-
"""Unit tests for HaPlugin.sibling_fence_vm (ZSTAC-83890 / ZSTAC-83890).

Two layers of coverage:

1. ``TestSiblingFenceProbe``: drives a self-contained mirror of the production
   decision tree (``_SiblingFenceProbe.probe``) with a mocked ssh runner. We
   keep this in sync with ha_plugin.py and rely on layer 2 to catch drift —
   importing ha_plugin directly pulls in rados/rbd/etc. which are not present
   in the unit-test environment, hence the same ``standalone copy`` pattern
   used by test_ha_fencer.py for VmStruct.

2. ``TestSiblingFenceSourceInvariants``: parses ha_plugin.py and asserts the
   safety invariants that the P0 fix locked in. Catches anyone re-introducing
   ``rsp.alive = False`` as the default — which is the exact regression that
   would re-open the split-brain we just closed.
"""
import ast
import os
import re
import unittest


# ============================================================
# Layer 1: standalone mirror of sibling_fence_vm decision logic
# ============================================================
_UUID_RE = re.compile(r'^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
_IPV4_RE = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')
_IPV6_RE = re.compile(r'^[0-9a-fA-F:]+$')


class _Cmd(object):
    """Stand-in for jsonobject-loaded request; only attribute access is used."""
    def __init__(self, vmUuid=None, failedHostIp=None, failedHostSshPort=22,
                 failedHostUuid=None):
        self.vmUuid = vmUuid
        self.failedHostIp = failedHostIp
        self.failedHostSshPort = failedHostSshPort
        self.failedHostUuid = failedHostUuid


class _Rsp(object):
    """Stand-in for AgentRsp."""
    def __init__(self):
        self.alive = True
        self.killed = False
        self.sshReachable = False
        self.qemuFound = False
        self.executorHostUuid = ""
        self.executorRole = "sibling"
        self.reason = ""


class _SiblingFenceProbe(object):
    """Mirror of HaPlugin.sibling_fence_vm — keep behaviour-identical to
    kvmagent/kvmagent/plugins/ha_plugin.py:sibling_fence_vm. The TestSiblingFenceSourceInvariants
    suite below cross-checks key invariants against the real source so drift
    is caught at test time."""

    @staticmethod
    def probe(cmd, executor_host_uuid, ssh_runner):
        rsp = _Rsp()
        rsp.alive = True   # conservative default — P0 fix
        rsp.executorHostUuid = executor_host_uuid

        vm_uuid = cmd.vmUuid
        host_ip = cmd.failedHostIp
        try:
            ssh_port = int(cmd.failedHostSshPort) if cmd.failedHostSshPort else 22
        except (TypeError, ValueError):
            rsp.reason = "invalid failedHostSshPort"
            return rsp

        if not vm_uuid or not host_ip:
            rsp.reason = "missing vmUuid or failedHostIp"
            return rsp

        if not _UUID_RE.match(vm_uuid):
            rsp.reason = "invalid vmUuid format"
            return rsp

        if not (_IPV4_RE.match(host_ip) or _IPV6_RE.match(host_ip)):
            rsp.reason = "invalid failedHostIp format"
            return rsp

        if ssh_port < 1 or ssh_port > 65535:
            rsp.reason = "ssh port out of range"
            return rsp

        # (a) connectivity probe
        ret, _, ssh_err = ssh_runner("true", 8)
        if ret == 255:
            rsp.alive = True
            rsp.reason = "ssh layer failure (rc=255)"
            return rsp
        if ret != 0:
            rsp.alive = False                 # explicit positive evidence
            rsp.reason = "ssh probe timed out (rc=%s)" % ret
            return rsp

        rsp.sshReachable = True

        # (b) is the vm there?
        ret, out, _ = ssh_runner("virsh list --uuid", 10)
        if ret != 0:
            rsp.alive = True
            rsp.reason = "virsh list failed"
            return rsp

        running = [line.strip() for line in (out or "").splitlines() if line.strip()]
        if vm_uuid not in running:
            rsp.alive = False                 # explicit positive evidence
            rsp.qemuFound = False
            rsp.reason = "vm not found on failed host"
            return rsp

        rsp.qemuFound = True

        # (c) destroy + pkill, recheck
        ssh_runner("virsh destroy %s" % vm_uuid, 15)
        ssh_runner('pkill -9 -f "guest=%s"' % vm_uuid, 10)

        ret2, out2, _ = ssh_runner("virsh list --uuid", 10)
        if ret2 != 0:
            rsp.alive = True
            rsp.killed = False
            rsp.reason = "post-kill virsh list failed"
            return rsp

        running2 = [line.strip() for line in (out2 or "").splitlines() if line.strip()]
        if vm_uuid in running2:
            rsp.alive = True
            rsp.killed = False
            rsp.reason = "destroy + kill -9 both failed"
        else:
            rsp.alive = False
            rsp.killed = True
            rsp.reason = "killed via virsh destroy + pkill"
        return rsp


# ============================================================
# Layer 1 tests: behavioural coverage via the mirror
# ============================================================
VALID_VM = "11112222333344445555666677778888"
VALID_IP = "10.0.0.5"


class _ScriptedSshRunner(object):
    """Returns scripted (rc, out, err) tuples per call. Matches by remote_cmd
    substring; falls back to a default when nothing matches."""
    def __init__(self, scripts, default=(0, "", "")):
        # scripts: list of (substr_match, (rc, out, err))
        self.scripts = list(scripts)
        self.default = default
        self.calls = []

    def __call__(self, remote_cmd, timeout):
        self.calls.append((remote_cmd, timeout))
        for substr, result in self.scripts:
            if substr in remote_cmd:
                return result
        return self.default


class TestSiblingFenceProbe(unittest.TestCase):

    # --- input validation: all must keep alive=True (conservative default) ---

    def test_missing_vm_uuid_keeps_alive_true(self):
        cmd = _Cmd(vmUuid=None, failedHostIp=VALID_IP)
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive,
            "missing vmUuid must NOT signal host-dead — would re-open split-brain")
        self.assertFalse(rsp.killed)
        self.assertIn("missing", rsp.reason)

    def test_missing_host_ip_keeps_alive_true(self):
        # This is the exact P0 scenario: cmd arrived without failedHostIp.
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=None)
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive,
            "P0 regression guard: missing failedHostIp must NOT yield alive=false")
        self.assertFalse(rsp.killed)
        self.assertFalse(rsp.sshReachable)

    def test_invalid_vm_uuid_keeps_alive_true(self):
        cmd = _Cmd(vmUuid="not; a uuid", failedHostIp=VALID_IP)
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive)
        self.assertIn("invalid vmUuid", rsp.reason)

    def test_invalid_host_ip_keeps_alive_true(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp="example.com; rm -rf /")
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive)
        self.assertIn("invalid failedHostIp", rsp.reason)

    def test_invalid_ssh_port_keeps_alive_true(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP, failedHostSshPort=70000)
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive)
        self.assertIn("port out of range", rsp.reason)

    def test_unparseable_ssh_port_keeps_alive_true(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP, failedHostSshPort="abc")
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", _ScriptedSshRunner([]))
        self.assertTrue(rsp.alive)
        self.assertIn("invalid failedHostSshPort", rsp.reason)

    # --- ssh probe semantics ---

    def test_ssh_rc_255_refuses_fence_alive_true(self):
        """ssh-layer failure (auth/host-key/network) is ambiguous — must NOT
        be treated as host-dead, otherwise a misconfigured sibling could
        unlock VM recreation while old qemu is alive."""
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)
        ssh = _ScriptedSshRunner([("true", (255, "", "Permission denied"))])
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", ssh)
        self.assertTrue(rsp.alive)
        self.assertFalse(rsp.sshReachable)
        self.assertFalse(rsp.killed)

    def test_ssh_rc_124_timeout_means_host_dead(self):
        """rc=124 is the GNU coreutils ``timeout`` exit — host or sshd
        unresponsive past the deadline is positive evidence host is dead."""
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)
        ssh = _ScriptedSshRunner([("true", (124, "", ""))])
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", ssh)
        self.assertFalse(rsp.alive, "rc=124 (timeout) is the dead-host signal")
        self.assertFalse(rsp.sshReachable)

    def test_vm_not_running_means_already_fenced(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)
        ssh = _ScriptedSshRunner([
            ("true", (0, "", "")),
            ("virsh list --uuid", (0, "other-uuid-1\nother-uuid-2", "")),
        ])
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", ssh)
        self.assertFalse(rsp.alive)
        self.assertFalse(rsp.qemuFound)
        self.assertFalse(rsp.killed)
        self.assertTrue(rsp.sshReachable)

    def test_vm_running_then_killed(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)
        # First virsh list shows VM running, second list (post-kill) shows VM gone.
        # ScriptedSshRunner matches by substring; the ``virsh list`` substring
        # would match both — feed a stateful ssh runner instead.
        state = {"virsh_list_calls": 0}

        def runner(remote_cmd, timeout):
            if "true" == remote_cmd:
                return (0, "", "")
            if "virsh list" in remote_cmd:
                state["virsh_list_calls"] += 1
                if state["virsh_list_calls"] == 1:
                    return (0, VALID_VM + "\nother-uuid", "")
                return (0, "other-uuid", "")  # post-kill: VM gone
            if "virsh destroy" in remote_cmd:
                return (0, "", "")
            if "pkill" in remote_cmd:
                return (0, "", "")
            return (0, "", "")

        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", runner)
        self.assertFalse(rsp.alive)
        self.assertTrue(rsp.killed)
        self.assertTrue(rsp.qemuFound)

    def test_vm_running_destroy_and_pkill_both_fail(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)

        def runner(remote_cmd, timeout):
            if "true" == remote_cmd:
                return (0, "", "")
            if "virsh list" in remote_cmd:
                return (0, VALID_VM + "\n", "")  # VM still running both times
            return (1, "", "destroy failed")

        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", runner)
        self.assertTrue(rsp.alive,
            "if destroy + pkill both fail, qemu may still be alive — must NOT signal fenced")
        self.assertFalse(rsp.killed)

    def test_virsh_list_failure_treats_as_alive(self):
        cmd = _Cmd(vmUuid=VALID_VM, failedHostIp=VALID_IP)
        ssh = _ScriptedSshRunner([
            ("true", (0, "", "")),
            ("virsh list --uuid", (1, "", "libvirtd hung")),
        ])
        rsp = _SiblingFenceProbe.probe(cmd, "exec-host", ssh)
        self.assertTrue(rsp.alive,
            "if virsh state cannot be inspected, default to alive — uncertain != dead")
        self.assertTrue(rsp.sshReachable)


# ============================================================
# Layer 2: source-level invariants on the real ha_plugin.py
# ============================================================
class TestSiblingFenceSourceInvariants(unittest.TestCase):
    """AST checks on the real kvmagent/plugins/ha_plugin.py.

    These guard the safety contract independently of the mirror above:
    if someone reverts the alive default, or removes one of the explicit
    alive=False sets, this test fails before any runtime regression."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            os.path.dirname(__file__), "..", "plugins", "ha_plugin.py")
        with open(path, "r") as f:
            cls.source = f.read()
        cls.tree = ast.parse(cls.source)
        cls.fn = cls._find_function(cls.tree, "sibling_fence_vm")
        cls.fn_source = ast.unparse(cls.fn) if hasattr(ast, "unparse") else None

    @staticmethod
    def _find_function(tree, name):
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError("sibling_fence_vm not found in ha_plugin.py")

    def test_function_exists(self):
        self.assertIsNotNone(self.fn)

    def test_default_alive_is_true(self):
        """The very first rsp.alive assignment in sibling_fence_vm must be
        True, not False. This is the central P0 invariant: any early-return
        before a real probe must NOT signal host-dead."""
        first_alive_assign = self._first_alive_assignment(self.fn)
        self.assertIsNotNone(first_alive_assign,
            "sibling_fence_vm must initialise rsp.alive")
        self.assertTrue(self._assigns_constant(first_alive_assign, True),
            "rsp.alive default must be True (conservative); reverting to False "
            "re-opens the split-brain ZSTAC-83890 closed")

    def test_has_explicit_alive_false_on_ssh_timeout_branch(self):
        """The ssh-probe ret!=0 branch must explicitly set alive=False —
        this is the only place we can assert host-dead from outside the VM."""
        snippet_re = re.compile(
            r"ssh probe timed out or unreachable.*?host considered dead",
            re.DOTALL)
        match = snippet_re.search(self.source)
        self.assertIsNotNone(match,
            "expected 'ssh probe timed out' message branch in ha_plugin.py")
        # Look ~200 chars before/after the message for an alive=False set.
        window = self.source[max(0, match.start() - 400):match.end() + 200]
        self.assertIn("rsp.alive = False", window,
            "the timeout/unreachable branch must explicitly set rsp.alive=False")

    def test_has_explicit_alive_false_on_vm_not_found(self):
        """When virsh list confirms the VM is not running on the failed
        host, alive must be set False (positive evidence)."""
        snippet_re = re.compile(r"vm not found on failed host")
        match = snippet_re.search(self.source)
        self.assertIsNotNone(match)
        window = self.source[max(0, match.start() - 400):match.end() + 200]
        self.assertIn("rsp.alive = False", window,
            "the 'vm not found' branch must explicitly set rsp.alive=False")

    def test_no_alive_false_in_input_validation_branches(self):
        """No early-return on input validation may set alive=False.
        Catches anyone re-introducing the original P0 bug shape."""
        validation_phrases = [
            "missing vmUuid or failedHostIp",
            "invalid vmUuid format",
            "invalid failedHostIp format",
            "invalid failedHostSshPort",
            "ssh port out of range",
        ]
        for phrase in validation_phrases:
            idx = self.source.find(phrase)
            self.assertNotEqual(idx, -1,
                "expected validation phrase %r in ha_plugin.py" % phrase)
            # The window from the phrase to the next ``return`` must not
            # contain ``rsp.alive = False``. Scan up to 250 chars (a
            # validation branch is short).
            tail = self.source[idx:idx + 250]
            ret_idx = tail.find("return")
            if ret_idx != -1:
                tail = tail[:ret_idx]
            self.assertNotIn("rsp.alive = False", tail,
                "validation branch %r must not set alive=False — "
                "it must inherit the conservative default" % phrase)

    # --- helpers ---

    @staticmethod
    def _first_alive_assignment(fn_node):
        for node in ast.walk(fn_node):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Attribute)
                            and tgt.attr == "alive"
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "rsp"):
                        return node
        return None

    @staticmethod
    def _assigns_constant(assign_node, expected):
        v = assign_node.value
        if isinstance(v, ast.Constant):
            return v.value is expected
        # Py2/Py3 compat: NameConstant for True/False on older Python
        if hasattr(ast, "NameConstant") and isinstance(v, ast.NameConstant):
            return v.value is expected
        return False


if __name__ == "__main__":
    unittest.main()
