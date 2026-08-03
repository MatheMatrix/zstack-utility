import os
import logging
import sys
import tempfile
import threading
import time
import types
import unittest


_MISSING = object()
_STUBBED_MODULES = [
    "zstacklib.utils.linux",
    "zstacklib.utils.log",
    "zstacklib.utils.lock",
    "zstacklib.utils.upload_task",
    "zstacklib.utils.bash",
]
_ORIGINAL_MODULES = dict((name, sys.modules.get(name, _MISSING)) for name in _STUBBED_MODULES)

linux = types.ModuleType("zstacklib.utils.linux")
linux.get_current_timestamp = lambda: int(time.time())
linux.rm_file_force = lambda path: os.path.lexists(path) and os.unlink(path)
linux.shellquote = lambda value: "'%s'" % value.replace("'", "'\\''")
linux.get_disk_capacity_by_df = lambda path: (0, 1024 * 1024 * 1024)
sys.modules["zstacklib.utils.linux"] = linux

log = types.ModuleType("zstacklib.utils.log")
log.get_logger = logging.getLogger
sys.modules["zstacklib.utils.log"] = log

lock = types.ModuleType("zstacklib.utils.lock")


class NamedLock(object):
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


lock.NamedLock = NamedLock
sys.modules["zstacklib.utils.lock"] = lock

upload_task = types.ModuleType("zstacklib.utils.upload_task")


class StorageObject(object):
    pass


class UploadTask(object):
    def __init__(self, task_uuid, install_path):
        self.completed = False
        self.taskUuid = task_uuid
        self.installPath = install_path
        self.expectedSize = 0
        self.lastError = None
        self.lastOpTime = linux.get_current_timestamp()
        self.failureTimes = {}
        self.close = None
        self.upload_lock = threading.Lock()
        self.task_created = False

    def fail(self, reason):
        self._fail(reason)

    def _fail_without_renew(self, reason):
        self._fail(reason)

    def _fail(self, reason):
        if self.completed:
            return
        self.completed = True
        self.lastError = reason
        if self.close:
            self.close()


upload_task.UploadTask = UploadTask
upload_task.StorageObject = StorageObject
sys.modules["zstacklib.utils.upload_task"] = upload_task

bash = types.ModuleType("zstacklib.utils.bash")
bash.bash_roe = lambda command: (0, "", "")
sys.modules["zstacklib.utils.bash"] = bash

from zstacklib.utils.file_system_upload_task import FileSystemUploadTask


def tearDownModule():
    for name, module in _ORIGINAL_MODULES.items():
        if module is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


class TestFileSystemUploadTask(unittest.TestCase):
    def test_complete_upload_atomically_replaces_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, 'package')
            task = FileSystemUploadTask('task-1', destination)
            task.expectedSize = 3
            with open(destination, 'wb') as stream:
                stream.write(b'old')
            with open(task.temporaryPath, 'wb') as stream:
                stream.write(b'new')

            task.complete_upload()

            self.assertTrue(task.completed)
            self.assertIsNone(task.lastError)
            self.assertFalse(os.path.exists(task.temporaryPath))
            with open(destination, 'rb') as stream:
                self.assertEqual(b'new', stream.read())

            task.complete_upload()
            with open(destination, 'rb') as stream:
                self.assertEqual(b'new', stream.read())

    def test_size_mismatch_preserves_destination_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, 'package')
            task = FileSystemUploadTask('task-1', destination)
            task.expectedSize = 4
            with open(destination, 'wb') as stream:
                stream.write(b'old')
            with open(task.temporaryPath, 'wb') as stream:
                stream.write(b'bad')

            with self.assertRaises(Exception):
                task.complete_upload()

            self.assertTrue(task.completed)
            self.assertIsNotNone(task.lastError)
            self.assertFalse(os.path.exists(task.temporaryPath))
            with open(destination, 'rb') as stream:
                self.assertEqual(b'old', stream.read())


if __name__ == '__main__':
    unittest.main()
