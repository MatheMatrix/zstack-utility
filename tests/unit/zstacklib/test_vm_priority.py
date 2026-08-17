import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def _load_linux_module():
    linux_path = Path(__file__).resolve().parents[3] / "zstacklib/zstacklib/utils/linux.py"
    spec = importlib.util.spec_from_file_location("linux_vm_priority_under_test", str(linux_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_shell_cmd(return_codes):
    calls = []

    class FakeShellCmd(object):
        def __init__(self, cmd):
            self.cmd = cmd
            self.return_code = 0

        def __call__(self, is_exception=True):
            calls.append((self.cmd, is_exception))
            self.return_code = return_codes.pop(0) if return_codes else 0

    return FakeShellCmd, calls


def test_set_vm_priority_updates_live_and_config(monkeypatch):
    linux = _load_linux_module()
    shell_cmd, calls = _fake_shell_cmd([0, 0])
    priority = SimpleNamespace(vmUuid="vm-uuid", cpuShares=1024, oomScoreAdj=-900)
    write_file = Mock(return_value=True)

    monkeypatch.setattr(linux.shell, "ShellCmd", shell_cmd)
    monkeypatch.setattr(linux, "write_file", write_file)

    linux.set_vm_priority("1234", priority)

    assert calls == [
        ("virsh schedinfo vm-uuid --set cpu_shares=1024 --live", False),
        ("virsh schedinfo vm-uuid --set cpu_shares=1024 --config", False),
    ]
    write_file.assert_called_once_with("/proc/1234/oom_score_adj", -900)


def test_set_vm_priority_keeps_oom_score_when_config_update_fails(monkeypatch):
    linux = _load_linux_module()
    shell_cmd, calls = _fake_shell_cmd([0, 1])
    priority = SimpleNamespace(vmUuid="vm-uuid", cpuShares=1024, oomScoreAdj=-900)
    write_file = Mock(return_value=True)
    logger = Mock()

    monkeypatch.setattr(linux.shell, "ShellCmd", shell_cmd)
    monkeypatch.setattr(linux, "write_file", write_file)
    monkeypatch.setattr(linux, "logger", logger)

    linux.set_vm_priority("1234", priority)

    assert calls == [
        ("virsh schedinfo vm-uuid --set cpu_shares=1024 --live", False),
        ("virsh schedinfo vm-uuid --set cpu_shares=1024 --config", False),
    ]
    write_file.assert_called_once_with("/proc/1234/oom_score_adj", -900)
    logger.warn.assert_called_once_with("set vm vm-uuid config cpu_shares failed")
