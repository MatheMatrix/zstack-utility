"""
Unit tests for the lazy-deploy path in kvmagent.plugins.zbs_vhost_target:
image source fallback ordering, conditional insecure-registry downgrade,
target health semantics, and shell quoting of request-supplied values.
"""
import json

import pytest
from unittest.mock import patch

from kvmagent.plugins import zbs_vhost_target as t


class TestPullImage:
    def test_plain_pull_success_leaves_docker_config_alone(self):
        with patch.object(t.bash, 'bash_errorout') as be, \
             patch.object(t, 'ensure_insecure_registry') as ir:
            t.pull_image("172.26.208.212:5000/zbs-vhost:x")
            ir.assert_not_called()
            assert be.call_count == 1

    def test_tls_error_downgrades_registry_and_retries(self):
        calls = {'n': 0}

        def be(cmd):
            calls['n'] += 1
            if calls['n'] == 1:
                raise Exception("Get https://172.26.208.212:5000/v2/: "
                                "http: server gave HTTP response to HTTPS client")

        with patch.object(t.bash, 'bash_errorout', side_effect=be), \
             patch.object(t, 'ensure_insecure_registry') as ir:
            t.pull_image("172.26.208.212:5000/zbs-vhost:x")
            ir.assert_called_once_with("172.26.208.212:5000")
            assert calls['n'] == 2

    def test_non_tls_error_propagates_without_downgrade(self):
        with patch.object(t.bash, 'bash_errorout', side_effect=Exception("manifest unknown")), \
             patch.object(t, 'ensure_insecure_registry') as ir:
            with pytest.raises(Exception):
                t.pull_image("172.26.208.212:5000/zbs-vhost:x")
            ir.assert_not_called()


class TestLoadImageFallback:
    def _absent(self):
        return patch.object(t, 'image_present', return_value=False)

    def test_pull_failure_falls_back_to_local_tar(self):
        with self._absent(), \
             patch.object(t, 'pull_image', side_effect=Exception("pull boom")), \
             patch.object(t.os.path, 'exists', return_value=True), \
             patch.object(t.bash, 'bash_errorout') as be:
            t.load_image("reg.io:5000/zbs-vhost:x", image_tar="/x/img.tar")
            assert any('docker load' in str(c) for c in be.call_args_list)

    def test_pull_and_tar_failures_fall_back_to_url(self):
        with self._absent(), \
             patch.object(t, 'pull_image', side_effect=Exception("pull boom")), \
             patch.object(t.os.path, 'exists', return_value=False), \
             patch.object(t, 'download_image') as dl, \
             patch.object(t.bash, 'bash_errorout') as be:
            t.load_image("reg.io:5000/zbs-vhost:x", image_url="http://x/img.tar")
            dl.assert_called_once()
            assert any('docker load' in str(c) for c in be.call_args_list)

    def test_all_sources_failing_raises_aggregate(self):
        with self._absent(), \
             patch.object(t, 'pull_image', side_effect=Exception("pull boom")), \
             patch.object(t.os.path, 'exists', return_value=False):
            with pytest.raises(Exception) as ei:
                t.load_image("reg.io:5000/zbs-vhost:x")
            assert 'pull boom' in str(ei.value)

    def test_present_image_skips_all_sources(self):
        with patch.object(t, 'image_present', return_value=True), \
             patch.object(t, 'pull_image') as pi, \
             patch.object(t.bash, 'bash_errorout') as be:
            t.load_image("reg.io:5000/zbs-vhost:x", image_tar="/x/img.tar")
            pi.assert_not_called()
            be.assert_not_called()


