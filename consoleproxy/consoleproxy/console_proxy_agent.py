from zstacklib.utils import plugin
from zstacklib.utils import http
from zstacklib.utils import log
from zstacklib.utils import jsonobject
from zstacklib.utils import daemon
from zstacklib.utils import linux
from zstacklib.utils import filedb
from zstacklib.utils import lock
from zstacklib.utils.bash import bash_roe
import os
import os.path
import time
import traceback
import pprint
import functools

from consoleproxy.plugins.vnc import ConsoleTokenFile, ConsoleTokenFileController, VncPlugin
from consoleproxy.plugins.nginx import NginxPlugin

logger = log.get_logger(__name__)


class AgentResponse(object):
    def __init__(self, success=True, error=None):
        self.success = success
        self.error = error if error else ''


class AgentCommand(object):
    def __init__(self):
        pass


class EstablishProxyCmd(AgentCommand):
    def __init__(self):
        super(EstablishProxyCmd, self).__init__()
        self.token = None
        self.targetSchema = None
        self.targetHostname = None
        self.targetPort = None
        self.proxyHostname = None
        self.vmUuid = None
        self.scheme = None
        self.idleTimeout = None
        self.tlsVersion = None


class EstablishProxyRsp(AgentResponse):
    def __init__(self):
        super(EstablishProxyRsp, self).__init__()
        self.proxyPort = None
        self.token = None


class CheckAvailabilityCmd(AgentCommand):
    def __init__(self):
        super(CheckAvailabilityCmd, self).__init__()
        self.proxyHostname = None
        self.proxyPort = None
        self.targetPort = None
        self.targetHostname = None
        self.targetSchema = None
        self.scheme = None
        self.token = None
        self.proxyIdentity = None
        self.expiredDate = None


class CheckAvailabilityRsp(AgentResponse):
    def __init__(self):
        super(CheckAvailabilityRsp, self).__init__()
        self.available = None


def replyerror(func):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            content = traceback.format_exc()
            err = '%s\n%s\nargs:%s' % (str(e), content, pprint.pformat([args, kwargs]))
            rsp = AgentResponse()
            rsp.success = False
            rsp.error = str(e)
            logger.warn(err)
            return jsonobject.dumps(rsp)

    return wrap


class ConsoleProxyError(Exception):
    ''' console proxy error '''


