from kvmagent import kvmagent
from kvmagent.plugins import vm_artifact
from kvmagent.plugins import vm_plugin
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import linux
from zstacklib.utils import log

logger = log.get_logger(__name__)


class MountModelCenterResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(MountModelCenterResponse, self).__init__()
        self.mountPoint = None


class SyncVmArtifactViewResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(SyncVmArtifactViewResponse, self).__init__()
        self.viewRoot = None
        self.artifacts = []


class DeleteVmArtifactViewResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(DeleteVmArtifactViewResponse, self).__init__()
        self.viewRoot = None


class ModelCenterPlugin(kvmagent.KvmAgent):
    MODEL_CENTER_MOUNT_PATH = '/modelcenter/mount'
    VM_ARTIFACT_VIEW_SYNC_PATH = '/vm/artifactview/sync'
    VM_ARTIFACT_VIEW_DELETE_PATH = '/vm/artifactview/delete'
    VM_ARTIFACT_VIEW_CLEANUP_PATH = '/vm/artifactview/cleanup'
    VIRTIOFS_ATTACH_PATH = '/virtiofs/attach'
    VIRTIOFS_DETACH_PATH = '/virtiofs/detach'

    @kvmagent.replyerror
    def mount_model_center(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = MountModelCenterResponse()

        mount_point = vm_artifact.get_attr(cmd, 'mountPoint')
        if not mount_point:
            mount_point = vm_artifact.model_center_mount_point(cmd.modelCenterUuid)
        else:
            mount_point = vm_artifact.ensure_under(mount_point, vm_artifact.MODEL_CENTER_ROOT, 'mountPoint')

        linux.mkdir(mount_point, 0o755)
        if not linux.is_mounted(path=mount_point):
            storage_url = vm_artifact.get_attr(cmd, 'storageUrl')
            if storage_url:
                linux.mount(storage_url, mount_point,
                            vm_artifact.get_attr(cmd, 'mountOptions'),
                            vm_artifact.get_attr(cmd, 'fsType'))

        rsp.mountPoint = mount_point
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def sync_vm_artifact_view(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = SyncVmArtifactViewResponse()

        view_root, specs = vm_artifact.sync_artifact_view(cmd.vmInstanceUuid, vm_artifact.get_attr(cmd, 'artifacts', []))
        rsp.viewRoot = view_root
        rsp.artifacts = specs
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def delete_vm_artifact_view(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = DeleteVmArtifactViewResponse()

        root = vm_artifact.vm_view_root(cmd.vmInstanceUuid)
        relative_path = vm_artifact.get_attr(cmd, 'relativePath')
        if relative_path:
            path = vm_artifact.safe_join(root, vm_artifact.validate_relative_path(relative_path, 'relativePath'))
            vm_artifact.unmount_if_needed(path)
            vm_artifact.remove_path(path)
        else:
            vm_artifact.cleanup_view(cmd.vmInstanceUuid)
        rsp.viewRoot = root
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def cleanup_vm_artifact_view(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = DeleteVmArtifactViewResponse()

        rsp.viewRoot = vm_artifact.cleanup_view(cmd.vmInstanceUuid)
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def attach_virtiofs(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = kvmagent.AgentResponse()

        vm_uuid = vm_artifact.get_attr(cmd, 'vmInstanceUuid') or vm_artifact.get_attr(cmd, 'vmUuid')
        vm = vm_plugin.get_vm_by_uuid(vm_uuid)
        vm_artifact.attach_virtiofs(vm.domain, vm_uuid, cmd.tag,
                                    vm_artifact.get_attr(cmd, 'sourcePath'),
                                    vm_artifact.get_attr(cmd, 'cache'),
                                    vm_artifact.get_attr(cmd, 'queue'))
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def detach_virtiofs(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = kvmagent.AgentResponse()

        vm_uuid = vm_artifact.get_attr(cmd, 'vmInstanceUuid') or vm_artifact.get_attr(cmd, 'vmUuid')
        vm = vm_plugin.get_vm_by_uuid(vm_uuid)
        detached = vm_artifact.detach_virtiofs(vm.domain, vm.domain_xmlobject, cmd.tag)
        if not detached:
            logger.debug('virtiofs device[tag:%s] is not attached to vm[uuid:%s], skip detach' % (cmd.tag, vm_uuid))
        return jsonobject.dumps(rsp)

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.MODEL_CENTER_MOUNT_PATH, self.mount_model_center)
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_SYNC_PATH, self.sync_vm_artifact_view)
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_DELETE_PATH, self.delete_vm_artifact_view)
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_CLEANUP_PATH, self.cleanup_vm_artifact_view)
        http_server.register_async_uri(self.VIRTIOFS_ATTACH_PATH, self.attach_virtiofs)
        http_server.register_async_uri(self.VIRTIOFS_DETACH_PATH, self.detach_virtiofs)

    def stop(self):
        pass
