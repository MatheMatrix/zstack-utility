import os
import shutil
import sys
import tempfile
import types
import unittest

try:
    from unittest import mock
except ImportError:
    import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

log_mod = types.ModuleType('zstacklib.utils.log')
log_mod.get_logger = lambda name: mock.MagicMock()

linux_mod = types.ModuleType('zstacklib.utils.linux')
linux_mod.mkdir = lambda path, mode=0o755: os.makedirs(path, mode) if not os.path.exists(path) else None
linux_mod.is_mounted = lambda path=None, url=None: False
linux_mod.umount = lambda path, is_exception=True: True

bash_mod = types.ModuleType('zstacklib.utils.bash')
bash_mod.bash_r = lambda cmd: 0

libvirt_mod = types.ModuleType('libvirt')
libvirt_mod.VIR_DOMAIN_AFFECT_LIVE = 1

zstacklib_mod = types.ModuleType('zstacklib')
utils_mod = types.ModuleType('zstacklib.utils')
utils_mod.log = log_mod
utils_mod.linux = linux_mod
utils_mod.bash = bash_mod

sys.modules.setdefault('zstacklib', zstacklib_mod)
sys.modules.setdefault('zstacklib.utils', utils_mod)
sys.modules.setdefault('zstacklib.utils.log', log_mod)
sys.modules.setdefault('zstacklib.utils.linux', linux_mod)
sys.modules.setdefault('zstacklib.utils.bash', bash_mod)
sys.modules.setdefault('libvirt', libvirt_mod)

from kvmagent.plugins import vm_artifact


class Obj(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class VmArtifactTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source_root = os.path.join(self.tmp, 'virtiofs-sources')
        self.view_root = os.path.join(self.tmp, 'vm-views')
        os.makedirs(self.source_root)
        os.makedirs(self.view_root)
        self.old_source_root = vm_artifact.HOST_SOURCE_ROOT
        self.old_view_root = vm_artifact.VM_VIEW_ROOT
        vm_artifact.HOST_SOURCE_ROOT = self.source_root
        vm_artifact.VM_VIEW_ROOT = self.view_root

    def tearDown(self):
        vm_artifact.HOST_SOURCE_ROOT = self.old_source_root
        vm_artifact.VM_VIEW_ROOT = self.old_view_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_path_escape_is_rejected(self):
        try:
            vm_artifact.validate_relative_path('../escape', 'installPath')
            self.fail('installPath traversal should be rejected')
        except Exception as exc:
            self.assertIn('escapes its root', str(exc))

        outside = os.path.join(self.tmp, 'outside-source')
        os.makedirs(outside)
        try:
            vm_artifact.ensure_under(outside, self.source_root, 'sourcePath')
            self.fail('sourcePath outside root should be rejected')
        except Exception as exc:
            self.assertIn('outside allowed root', str(exc))

    def test_bind_readonly_uses_bind_mount_and_remount_ro(self):
        source = os.path.join(self.source_root, 'source-1', 'qwen')
        target = os.path.join(self.view_root, 'vm-1', 'qwen')
        os.makedirs(source)

        commands = []
        with mock.patch.object(vm_artifact.linux, 'is_mounted', return_value=False), \
                mock.patch.object(vm_artifact.bash, 'bash_r', side_effect=lambda cmd: commands.append(cmd) or 0):
            vm_artifact.bind_readonly(source, target, True)

        self.assertEqual(2, len(commands))
        self.assertIn('mount --bind', commands[0])
        self.assertIn(source, commands[0])
        self.assertIn(target, commands[0])
        self.assertIn('mount -o remount,bind,ro', commands[1])
        self.assertIn(target, commands[1])

    def test_cleanup_view_is_idempotent(self):
        stale = os.path.join(self.view_root, 'vm-1', 'stale')
        os.makedirs(stale)

        with mock.patch.object(vm_artifact.linux, 'is_mounted', return_value=False):
            vm_artifact.cleanup_view('vm-1')
            vm_artifact.cleanup_view('vm-1')

        self.assertTrue(os.path.isdir(os.path.join(self.view_root, 'vm-1')))
        self.assertFalse(os.path.exists(stale))

    def test_cleanup_keeps_nested_desired_path(self):
        desired = os.path.join(self.view_root, 'vm-1', 'nested', 'qwen')
        stale = os.path.join(self.view_root, 'vm-1', 'stale')
        os.makedirs(desired)
        os.makedirs(stale)

        with mock.patch.object(vm_artifact.linux, 'is_mounted', return_value=False):
            vm_artifact.cleanup_view('vm-1', [desired])

        self.assertTrue(os.path.isdir(desired))
        self.assertFalse(os.path.exists(stale))

    def test_virtiofs_xml_defaults_cache_none_queue_1024(self):
        source = os.path.join(self.view_root, 'vm-1')
        os.makedirs(source)
        xml = vm_artifact.build_virtiofs_device_xml('vm-1', 'source-qwen')

        self.assertIn("type='virtiofs'", xml)
        self.assertIn("queue='1024'", xml)
        self.assertIn("mode='none'", xml)
        self.assertTrue("dir='%s'" % source in xml or 'dir="%s"' % source in xml)
        self.assertTrue("dir='source-qwen'" in xml or 'dir="source-qwen"' in xml)


if __name__ == '__main__':
    unittest.main()