class ConsoleProxyAgent(object):

    PORT = 7758
    http_server = http.HttpServer(PORT)
    http_server.logfile_path = log.get_logfile_path()

    CHECK_AVAILABILITY_PATH = "/console/check"
    ESTABLISH_PROXY_PATH = "/console/establish"
    DELETE_PROXY_PATH = "/console/delete"
    PING_PATH = "/console/ping"

    TOKEN_FILE_DIR = "/var/lib/zstack/consoleProxy/"
    PROXY_LOG_DIR = "/var/log/zstack/consoleProxy/"
    DB_NAME = "consoleProxy"

    BM2_INSTANCE_NGINX_CONF_DIR = "/var/lib/zstack/nginx/baremetal/v2/management_node/"

    def __init__(self):
        self.http_server.register_async_uri(self.CHECK_AVAILABILITY_PATH, self.check_proxy_availability)
        self.http_server.register_async_uri(self.ESTABLISH_PROXY_PATH, self.establish_new_proxy)
        self.http_server.register_async_uri(self.DELETE_PROXY_PATH, self.delete)
        self.http_server.register_sync_uri(self.PING_PATH, self.ping)

        if not os.path.exists(self.PROXY_LOG_DIR):
            os.makedirs(self.PROXY_LOG_DIR, 0o755)
        if not os.path.exists(self.TOKEN_FILE_DIR):
            os.makedirs(self.TOKEN_FILE_DIR, 0o755)

        self.db = filedb.FileDB(self.DB_NAME)
        self.token_ctrl = ConsoleTokenFileController()
        self.vnc_plugin = VncPlugin(self.db, self.token_ctrl)
        self.nginx_plugin = NginxPlugin()

    def _check_proxy_availability(self, args):
        targetSchema = args['targetSchema']
        if targetSchema == 'vnc':
            return self._check_vnc_proxy_availability(args)
        if targetSchema == 'http':
            return self._check_http_proxy_availability(args)
        return False

    def _check_vnc_proxy_availability(self, args):
        return self.vnc_plugin.check_availability(args)

    def _check_http_proxy_availability(self, args):
        return self.nginx_plugin.check_availability(args)

    @replyerror
    def ping(self, req):
        return jsonobject.dumps(AgentResponse())

    @replyerror
    def check_proxy_availability(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        ret = self._check_proxy_availability({
            'proxyPort': cmd.proxyPort,
            'targetSchema': cmd.targetSchema,
            'targetHostname': cmd.targetHostname,
            'targetPort': cmd.targetPort,
            'token': cmd.token,
        })
        rsp = CheckAvailabilityRsp()
        rsp.available = ret
        return jsonobject.dumps(rsp)

    @replyerror
    @lock.lock('console-proxy')
    def delete(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = AgentResponse()

        if not cmd.targetSchema or cmd.targetSchema == 'vnc':
            self.vnc_plugin.delete(cmd)
            return jsonobject.dumps(rsp)

        if cmd.targetSchema == 'http':
            self.nginx_plugin.delete(cmd)
            return jsonobject.dumps(rsp)

        rsp.error = "unknown target schema %s" % cmd.targetSchema
        rsp.success = False
        return jsonobject.dumps(rsp)

    @replyerror
    @lock.lock('console-proxy')
    def establish_new_proxy(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = EstablishProxyRsp()

        def check_parameters():
            if not cmd.targetHostname:
                raise ConsoleProxyError('targetHostname cannot be null')
            if not cmd.targetPort:
                raise ConsoleProxyError('targetPort cannot be null')
            if not cmd.token:
                raise ConsoleProxyError('token cannot be null')
            if not cmd.proxyHostname:
                raise ConsoleProxyError('proxyHostname cannot be null')
            if not cmd.expiredDate:
                raise ConsoleProxyError('expiredDate cannot be null')

        def check_port_conflict():
            if cmd.proxyPort is None or str(cmd.proxyPort).isdigit() is False:
                raise ConsoleProxyError('proxyPort is None or is not a Number')
            ret, out, err = bash_roe('sysctl -n net.ipv4.ip_local_port_range')
            if ret != 0:
                logger.warn(err)
            elif out.strip() is None:
                logger.warn("None is net.ipv4.ip_local_port_range in current system")
            else:
                port_range = out.strip().split()
                if len(port_range) == 2 and str(port_range[0]).isdigit() and str(port_range[1]).isdigit():
                    if int(port_range[0]) < int(cmd.proxyPort) < int(port_range[1]):
                        logger.warn("cmd.proxyPort [%s] is probably conflict with linux ip_local_port_range: %s" % (cmd.proxyPort, port_range))

        try:
            check_parameters()
            check_port_conflict()
        except ConsoleProxyError as e:
            err = linux.get_exception_stacktrace()
            logger.warn(err)
            rsp.error = str(e)
            rsp.success = False
            return jsonobject.dumps(rsp)

        if not cmd.targetSchema or cmd.targetSchema == 'vnc':
            rsp.proxyPort = self.vnc_plugin.establish(cmd)
            rsp.token = cmd.token
            return jsonobject.dumps(rsp)

        if cmd.targetSchema == 'http':
            rsp.proxyPort = self.nginx_plugin.establish(cmd)
            rsp.token = cmd.token
            return jsonobject.dumps(rsp)

        rsp.error = "unknown target schema %s" % cmd.targetSchema
        rsp.success = False
        return jsonobject.dumps(rsp)


class ConsoleProxyDaemon(daemon.Daemon):
    def __init__(self, pidfile, py_process_name):
        super(ConsoleProxyDaemon, self).__init__(pidfile, py_process_name)

    def run(self):
        self.agent = ConsoleProxyAgent()
        self.agent.http_server.start()
