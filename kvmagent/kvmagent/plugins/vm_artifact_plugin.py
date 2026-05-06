from kvmagent import kvmagent
from kvmagent.plugins import vm_artifact
from zstacklib.utils import http
from zstacklib.utils import jsonobject


class SyncVmArtifactViewResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(SyncVmArtifactViewResponse, self).__init__()
        self.viewRoot = None
        self.artifacts = []


class DeleteVmArtifactViewResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(DeleteVmArtifactViewResponse, self).__init__()
        self.viewRoot = None


class VmArtifactViewPlugin(kvmagent.KvmAgent):
    VM_ARTIFACT_VIEW_SYNC_PATH = '/vm/artifactview/sync'
    VM_ARTIFACT_VIEW_DELETE_PATH = '/vm/artifactview/delete'
    VM_ARTIFACT_VIEW_CLEANUP_PATH = '/vm/artifactview/cleanup'

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
        relative_path = vm_artifact.get_attr(cmd, 'relativePath', None)
        if relative_path is not None:
            try:
                relative_path = vm_artifact.validate_relative_path(relative_path, 'relativePath')
            except Exception as exc:
                rsp.success = False
                rsp.error = str(exc)
                rsp.viewRoot = root
                return jsonobject.dumps(rsp)

            path = vm_artifact.safe_join(root, relative_path)
            failed_unmounts = []
            for mount in vm_artifact.list_mounts_under(path):
                if not vm_artifact.unmount_if_needed(mount):
                    failed_unmounts.append(mount)

            if failed_unmounts:
                rsp.success = False
                rsp.error = 'failed to unmount %s' % ','.join(failed_unmounts)
            elif vm_artifact.unmount_if_needed(path):
                vm_artifact.remove_path(path)
            else:
                rsp.success = False
                rsp.error = 'failed to unmount %s' % path
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

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_SYNC_PATH, self.sync_vm_artifact_view)
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_DELETE_PATH, self.delete_vm_artifact_view)
        http_server.register_async_uri(self.VM_ARTIFACT_VIEW_CLEANUP_PATH, self.cleanup_vm_artifact_view)

    def stop(self):
        pass
