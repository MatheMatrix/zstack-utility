import imp
import os
import sys
import tempfile
import threading
import types
import unittest


def _module(name, created_modules=None):
    m = types.ModuleType(name)
    sys.modules[name] = m
    if created_modules is not None:
        created_modules.append(m)
    return m


def _load_lock_with_stubs():
    module_names = ['log']
    sentinel = object()
    old_modules = dict((name, sys.modules.get(name, sentinel))
                       for name in module_names)
    created_modules = []

    try:
        log = _module('log', created_modules)
        log.get_logger = lambda name: None

        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..'))
        lock_path = os.path.join(
            root, 'zstacklib', 'zstacklib', 'utils', 'lock.py')
        return imp.load_source('_lock_timeout_under_test', lock_path)
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


lock = _load_lock_with_stubs()


class TestLockTimeout(unittest.TestCase):
    def test_named_lock_times_out_when_another_thread_holds_it(self):
        ready = threading.Event()
        release = threading.Event()

        def hold_lock():
            with lock.NamedLock('rpmdb-timeout-test'):
                ready.set()
                release.wait(1)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        try:
            self.assertTrue(ready.wait(1))
            with self.assertRaises(lock.LockTimeout):
                with lock.NamedLock('rpmdb-timeout-test',
                                    timeout=0.01,
                                    interval=0.001):
                    pass
        finally:
            release.set()
            holder.join()

    def test_file_lock_passes_timeout_to_named_lock(self):
        dname = tempfile.mkdtemp()
        lock_file = os.path.join(dname, 'rpmdb.lock')
        calls = []

        class Locker(object):
            timeout = 3

            def lock(self, lock_file):
                calls.append('lock')

            def unlock(self, lock_file):
                calls.append('unlock')

        @lock.file_lock(lock_file, locker=Locker())
        def locked_function():
            calls.append('body')

        locked_function()

        self.assertEqual(['lock', 'body', 'unlock'], calls)


if __name__ == '__main__':
    unittest.main()
