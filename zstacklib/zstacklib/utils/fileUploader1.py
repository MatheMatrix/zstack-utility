
class UploadTask(object):
    def __init__(self, taskUuid, installPath, dstPath, tmpPath):
        self.completed = False
        self.taskUuid = taskUuid
        self.installPath = installPath
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

class FileUploader:
    def __init__(self):
        self.UPLOAD_PROTO = "UPLOAD_PROTO"

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

        task = UploadTask("taskUuid", cmd.installPath)
        ImageUploadDaemon(task).start()

    def _get_upload_path(self, req):
        host = req[http.REQUEST_HEADER]['Host']
        return 'http://' + host + self.UPLOAD_IMAGE_PATH

    def download(self, req):
        if cmd.url.startswith(self.UPLOAD_PROTO):
            self._prepare_upload(cmd)
            rsp.size = 0
            rsp.uploadPath = self._get_upload_path(req)
            self._set_capacity_to_response(rsp)
            return jsonobject.dumps(rsp)