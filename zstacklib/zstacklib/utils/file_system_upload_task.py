import os
import traceback
import urlparse
from enum import Enum

from zstacklib.utils import traceable_shell, linux, shell, plugin, log, lock
from zstacklib.utils.bash import bash_roe
from zstacklib.utils.upload_task import UploadTask, StorageObject

logger = log.get_logger(__name__)

class FileObject(StorageObject):
    def __init__(self, file_path):
        super(FileObject, self).__init__()
        self.file_path = file_path
        self.offset = 0
        try:
            self.file_obj = open(file_path, 'r+b')
            self.size = os.path.getsize(file_path)
        except (IOError, OSError) as e:
            raise type(e)("Failed to open file %s: %s" % (file_path, str(e)))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_obj.close()

    def seek(self, offset):
        self.offset = min(offset, self.size)
        self.file_obj.seek(self.offset)

    def read(self, n):
        self.file_obj.seek(self.offset)
        length = min(self.size - self.offset, n)
        content = self.file_obj.read(length)
        self.offset += len(content)
        return content

    def write(self, content):
        self.file_obj.seek(self.offset)
        self.file_obj.write(content)
        self.offset += len(content)
        self.file_obj.flush()

    def close(self):
        self.file_obj.close()

class FileSystemUploadTask(UploadTask):
    def __init__(self, task_uuid, install_path):
        super(FileSystemUploadTask, self).__init__(task_uuid, install_path)

    def complete_upload(self):
        self.success()

    def create_object(self, slice_offset):
        dir_path = os.path.dirname(self.installPath)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        self.create_file_if_not_exists()
        file_obj = FileObject(self.installPath)
        file_obj.seek(slice_offset)
        return file_obj

    def create_file_if_not_exists(self):
        if self.task_created:
            return

        with lock.NamedLock("upload-file-task-%s" % self.taskUuid):
            if not self.task_created:
                r, _, e = bash_roe("fallocate -l %s %s" % (self.expectedSize, self.installPath))
                if r != 0:
                    raise Exception("Failed to allocate file space for %s, because %s " % (self.installPath, str(e)))
                self.task_created = True

    def check_capacity(self, required_size):
        dir_path = os.path.dirname(self.installPath)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        _, avail = linux.get_disk_capacity_by_df(dir_path)
        if avail <= required_size:
            return "dstPath capacity not enough for size: %d, available: %d" % (required_size, avail)
        return None