class TestTargetRunning:
    _SOCK = "/var/zbsvhost/sockets/admin.sock"
    _NAME = "zbsvhost-10.0.0.9"

    def test_never_deployed_is_not_running(self):
        with patch.object(t, 'container_exists', return_value=False):
            assert t.target_running(self._SOCK, self._NAME) is False

    def test_deployed_but_exited_is_not_running(self):
        with patch.object(t, 'container_exists', return_value=True), \
             patch.object(t, 'is_running', return_value=False):
            assert t.target_running(self._SOCK, self._NAME) is False

    def test_running_with_ready_sock_is_running(self):
        with patch.object(t, 'container_exists', return_value=True), \
             patch.object(t, 'is_running', return_value=True), \
             patch.object(t, '_control_sock_ready', return_value=True):
            assert t.target_running(self._SOCK, self._NAME) is True

    def test_running_with_dead_sock_is_not_running(self):
        with patch.object(t, 'container_exists', return_value=True), \
             patch.object(t, 'is_running', return_value=True), \
             patch.object(t, '_control_sock_ready', return_value=False):
            assert t.target_running(self._SOCK, self._NAME) is False


class TestShellQuoting:
    def test_download_image_quotes_url_and_dest(self):
        with patch.object(t.bash, 'bash_errorout') as be:
            t.download_image("http://x/a;rm -rf /", "/tmp/a b.tar")
            cmd = be.call_args[0][0]
            assert "'http://x/a;rm -rf /'" in cmd
            assert "'/tmp/a b.tar'" in cmd

    def test_docker_load_quotes_tar_path(self):
        with patch.object(t, 'image_present', return_value=False), \
             patch.object(t.os.path, 'exists', return_value=True), \
             patch.object(t.bash, 'bash_errorout') as be:
            t.load_image("zbs-vhost-local", image_tar="/x/evil;touch pwn.tar")
            cmd = be.call_args[0][0]
            assert "'/x/evil;touch pwn.tar'" in cmd


