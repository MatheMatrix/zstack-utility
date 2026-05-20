import time

from kvmagent.test.utils import pytest_utils
from kvmagent.test.utils.stub import *
from kvmagent.plugins.ha_plugin import HaPlugin
from zstacklib.test.utils import env
from zstacklib.utils.http import REQUEST_BODY
from zstacklib.utils import bash, jsonobject
from unittest import TestCase


init_kvmagent()

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {}
}


## describe: case will manage by ztest
class TestHaPreFenceVmOnSuspectHost(TestCase, pytest_utils.PytestExtension):
    @classmethod
    def setUpClass(cls):
        cls.ha_plugin = HaPlugin()
        cls.vm_uuid = 'zstac83890-fence-ssh-kill-0001'
        cls.workdir = '/tmp/zstac83890-fence'

    def _cleanup_qemu_like_process(self):
        bash.bash_ro("pkill -9 -f '[q]emu-[ks].*%s' 2>/dev/null || true" % self.vm_uuid)
        bash.bash_ro("rm -rf %s" % self.workdir)

    def _qemu_like_process_exists(self):
        r, o = bash.bash_ro("pgrep -f '[q]emu-[ks].*%s'" % self.vm_uuid)
        return r == 0 and o.strip() != ''

    def _wait_qemu_like_process_started(self):
        for _ in range(20):
            if self._qemu_like_process_exists():
                return
            time.sleep(0.5)
        self.fail('failed to start qemu-like process for vm[%s]' % self.vm_uuid)

    def _wait_qemu_like_process_killed(self):
        for _ in range(20):
            if not self._qemu_like_process_exists():
                return
            time.sleep(0.5)
        self.fail('qemu-like process still alive after pre-fence for vm[%s]' % self.vm_uuid)

    def _start_qemu_like_process(self):
        bash.bash_errorout('mkdir -p %s' % self.workdir)
        bash.bash_errorout(
            "nohup bash -c 'exec -a \"qemu-system-x86_64 -name guest=%s\" sleep 300' "
            "> %s/qemu-like.log 2>&1 &" % (self.vm_uuid, self.workdir)
        )
        self._wait_qemu_like_process_started()

    def _make_request_without_logging_private_key(self, body):
        return {
            REQUEST_BODY: jsonobject.dumps(body, include_protected_attr=True)
        }

    def _get_current_host_ssh_ip(self):
        current_host = env.get_test_environment_metadata()
        target_ip = current_host.get('ip', '') if hasattr(current_host, 'get') else ''
        target_ip = target_ip.strip() if target_ip else ''
        if target_ip:
            return target_ip

        r, o = bash.bash_ro(
            "ip -4 route get 1.1.1.1 | awk '{for (i=1; i<=NF; i++) if ($i == \"src\") {print $(i+1); exit}}'"
        )
        if r == 0 and o.strip():
            return o.strip().splitlines()[0]

        return '127.0.0.1'

    def test_pre_fence_ssh_unreachable_classification(self):
        self.assertTrue(self.ha_plugin._is_pre_fence_ssh_unreachable(
            255, '', 'ssh: connect to host 192.0.2.10 port 22: Connection timed out'))
        self.assertTrue(self.ha_plugin._is_pre_fence_ssh_unreachable(
            255, '', 'ssh: connect to host 192.0.2.10 port 22: No route to host'))
        self.assertTrue(self.ha_plugin._is_pre_fence_ssh_unreachable(
            255, '', 'ssh: connect to host 192.0.2.10 port 22: Connection refused'))

        self.assertFalse(self.ha_plugin._is_pre_fence_ssh_unreachable(
            255, '', 'Permission denied (publickey,password).'))
        self.assertFalse(self.ha_plugin._is_pre_fence_ssh_unreachable(
            255, '', 'Authentication failed.'))
        self.assertFalse(self.ha_plugin._is_pre_fence_ssh_unreachable(
            1, '', 'local command failed'))

    @pytest_utils.ztest_decorater
    def test_fence_vm_on_suspect_host_ssh_kills_qemu_process(self):
        target_ip = self._get_current_host_ssh_ip()

        self._cleanup_qemu_like_process()
        try:
            self._start_qemu_like_process()

            rsp = self.ha_plugin.fence_vm_on_suspect_host(self._make_request_without_logging_private_key({
                'vmUuid': self.vm_uuid,
                'targetHostUuid': 'zstac83890-target-host',
                'targetHostIp': target_ip,
                'targetHostUsername': 'root',
                'targetHostPrivateKey': env.get_private_key(),
                'targetHostSshPort': 22,
                'sshTimeoutSec': 20
            }))
            rsp = jsonobject.loads(rsp)

            self.assertEqual(True, rsp.success, rsp.error)
            self._wait_qemu_like_process_killed()
        finally:
            self._cleanup_qemu_like_process()
