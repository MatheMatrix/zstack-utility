"""
AI Model Mount Plugin for KVM Agent

ZSTAC-83157: Mount AI models to VMs using JuiceFS subpath mounting
"""
import shlex

from kvmagent import kvmagent
from kvmagent.plugins import vm_plugin
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils.qga import VmQga

log.configure_log('/var/log/zstack/zstack-kvmagent.log')
logger = log.get_logger(__name__)


class KvmAttachModelMsg(kvmagent.AgentCommand):
    def __init__(self):
        super(KvmAttachModelMsg, self).__init__()
        self.vmInstanceUuid = None
        self.zdfsUrl = None
        self.juicefsSubdir = None  # e.g., "models/Qwen/2.5b"
        self.mountPath = None     # e.g., "/mnt/models"


class KvmAttachModelReply(kvmagent.AgentResponse):
    def __init__(self):
        super(KvmAttachModelReply, self).__init__()


class KvmDetachModelMsg(kvmagent.AgentCommand):
    def __init__(self):
        super(KvmDetachModelMsg, self).__init__()
        self.vmInstanceUuid = None
        self.mountPath = None


class KvmDetachModelReply(kvmagent.AgentResponse):
    def __init__(self):
        super(KvmDetachModelReply, self).__init__()


class AIModelMountPlugin(kvmagent.KvmAgent):
    ATTACH_MODEL_PATH = "/aimodel/attach"
    DETACH_MODEL_PATH = "/aimodel/detach"

    def __init__(self):
        self.plugin_uuid = None

    def configure(self, config):
        self.config = config

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.ATTACH_MODEL_PATH, self.attach_model)
        http_server.register_async_uri(self.DETACH_MODEL_PATH, self.detach_model)
        logger.debug("AI Model Mount Plugin started")

    def stop(self):
        pass

    def _validate_vm_and_qga(self, vm_uuid):
        """
        Validate VM exists and Qemu Guest Agent is running.

        Returns:
            tuple: (vm, qga) if validation passes

        Raises:
            Exception: If VM not found or QGA not running
        """
        vm = vm_plugin.get_vm_by_uuid(vm_uuid, exception_if_not_existing=False)
        if not vm:
            raise Exception("VM not found: %s" % vm_uuid)

        qga = VmQga(vm.domain)
        if qga.state != VmQga.QGA_STATE_RUNNING:
            raise Exception("Qemu Guest Agent is not running on VM: %s" % vm_uuid)

        return vm, qga

    @kvmagent.replyerror
    def attach_model(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        logger.debug("Received KvmAttachModelMsg: vm=%s, mount=%s, subdir=%s" %
                     (cmd.vmInstanceUuid, cmd.mountPath, cmd.juicefsSubdir))

        rsp = KvmAttachModelReply()

        try:
            # Validate VM and QGA
            vm, qga = self._validate_vm_and_qga(cmd.vmInstanceUuid)

            # Execute mount command in guest (optimized: single bash command)
            self._mount_juicefs_in_guest(qga, cmd)

            rsp.success = True
            return jsonobject.dumps(rsp)

        except Exception as e:
            logger.error("Failed to attach model to VM %s: %s" % (cmd.vmInstanceUuid, str(e)))
            rsp.error = str(e)
            rsp.success = False
            return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def detach_model(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        logger.debug("Received KvmDetachModelMsg: vm=%s, mount=%s" %
                     (cmd.vmInstanceUuid, cmd.mountPath))

        rsp = KvmDetachModelReply()

        try:
            # Validate VM and QGA
            vm, qga = self._validate_vm_and_qga(cmd.vmInstanceUuid)

            # Execute unmount command in guest
            self._unmount_juicefs_in_guest(qga, cmd.mountPath)

            rsp.success = True
            return jsonobject.dumps(rsp)

        except Exception as e:
            logger.error("Failed to detach model from VM %s: %s" % (cmd.vmInstanceUuid, str(e)))
            rsp.error = str(e)
            rsp.success = False
            return jsonobject.dumps(rsp)

    def _mount_juicefs_in_guest(self, qga, cmd):
        """
        Mount JuiceFS with subpath in guest OS using Qemu Guest Agent.

        This method executes a single bash command that:
        1. Creates mount point directory if not exists
        2. Executes juicefs mount command with --subdir
        3. Verifies mount succeeded

        Optimized: Uses inline bash command instead of temporary script file,
        reducing QGA round-trips from 4 to 1.
        """
        # Build bash command with proper quoting to prevent injection
        mount_cmd = (
            'mkdir -p {mount} && '
            'juicefs mount {url} {mount} --subdir {subdir} --read-only -d && '
            'mountpoint -q {mount}'
        ).format(
            mount=shlex.quote(cmd.mountPath),
            url=shlex.quote(cmd.zdfsUrl),
            subdir=shlex.quote(cmd.juicefsSubdir)
        )

        exitcode, output = qga.guest_exec_cmd_no_exitcode(mount_cmd)
        if exitcode != 0:
            raise Exception("Failed to mount JuiceFS: %s" % output)

        logger.info(
            "Successfully mounted JuiceFS subdir %s to %s for VM %s" %
            (cmd.juicefsSubdir, cmd.mountPath, cmd.vmInstanceUuid)
        )

    def _unmount_juicefs_in_guest(self, qga, mount_point):
        """
        Unmount JuiceFS from guest OS using Qemu Guest Agent.

        Note: Uses shlex.quote() to prevent shell injection.
        """
        # Unmount command with proper quoting
        unmount_cmd = "umount %s" % shlex.quote(mount_point)
        exitcode, output = qga.guest_exec_cmd_no_exitcode(unmount_cmd)

        if exitcode != 0:
            logger.warn("Failed to unmount %s: %s" % (mount_point, output))
            # Don't raise exception, unmount may already be done

        logger.info("Successfully unmounted %s" % mount_point)

