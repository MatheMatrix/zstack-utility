import hashlib

from zstacklib.utils import linux, lock
from zstacklib.utils import log
from cherrypy.lib.static import _serve_fileobj
from cherrypy._cpreqbody import Entity, Part, SizedReader
from cherrypy._cprequest import Request

logger = log.get_logger(__name__)

class UploadTasks(object):
    MAX_RECORDS = 80
    lock_name = 'lock_name'

    def __init__(self):
        self.tasks = {}

    def _expunge_oldest_task(self):
        key, ts = '',  linux.get_current_timestamp()
        for k in self.tasks:
            task = self.tasks[k]

            if task.is_running():
                continue

            if task.lastOpTime < ts:
                key, ts = k, task.lastOpTime

        if key != '': del(self.tasks[key])

    @lock.lock(lock_name)
    def add_task(self, t):
        # type: (UploadTask) -> None
        if len(self.tasks) > self.MAX_RECORDS:
            self._expunge_oldest_task()
        self.tasks[t.imageUuid] = t

    @lock.lock(lock_name)
    def get_task(self, image_uuid):
        # type: (str) -> UploadTask
        return self.tasks.get(image_uuid)

    def upload(self, req):
        upload_param = self.get_upload_param(req.headers)
        task = self.get_upload_task(upload_param)
        self.upload_slice(req.body, upload_param, task)

        if task.allow_image_completing():
            pool, img_name = task.dstPath.split('/')
            ioctx = self.get_ioctx(pool)
            complete_upload(task, ioctx)

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

        up = upload_task.UploadParam()
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
        task = upload_tasks.get_task(param.image_uuid)
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

        pool, _ = task.tmpPath.split('/')
        ioctx = self.get_ioctx(pool)

        try:
            stream_body(entity, boundary, param, task, ioctx)
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

    def complete_upload(task, ioctx):
        # type: (UploadTask) -> None
        try:
            file_format = linux.get_img_fmt('rbd:' + task.tmpPath)
        except Exception as e:
            task.fail('upload image %s failed: %s' % (task.imageUuid, str(e)))
            shell.run('rbd rm %s' % task.tmpPath)
            return

        if file_format == 'qcow2' and linux.qcow2_get_backing_file('rbd:' + task.tmpPath):
            task.fail('Qcow2 image %s has backing file' % task.imageUuid)
            shell.run('rbd rm %s' % task.tmpPath)
            return

        if file_format in ['qcow2', 'vmdk']:
            conf_path = None
            try:
                with open('/etc/ceph/ceph.conf', 'r') as fd:
                    conf = fd.read()
                    conf = '%s\n%s\n' % (conf, 'rbd default format = 2')
                    conf_path = linux.write_to_temp_file(conf)

                shell.check_run('%s -f %s -O rbd rbd:%s rbd:%s:conf=%s' % (qemu_img.subcmd('convert'), file_format,
                                                                           task.tmpPath, task.dstPath, conf_path))
            except Exception as e:
                task.fail('cannot convert %s image %s to rbd' % (file_format, task.imageUuid))
                logger.warn('convert image %s failed: %s', (task.imageUuid, str(e)))
                return
            finally:
                shell.run('rbd rm %s' % task.tmpPath)
                if conf_path:
                    os.remove(conf_path)
        else:
            shell.check_run('rbd mv %s %s' % (task.tmpPath, task.dstPath))

        if task.lastError:
            raise Exception(task.lastError)

        _, img_name = task.dstPath.split('/')
        task.image_format = get_image_format_from_header(ioctx, img_name)
        task.success()

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

    def stream_body(entity, boundary, param, task, ioctx):
        # type: (Entity, str, UploadParam, UploadTask, rados.Ioctx) -> None

        _, image_name = task.tmpPath.split('/')
        task.create_image_if_not_exists(ioctx, image_name)
        image_obj = ImageFileObject(rbd.Image(ioctx, image_name))
        image_obj.seek(param.slice_offset)

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

class UploadParam(object):
    def __init__(self):
        self.image_uuid = None
        self.image_size = 0
        self.slice_index = 0
        self.slice_offset = 0
        self.slice_size = 0
        self.slice_md5 = None

class UploadTask(object):
    def __init__(self, imageUuid, installPath, dstPath, tmpPath):
        self.completed = False
        self.imageUuid = imageUuid
        self.installPath = installPath
        self.dstPath = dstPath # without 'ceph://'
        self.tmpPath = tmpPath # where image firstly imported to
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
        return not(self.completed or self.is_started())

    def renew(self):
        self.lastOpTime = linux.get_current_timestamp()

    def all_slice_uploaded(self):
        return 0 < self.slice_count == len(self.slice_uploaded)

    def checked_download_size(self):
        for i in range(self.slice_count):
            if i not in self.slice_uploaded:
                return i * self.slice_size

        return self.expectedSize

    def create_image_if_not_exists(self, ioctx, image_name):
        # type: (rados.Ioctx, str) -> None

        if self.image_created:
            return

        with lock.NamedLock("upload-image-%s" % self.imageUuid):
            if not self.image_created:
                rbd.RBD().create(ioctx, image_name, self.expectedSize)
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

