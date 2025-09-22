
import os
import pprint
import urlparse
import threading
import rados
import rbd

import zstacklib.utils.http as http
import zstacklib.utils.jsonobject as jsonobject
from zstacklib.utils.bash import *
from zstacklib.utils import qemu_img

from kvmagent.kvmagent import logger
from zstacklib.utils import linux, lock


class UploadTask(object):
    def __init__(self, imageUuid, installPath, dstPath):
        self.completed = False
        self.imageUuid = imageUuid
        self.installPath = installPath
        self.dstPath = dstPath
        self.expectedSize = 0
        self.downloadSize = 0
        self.progress = 0
        self.lastError = None
        self.lastOpTime = linux.get_current_timestamp()
        self.image_format = "raw"
        self.close = None

        self.slice_uploaded = set()
        self.slice_count = 0
        self.slice_size = 0

        self.image_created = False
        self.image_completing = False

    def fail(self, reason):
        self.completed = True
        self.lastError = reason
        self.lastOpTime = linux.get_current_timestamp()
        if self.close:
            self.close()
        logger.info('task failed for %s: %s' % (self.imageUuid, reason))

    def success(self):
        self.completed = True
        self.progress = 100
        self.lastOpTime = linux.get_current_timestamp()
        if self.close:
            self.close()

    def is_started(self):
        return self.progress > 0

    def is_running(self):
        return not (self.completed or self.is_started())

    def renew(self):
        self.lastOpTime = linux.get_current_timestamp()

    def all_slice_uploaded(self):
        return 0 < self.slice_count == len(self.slice_uploaded)

    def checked_download_size(self):
        for i in range(self.slice_count):
            if i not in self.slice_uploaded:
                return i * self.slice_size

        return self.expectedSize

    def create_image_if_not_exists(self):
        if self.image_created:
            return

        with lock.NamedLock("upload-image-%s" % self.imageUuid):
            # 创建目录 创建文件
            if not self.image_created:
                # 创建文件
                self.image_created = True

    def allow_image_completing(self):
        if self.all_slice_uploaded():
            with lock.NamedLock("upload-image-%s" % self.imageUuid):
                if not self.image_completing:
                    self.image_completing = True
                    return True
        return False

    def add_download_size(self, delta):
        with lock.NamedLock("upload-image-%s" % self.imageUuid):
            self.downloadSize += delta
