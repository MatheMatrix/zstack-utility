import errno
import os

from zstacklib.utils import linux, log, lock
from zstacklib.utils.bash import bash_roe
from zstacklib.utils.upload_task import UploadTask, StorageObject

logger = log.get_logger(__name__)

class FileObject(StorageObject):
    def __init__(self, file_path):
        super(FileObject, self).__init__()
        self.file_path = file_path
        self.offset = 0
        self.file_obj = None
        try:
            self.file_obj = open(file_path, 'r+b')
            self.size = os.path.getsize(file_path)
        except (IOError, OSError) as e:
            if self.file_obj is not None:
                self.file_obj.close()
            raise Exception("Failed to open file %s: %s" % (file_path, str(e)))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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
        self.size = max(self.size, self.offset)
        self.file_obj.flush()

    def sync_size(self):
        try:
            self.size = os.path.getsize(self.file_path)
        except (IOError, OSError):
            pass

    def close(self):
        if self.file_obj is not None and not self.file_obj.closed:
            self.file_obj.close()

class FileSystemUploadTask(UploadTask):
    def __init__(self, task_uuid, install_path):
        super(FileSystemUploadTask, self).__init__(task_uuid, install_path)
        self.temporaryPath = "%s.uploading.%s" % (install_path, task_uuid)

    def complete_upload(self):
        close = None
        try:
            with self.upload_lock:
                if self.completed:
                    if self.lastError:
                        raise Exception(self.lastError)
                    return
                actual_size = os.path.getsize(self.temporaryPath)
                if actual_size != self.expectedSize:
                    raise Exception(
                        "uploaded file size mismatch, expected: %s, actual: %s"
                        % (self.expectedSize, actual_size))
                os.replace(self.temporaryPath, self.installPath)
                self.completed = True
                self.failureTimes.clear()
                self.lastOpTime = linux.get_current_timestamp()
                close = self.close
        except Exception as error:
            self.fail(str(error))
            raise
        if close:
            close()

    def create_object(self, slice_offset):
        dir_path = os.path.dirname(self.installPath)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, 0o755)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise Exception("Failed to create directory %s: %s" % (dir_path, str(e)))

        self.create_file_if_not_exists()
        file_obj = FileObject(self.temporaryPath)
        file_obj.seek(slice_offset)
        return file_obj

    def create_file_if_not_exists(self):
        if self.task_created:
            return

        with lock.NamedLock("upload-file-task-%s" % self.taskUuid):
            if not self.task_created:
                try:
                    size = int(self.expectedSize)
                except (TypeError, ValueError):
                    raise Exception("expectedSize must be a valid integer, current: %s (type: %s)"
                                    % (self.expectedSize, type(self.expectedSize).__name__))
                if size <= 0:
                    raise Exception("expectedSize must be set before creating file, current: %s" % self.expectedSize)
                r, _, e = bash_roe(
                    "fallocate -l %d %s"
                    % (size, linux.shellquote(self.temporaryPath)))
                if r != 0:
                    raise Exception(
                        "Failed to allocate file space for %s, because %s "
                        % (self.temporaryPath, str(e)))
                self.task_created = True

    def fail(self, reason):
        super(FileSystemUploadTask, self).fail(reason)
        linux.rm_file_force(self.temporaryPath)

    def _fail_without_renew(self, reason):
        super(FileSystemUploadTask, self)._fail_without_renew(reason)
        linux.rm_file_force(self.temporaryPath)

    def check_capacity(self, required_size):
        dir_path = os.path.dirname(self.installPath)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, 0o755)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise Exception("Failed to create directory %s: %s" % (dir_path, str(e)))

        _, avail = linux.get_disk_capacity_by_df(dir_path)
        if avail <= required_size:
            return "dstPath capacity not enough for size: %d, available: %d" % (required_size, avail)
        return None
