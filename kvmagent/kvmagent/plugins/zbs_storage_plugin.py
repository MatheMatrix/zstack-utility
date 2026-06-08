from kvmagent import kvmagent
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import shell



logger = log.get_logger(__name__)


class CheckHostStorageConnectionRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(CheckHostStorageConnectionRsp, self).__init__()


class ZbsStoragePlugin(kvmagent.KvmAgent):
    CHECK_HOST_STORAGE_CONNECTION_PATH = "/zbs/primarystorage/check/host/connection"
    UPDATE_HOST_DEPENDENCY_PATH = "/zbs/primarystorage/host/updatedependency"

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.CHECK_HOST_STORAGE_CONNECTION_PATH, self.check_host_storage_connection)
        http_server.register_async_uri(self.UPDATE_HOST_DEPENDENCY_PATH, self.update_host_dependency)

    @kvmagent.replyerror
    @bash.in_bash
    def check_host_storage_connection(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = CheckHostStorageConnectionRsp()

        c = 'timeout 20 qemu-io -c "read 0G 4k" -f cbd {}_zbs_:/etc/zbs/client.conf'.format(cmd.path)
        r, o, e = bash.bash_roe(c)
        if r != 0:
            if linux.catch_bad_alloc_exception(r, e):
                return jsonobject.dumps(rsp)
            rsp.error = "failed to check heartbeat[%s], %s" % (cmd.path, e)
            rsp.success = False
            return jsonobject.dumps(rsp)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    @bash.in_bash
    def update_host_dependency(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = CheckHostStorageConnectionRsp()
        releasever = kvmagent.get_host_yum_release()
        packages = cmd.updatePackages.split(',')
        for package in packages:
            yum_cmd = "export YUM0={};yum --enablerepo=* clean all && " \
                      "(rpm -q {} && yum --disablerepo=* --enablerepo={} update {} -y " \
                      "|| yum --disablerepo=* --enablerepo={} install {} -y)"
            yum_cmd = yum_cmd.format(releasever, package.strip(), cmd.zstackRepo,
                                     package.strip(), cmd.zstackRepo, package.strip())
            if shell.run(yum_cmd) != 0:
                rsp.success = False
                rsp.error = "failed to update zbs host client dependency using: %s" % yum_cmd
            else:
                logger.debug("successfully run: %s" % yum_cmd)

        return jsonobject.dumps(rsp)


    def stop(self):
        pass

    def configure(self, config=None):
        if config is None:
            config = {}
        self.config = config
