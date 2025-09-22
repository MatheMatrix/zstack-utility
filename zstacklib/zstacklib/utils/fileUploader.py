import hashlib

import cherrypy
import rbd
from cherrypy._cpreqbody import Entity, Part, SizedReader
from cherrypy._cprequest import Request

import zstacklib.utils.http as http
import zstacklib.utils.jsonobject as jsonobject
import zstacklib.utils.plugin as plugin
from zstacklib.utils.bash import *


def get_boundary(entity):
    # type: (Entity) -> str

    ib = ""
    if 'boundary' in entity.content_type.params:
        # http://tools.ietf.org/html/rfc2046#section-5.1.1
        # "The grammar for parameters on the Content-type field is such that it
        # is often necessary to enclose the boundary parameter values in quotes
        # on the Content-type line"
        ib = entity.content_type.params['boundary'].strip('"')

    if not re.match("^[ -~]{0,200}[!-~]$", ib):
        raise ValueError('Invalid boundary in multipart form: %r' % (ib,))

    ib = ('--' + ib).encode('ascii')

    # Find the first marker
    while True:
        b = entity.readline()
        if not b:
            return

        b = b.strip()
        if b == ib:
            break

    return ib


def stream_body(entity, boundary, param, task):
    # type: (Entity, str, UploadParam, UploadTask) -> None

    _, image_name = task.tmpPath.split('/')
    task.create_image_if_not_exists(ioctx, image_name)
    image_obj = ImageFileObject(rbd.Image(ioctx, image_name))
    image_obj.seek(param.slice_offset)

    # 检查文件是否存在，存在和不存在需要做不同的处理

    while True:
        headers = Part.read_headers(entity.fp)
        p = Part(entity.fp, headers, boundary)
        if not p.filename:
            continue

        logger.debug("uploading file %s: %s slice, index: %d, offset: %d, content length: %d" %
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


def complete_upload(task):
    task.success()


class FileUploader:
    def __init__(self, req, cmd):
        self.req = req
        self.cmd = cmd

    class FileObject(object):
        def __init__(self, file):
            # type: (rbd.Image) -> None
            self.offset = 0
            self.file = file
            self.size = file.size()

        def seek(self, offset):
            self.offset = min(offset, self.size)

        def read(self, n):
            length = min(self.size - self.offset, n)
            content = self.image.read(self.offset, length)
            self.offset += length
            return content

        def write(self, content):
            self.image.write(content, self.offset)
            self.offset = min(self.offset + len(content), self.size)

        def close(self):
            self.image.close()
            logger.debug("%s closed" % str(self.image))

    def upload(self, req):
        # type: (Request) -> None

        upload_param = self.get_upload_param(req.headers)
        task = self.get_upload_task(upload_param)
        self.upload_slice(req.body, upload_param, task)

        if task.allow_image_completing():
            self.complete_upload(task)

    def get_upload_param(req_header):
        # type: (dict[str, str]) -> UploadParam

        def get_long_field(key, default=None):
            v = req_header.get(key, default)
            try:
                lv = long(v)
                if lv < 0:
                    raise ValueError
                return lv
            except ValueError:
                raise Exception('invalid header "%s": %s' % (key, v))

        up = UploadParam()
        up.image_uuid = req_header['X-IMAGE-UUID']
        up.image_size = get_long_field('X-IMAGE-SIZE')
        up.slice_offset = get_long_field('X-SLICE-OFFSET', default=0)
        up.slice_size = get_long_field('X-SLICE-SIZE', default=up.image_size)
        up.slice_index = get_long_field('X-SLICE-INDEX', default=0)
        up.expected_md5 = req_header.get('X-SLICE-MD5', None)

        if up.slice_offset >= up.image_size:
            raise Exception('invalid slice offset header: %s, image_size: %d' % (up.slice_offset, up.image_size))

        return up

    def get_upload_task(self, param):
        # type: (UploadParam) -> UploadTask
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

            _, avail, _ = self._get_capacity()
            if avail <= task.expectedSize:
                self._fail_task(task, 'capacity not enough for size: %d' % param.image_size)

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

    def upload_slice(self, entity, param, task):
        # type: (Entity, UploadParam, UploadTask) -> None

        boundary = get_boundary(entity)
        if not boundary:
            self._fail_task(task, 'unexpected post form')

        try:
            stream_body(entity, boundary, param, task)
        except cherrypy.HTTPError as e:
            raise cherrypy.HTTPError(e.status, e._message)
        except Exception as e:
            if str(e).lstrip() != 'timed out':
                shell.run('rbd rm %s' % task.tmpPath)
                self._fail_task(task, str(e))
            if param.slice_offset == 0:
                shell.run('rbd rm %s' % task.tmpPath)

    def _prepare_upload(self, cmd):
        class ImageUploadDaemon(plugin.TaskDaemon):
            def __init__(self, task):
                super(ImageUploadDaemon, self).__init__(cmd, 'imageUpload')
                self.task = task
                self.task.close = self.close

            def _cancel(self):
                if self.task.completed:
                    return
                self.task.lastError = "image [uuid: %s] upload canceled" % cmd.imageUuid
                shell.run('rbd rm %s' % task.tmpPath)

        start = len(self.UPLOAD_PROTO)
        imageUuid = cmd.url[start:start + self.LENGTH_OF_UUID]
        dstPath = self._normalize_install_path(cmd.installPath)

        pool, image_name = self._parse_install_path(cmd.installPath)
        tmp_image_name = 'tmp-%s' % image_name
        tmpPath = '%s/%s' % (pool, tmp_image_name)

        task = UploadTask(imageUuid, cmd.installPath, dstPath, tmpPath)
        self.upload_tasks.add_task(task)
        ImageUploadDaemon(task).start()

    def _get_upload_path(self, req):
        host = req[http.REQUEST_HEADER]['Host']
        return 'http://' + host + self.UPLOAD_IMAGE_PATH

    def get_upload_progress(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        task = self.upload_tasks.get_task(cmd.imageUuid)
        if task is None:
            raise Exception('image not found %s' % cmd.imageUuid)

        rsp = UploadProgressRsp()
        rsp.completed = task.completed
        rsp.installPath = task.installPath
        rsp.size = task.expectedSize
        rsp.actualSize = task.expectedSize
        rsp.downloadSize = task.checked_download_size()
        rsp.lastOpTime = long(task.lastOpTime) * 1000
        rsp.format = task.image_format
        if task.expectedSize == 0:
            rsp.progress = 0
        elif task.completed and not task.lastError:
            rsp.size = self._get_file_size(task.dstPath)
            rsp.progress = 100
        else:
            rsp.progress = task.downloadSize * 90 / task.expectedSize

        if task.lastError is not None:
            rsp.success = False
            rsp.error = task.lastError
        return jsonobject.dumps(rsp)






