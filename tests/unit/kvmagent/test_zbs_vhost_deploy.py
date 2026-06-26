# -*- coding: utf-8 -*-
"""
Unit tests for the lazy-deploy path in kvmagent.plugins.zbs_vhost_target:
image source fallback ordering, conditional insecure-registry downgrade,
target health semantics, and shell quoting of request-supplied values.
"""
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
    # connectivity (not fencing): a host with NO target must read as not-running so its
    # per-protocol ref flips Disconnected and the allocator skips it.
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