class TestEnsureDocker:
    @pytest.fixture(autouse=True)
    def daemon_config(self, tmp_path):
        self.daemon_config = tmp_path / "daemon.json"
        self.daemon_config_path = str(self.daemon_config)
        with patch.object(t, 'DOCKER_DAEMON_CONFIG_PATH', self.daemon_config_path), \
             patch.object(t, 'docker_active', return_value=False) as active:
            self.docker_active = active
            yield

    def _write_daemon_config(self, config):
        self.daemon_config.write_text(json.dumps(config) if isinstance(config, dict) else config)

    def _read_daemon_config(self):
        return json.loads(self.daemon_config.read_text()) if self.daemon_config.exists() else None

    def _read_daemon_config_bytes(self):
        return self.daemon_config.read_bytes() if self.daemon_config.exists() else None

    def test_skips_install_when_docker_ready(self):
        self._write_daemon_config({'iptables': False})
        with patch.object(t, 'docker_ready', return_value=True), \
             patch.object(t.bash, 'bash_roe') as br, \
             patch.object(t.bash, 'bash_errorout') as be:
            t.ensure_docker()
            br.assert_not_called()
            be.assert_not_called()

    def test_installs_and_starts_when_missing(self):
        states = iter([False, True])

        def start(cmd):
            assert self._read_daemon_config()['iptables'] is False

        with patch.object(t, 'docker_ready', side_effect=lambda: next(states)), \
             patch.object(t.bash, 'bash_roe', return_value=(0, "", None)) as br, \
             patch.object(t.bash, 'bash_errorout', side_effect=start) as be:
            t.ensure_docker()
            cmds = " ".join(str(c) for c in br.call_args_list)
            assert t.DOCKER_CE_INSTALL_CMD in cmds
            assert any('systemctl enable --now docker' in str(c) for c in be.call_args_list)
            assert self._read_daemon_config() == {'iptables': False}

    def test_preserves_existing_daemon_config_when_disabling_iptables(self):
        self._write_daemon_config({'registry-mirrors': ['https://mirror.example.com']})
        states = iter([False, True])
        with patch.object(t, 'docker_ready', side_effect=lambda: next(states)), \
             patch.object(t.bash, 'bash_roe', return_value=(0, "", None)), \
             patch.object(t.bash, 'bash_errorout'):
            t.ensure_docker()

        assert self._read_daemon_config() == {
            'iptables': False,
            'registry-mirrors': ['https://mirror.example.com'],
        }

    @pytest.mark.parametrize('config', [
        {'iptables': True},
        '{invalid-json',
        '[]',
        'null',
    ])
    def test_rejects_conflicting_daemon_config_before_start(self, config):
        self._write_daemon_config(config)
        with patch.object(t, 'docker_ready', return_value=False), \
             patch.object(t.bash, 'bash_roe') as br, \
             patch.object(t.bash, 'bash_errorout') as be, \
             pytest.raises(Exception):
            t.ensure_docker()

        br.assert_not_called()
        be.assert_not_called()

    @pytest.mark.parametrize('config', [
        None,
        {'iptables': True},
        '{invalid-json',
        '[]',
        'null',
    ])
    def test_rejects_active_docker_without_safe_firewall_config(self, config):
        if config is not None:
            self._write_daemon_config(config)
        original = self._read_daemon_config_bytes()
        with patch.object(t, 'docker_ready', return_value=True), \
             patch.object(t.bash, 'bash_roe') as br, \
             patch.object(t.bash, 'bash_errorout') as be, \
             pytest.raises(Exception):
            t.ensure_docker()

        br.assert_not_called()
        be.assert_not_called()
        assert self._read_daemon_config_bytes() == original

    def test_rejects_active_docker_when_cli_is_unavailable(self):
        self._write_daemon_config({'iptables': False})
        self.docker_active.return_value = True
        with patch.object(t, 'docker_ready', return_value=False), \
             patch.object(t.bash, 'bash_roe', return_value=(0, "", None)) as br, \
             patch.object(t.bash, 'bash_errorout') as be, \
             pytest.raises(Exception, match='active.*command'):
            t.ensure_docker()

        br.assert_not_called()
        be.assert_not_called()

    def test_installs_docker_ce_from_management_node_repo_first(self):
        states = iter([False, True])

        with patch.object(t, 'docker_ready', side_effect=lambda: next(states)), \
             patch.object(t.bash, 'bash_roe', return_value=(0, "", None)) as br, \
             patch.object(t.bash, 'bash_errorout') as be:
            t.ensure_docker()
            cmds = " ".join(str(c) for c in br.call_args_list)
            assert t.DOCKER_CE_INSTALL_CMD in cmds
            assert t.DOCKER_ENGINE_INSTALL_CMD not in cmds
            assert any('systemctl enable --now docker' in str(c) for c in be.call_args_list)

    def test_falls_back_to_docker_engine_when_ce_is_unavailable(self):
        states = iter([False, True])
        installs = []

        def run(cmd):
            assert self._read_daemon_config()['iptables'] is False
            installs.append(cmd)
            if cmd == t.DOCKER_CE_INSTALL_CMD:
                return 1, "", "No match for argument: docker-ce"
            return 0, "", None

        with patch.object(t, 'docker_ready', side_effect=lambda: next(states)), \
             patch.object(t.bash, 'bash_roe', side_effect=run):
            t.ensure_docker()
            assert installs[0] == t.DOCKER_CE_INSTALL_CMD
            assert installs[1] == t.DOCKER_ENGINE_INSTALL_CMD

    def test_raises_with_yum_output_when_both_providers_fail(self):
        def run(cmd):
            if cmd == t.DOCKER_CE_INSTALL_CMD:
                return 1, "ce stdout", "ce stderr"
            return 1, "engine stdout", "engine stderr"

        with patch.object(t, 'docker_ready', return_value=False), \
             patch.object(t.bash, 'bash_roe', side_effect=run):
            with pytest.raises(Exception) as ei:
                t.ensure_docker()
            assert 'ce stderr' in str(ei.value)
            assert 'engine stderr' in str(ei.value)

    def test_raises_when_docker_unavailable_after_install(self):
        with patch.object(t, 'docker_ready', return_value=False), \
             patch.object(t.bash, 'bash_errorout'):
            with pytest.raises(Exception):
                t.ensure_docker()
