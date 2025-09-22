# encoding: utf-8

import re
import hashlib
import logging
from zstacklib.utils import linux, lock
import cherrypy
from cherrypy._cpreqbody import Entity, Part, SizedReader
from cherrypy._cprequest import Request

logger = logging.getLogger(__name__)
BUFFER_SIZE = 16 * 1024 ** 2  # 16MB


class UploadParam(object):
    def __init__(self):
        self.image_uuid = None
        self.image_size = 0

        self.slice_index = 0
        self.slice_offset = 0
        self.slice_size = 0
        self.slice_md5 = None


class UploadTasks(object):
    MAX_RECORDS = 80

    def __init__(self):
        self.tasks = {}

    def _expunge_oldest_task(self):
        key, ts = '', linux.get_current_timestamp()
        for k in self.tasks:
            task = self.tasks[k]

            if task.is_running():
                continue

            if task.lastOpTime < ts:
                key, ts = k, task.lastOpTime

        if key != '': del (self.tasks[key])

    @lock.lock('upload-task')
    def add_task(self, task):
        if len(self.tasks) >= self.MAX_RECORDS:
            self._expunge_oldest_task()
        self.tasks[task.imageUuid] = task

    @lock.lock('upload-task')
    def get_task(self, image_uuid):
        return self.tasks.get(image_uuid)


class UploadTask(object):
    def __init__(self, imageUuid, installPath):
        self.completed = False
        self.imageUuid = imageUuid
        self.installPath = installPath
        self.expectedSize = 0
        self.downloadSize = 0
        self.progress = 0
        self.lastError = None
        self.lastOpTime = linux.get_current_timestamp()
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

    def create_image_if_not_exists(self, install_path):
        raise NotImplementedError()

    def complete_upload(self):
        raise NotImplementedError()

    def create_object(self, slice_offset):
        raise NotImplementedError()


class StorageObject(object):
    def seek(self, offset):
        raise NotImplementedError()

    def read(self, n):
        raise NotImplementedError()

    def write(self, content):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class UploadHandler(object):
    def __init__(self, req, upload_tasks):
        self.req = req
        self.upload_tasks = upload_tasks

    @staticmethod
    def get_boundary(entity):
        if 'boundary' in entity.content_type.params:
            ib = entity.content_type.params['boundary'].strip('"')
        else:
            return None

        if not re.match("^[ -~]{0,200}[!-~]$", ib):
            raise ValueError('Invalid boundary in multipart form: %r' % (ib,))

        ib = ('--' + ib).encode('ascii')

        # Find the first marker
        while True:
            b = entity.readline()
            if not b:
                return None

            b = b.strip()
            if b == ib:
                break

        return ib

    @staticmethod
    def get_upload_param(headers):
        def get_long_field(key, default=None):
            v = headers.get(key, default)
            try:
                lv = long(v)
                if lv < 0:
                    raise ValueError
                return lv
            except ValueError:
                raise Exception('invalid header "%s": %s' % (key, v))

        up = UploadParam()
        up.image_uuid = headers['X-IMAGE-UUID']
        up.image_size = get_long_field('X-IMAGE-SIZE')
        up.slice_offset = get_long_field('X-SLICE-OFFSET', default=0)
        up.slice_size = get_long_field('X-SLICE-SIZE', default=up.image_size)
        up.slice_index = get_long_field('X-SLICE-INDEX', default=0)
        up.slice_md5 = headers.get('X-SLICE-MD5', None)

        if up.slice_offset >= up.image_size:
            raise Exception('invalid slice offset header: %s, total_size: %d' %
                            (up.slice_offset, up.image_size))

        return up

    def get_upload_task(self, param):
        task = self.upload_tasks.get_task(param.image_uuid)
        if task is None:
            raise Exception('image not found %s' % param.image_uuid)

        if task.lastError:
            self._fail_task(task, task.lastError)

        if task.completed:
            raise Exception('image[uuid: %s] upload has completed' % param.image_uuid)

        task.expectedSize = param.image_size

        if param.slice_index == 0:
            task.slice_size = param.slice_size
            err = task.check_capacity(task.expectedSize)
            if err:
                self._fail_task(task, err)

        if param.slice_offset + param.slice_size == param.image_size:
            slice_count = param.slice_index + 1
        else:
            slice_count = (param.image_size - 1) / param.slice_size + 1

        if not task.slice_count:
            task.slice_count = slice_count
        elif task.slice_count != slice_count:
            raise Exception(
                "every upload request for image[uuid:%s] should has the same slice size and image size" % param.image_uuid)

        return task

    @staticmethod
    def _fail_task(task, reason):
        task.fail(reason)
        raise Exception(reason)

    def upload_slice(self, entity, param, task):
        boundary = self.get_boundary(entity)
        if not boundary:
            self._fail_task(task, 'unexpected post form')

        try:
            self.stream_body(entity, boundary, param, task)
        except Exception, e:
            self._fail_task(task, str(e))

    @staticmethod
    def stream_body(entity, boundary, param, task):
        # type: (Entity, str, UploadParam, UploadTask) -> None

        image_obj = task.create_object(param.slice_offset)
        while True:
            headers = Part.read_headers(entity.fp)
            p = Part(entity.fp, headers, boundary)
            if not p.filename:
                continue

            logger.debug("uploading image %s: %s slice, index: %d, offset: %d, content length: %d" %
                         (param.image_uuid, p.filename, param.slice_index, param.slice_offset, param.slice_size))

            slice_downloaded_size = 0
            try:
                reader = SizedReader(p.fp, None, param.slice_offset)
                remaining = param.slice_size
                bytes_read = 0
                md5 = hashlib.md5()
                chunks = []
                chunk_size = 32 * 1024
                while remaining > 0:
                    if task.lastError:
                        raise Exception(task.lastError)
                    tmp = reader.read(min(chunk_size, remaining))
                    datalen = len(tmp)
                    task.renew()
                    chunks.append(tmp)
                    md5.update(tmp)

                    remaining -= datalen
                    bytes_read += datalen
                    if bytes_read >= BUFFER_SIZE or remaining <= 0:
                        image_obj.write(b''.join(chunks))
                        task.add_download_size(bytes_read)
                        slice_downloaded_size += bytes_read
                        chunks = []
                        bytes_read = 0
            finally:
                image_obj.close()
            break

        if param.slice_size != slice_downloaded_size:
            task.add_download_size(-slice_downloaded_size)
            raise Exception("incomplete image %s slice index %d, offset %d, completed %d, expected %d" %
                            (param.image_uuid, param.slice_index, param.slice_offset, slice_downloaded_size,
                             param.slice_size))

        if param.slice_md5 and param.slice_md5 != md5.hexdigest():
            task.add_download_size(-slice_downloaded_size)
            raise cherrypy.HTTPError(406, "content md5 not match, expected: %s, actual: %s" % (
                param.slice_md5, md5.hexdigest()))

        task.slice_uploaded.add(param.slice_index)
        logger.debug("uploaded image %s slice, index: %d offset: %d, content length: %d" %
                     (param.image_uuid, param.slice_index, param.slice_offset, param.slice_size))

    def handle_upload(self):
        upload_param = self.get_upload_param(self.req.headers)
        task = self.get_upload_task(upload_param)

        logger.debug("======================================================")
        logger.debug(task.expectedSize)
        logger.debug("======================================================")

        self.upload_slice(self.req.body, upload_param, task)
        if task.allow_image_completing():
            task.complete_upload()
