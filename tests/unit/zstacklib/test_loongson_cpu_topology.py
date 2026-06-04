# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys
import types
import unittest


def _stub_module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _load_linux():
    stub_names = [
        "netaddr", "simplejson", "xxhash", "zstacklib", "zstacklib.utils",
        "zstacklib.utils.thread", "zstacklib.utils.qemu_img",
        "zstacklib.utils.lock", "zstacklib.utils.xmlobject",
        "zstacklib.utils.shell", "zstacklib.utils.log",
        "zstacklib.utils.iproute",
    ]
    sentinel = object()
    saved = {name: sys.modules.get(name, sentinel) for name in stub_names}

    _stub_module("netaddr")
    _stub_module("simplejson")
    _stub_module("xxhash")
    zstacklib_pkg = _stub_module("zstacklib")
    utils_pkg = _stub_module("zstacklib.utils")
    zstacklib_pkg.utils = utils_pkg

    for name in ("thread", "qemu_img", "xmlobject", "iproute"):
        module = _stub_module("zstacklib.utils.%s" % name)
        setattr(utils_pkg, name, module)

    lock = _stub_module("zstacklib.utils.lock")
    lock.lock = lambda name: (lambda func: func)
    utils_pkg.lock = lock

    shell = _stub_module("zstacklib.utils.shell")
    shell.call = lambda cmd, exception=True, workdir=None, output_bytes=False: ""
    utils_pkg.shell = shell

    log = _stub_module("zstacklib.utils.log")
    log.get_logger = lambda name: type("Logger", (), {
        "debug": lambda self, *args, **kwargs: None,
        "info": lambda self, *args, **kwargs: None,
        "warn": lambda self, *args, **kwargs: None,
        "error": lambda self, *args, **kwargs: None,
    })()
    utils_pkg.log = log

    path = pathlib.Path(__file__).parents[3] / "zstacklib/zstacklib/utils/linux.py"
    spec = importlib.util.spec_from_file_location("linux_for_loongson_test", str(path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in saved.items():
            if old is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


class TestLoongsonCpuTopology(unittest.TestCase):
    def setUp(self):
        self.linux = _load_linux()

    def test_detects_loongson_3c5000l_model(self):
        self.assertTrue(self.linux.is_loongson_3c5000l_cpu("Loong-son-3C5000L"))
        self.assertTrue(self.linux.is_loongson_3c5000l_cpu("loongson-3c5000l"))
        self.assertFalse(self.linux.is_loongson_3c5000l_cpu("Loongson-3A5000"))
        self.assertFalse(self.linux.is_loongson_3c5000l_cpu(""))

    def test_loongson_3c5000l_derives_socket_count_from_visible_cpus(self):
        self.linux.get_cpu_model = lambda: ("Loongson", "Loong-son-3C5000L")

        for cpu_num, socket_num, core_num in (
                (16, 1, 16),
                (32, 2, 32),
                (64, 4, 64),
                (31, 2, 32)):
            self.linux.get_cpu_num = lambda cpu_num=cpu_num: cpu_num

            with self.subTest(cpu_num=cpu_num):
                self.assertEqual(socket_num, self.linux.get_socket_num())
                self.assertEqual(core_num, self.linux.get_cpu_core_num())

    def test_regular_cpu_keeps_existing_majority_socket_logic(self):
        self.linux.get_cpu_model = lambda: ("GenuineIntel", "Intel(R) Xeon(R)")

        def shell_call(cmd, exception=True, workdir=None, output_bytes=False):
            if "dmidecode -t processor" in cmd:
                return "2"
            if "Socket\\(s\\)" in cmd:
                return "2"
            if "physical id" in cmd:
                return "1"
            if "per socket" in cmd:
                return "4"
            return ""

        self.linux.shell.call = shell_call

        self.assertEqual(2, self.linux.get_socket_num())
        self.assertEqual(8, self.linux.get_cpu_core_num())


if __name__ == '__main__':
    unittest.main()
