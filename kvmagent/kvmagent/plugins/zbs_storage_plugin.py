from kvmagent import kvmagent
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import shell


logger = log.get_logger(__name__)


class CheckHostStorageConnectionRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(CheckHostStorageConnectionRsp, self).__init__()


class ZbsStoragePlugin(kvmagent.KvmAgent):
    CHECK_HOST_STORAGE_CONNECTION_PATH = "/zbs/primarystorage/check/host/connection"

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.CHECK_HOST_STORAGE_CONNECTION_PATH, self.check_host_storage_connection)

    @kvmagent.replyerror
    def check_host_storage_connection(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = CheckHostStorageConnectionRsp()

        heartbeat_check = shell.ShellCmd('qemu-io -c "read 0G 4k" -f cbd {}_zbs_:/etc/zbs/client.conf'.format(cmd.path))
        heartbeat_check(False)
        if heartbeat_check.return_code != 0:
            rsp.error = "failed to check heartbeat[%s], %s" % (cmd.path, heartbeat_check.stderr)
            rsp.success = False
            return jsonobject.dumps(rsp)

        return jsonobject.dumps(rsp)


    def stop(self):
        pass

    def configure(self, config):
        self.config = config
