import imp
import os
import sys
import types
import unittest


def _module(name, created_modules=None):
    m = types.ModuleType(name)
    sys.modules[name] = m
    if created_modules is not None:
        created_modules.append(m)
    return m


def _load_linux_with_stubs():
    module_names = [
        'netaddr',
        'simplejson',
        'xxhash',
        'zstacklib',
        'zstacklib.utils',
        'zstacklib.utils.thread',
        'zstacklib.utils.qemu_img',
        'zstacklib.utils.lock',
        'zstacklib.utils.xmlobject',
        'zstacklib.utils.shell',
        'zstacklib.utils.log',
        'zstacklib.utils.iproute',
    ]
    sentinel = object()
    old_modules = dict((name, sys.modules.get(name, sentinel))
                       for name in module_names)
    created_modules = []

    def stub_module(name):
        return _module(name, created_modules)

    try:
        for name in ['netaddr', 'simplejson', 'xxhash']:
            stub_module(name)

        zstacklib_pkg = stub_module('zstacklib')
        utils_pkg = stub_module('zstacklib.utils')
        zstacklib_pkg.utils = utils_pkg
        for name in [
                'thread', 'qemu_img', 'lock', 'xmlobject', 'shell', 'log',
                'iproute']:
            m = stub_module('zstacklib.utils.' + name)
            setattr(utils_pkg, name, m)

        utils_pkg.log.get_logger = lambda name: None
        utils_pkg.shell.call = lambda *args, **kwargs: ''

        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..'))
        linux_path = os.path.join(
            root, 'zstacklib', 'zstacklib', 'utils', 'linux.py')
        return imp.load_source(
            '_linux_libvirt_package_version_under_test', linux_path)
    finally:
        created_module_ids = set(id(module) for module in created_modules)
        for name, module in list(sys.modules.items()):
            if id(module) in created_module_ids:
                sys.modules.pop(name, None)
        for name, old_module in old_modules.items():
            if old_module is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


linux = _load_linux_with_stubs()


class TestLibvirtPackageVersion(unittest.TestCase):
    def test_uses_timeout_and_allows_rpm_query_failure(self):
        calls = []

        def shell_call(cmd, exception=True):
            calls.append((cmd, exception))
            return ' 9.0.0-1.el8\n'

        linux.shell.call = shell_call

        version = linux.get_libvirt_package_version()

        self.assertEqual('9.0.0-1.el8', version)
        self.assertEqual(1, len(calls))
        self.assertIn('timeout -k 5s 10s rpm -q libvirt', calls[0][0])
        self.assertFalse(calls[0][1])

    def test_libvirt_rpm_info_uses_timeout_and_keeps_failure_empty(self):
        calls = []

        class ShellCmd(object):
            def __init__(self, cmd):
                self.cmd = cmd
                self.return_code = 1
                self.stdout = ''

            def __call__(self, is_exception=True):
                calls.append((self.cmd, is_exception))

        linux.shell.ShellCmd = ShellCmd

        version, release = linux.get_libvirt_rpm_info()

        self.assertEqual('', version)
        self.assertEqual('', release)
        self.assertEqual(2, len(calls))
        self.assertIn("timeout -k 5s 10s rpm -q --qf '%{VERSION}' libvirt",
                      calls[0][0])
        self.assertIn("timeout -k 5s 10s rpm -q --qf '%{RELEASE}' libvirt",
                      calls[1][0])
        self.assertFalse(calls[0][1])
        self.assertFalse(calls[1][1])


if __name__ == '__main__':
    unittest.main()
