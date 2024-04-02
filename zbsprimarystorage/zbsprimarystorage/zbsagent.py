__author__ = 'Xingwei Yu'

import traceback
import pprint

import zstacklib.utils.jsonobject as jsonobject

from zstacklib.utils import plugin
from zstacklib.utils import daemon

log.configure_log('/var/log/zstack/zbs-primarystorage.log')
logger = log.get_logger(__name__)


class AgentResponse(object):
    def __init__(self, success=True, error=None):
        self.success = success
        self.error = error if error else ''

    def set_error(self, error):
        self.success = False
        self.error = error


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


class ZbsAgent(plugin.TaskManager):
    ECHO_PATH = "zbs/primarystorage/echo"
    CONNECT_PATH = "/zbs/primarystorage/connect"
    GET_FACTS_PATH = "/zbs/primarystorage/facts"
    CHECK_POOL_PATH = "/zbs/primarystorage/checkpool"
    INIT_PATH = "/zbs/primarystorage/init"

    http_server = http.HttpServer(port=7763)
    http_server.logfile_path = log.get_logfile_path()

    def __init__(self):
        super(ZbsAgent, self).__init__()
        self.http_server.register_async_uri(self.ECHO_PATH, self.echo)
        self.http_server.register_async_uri(self.CONNECT_PATH, self.connect)
        self.http_server.register_async_uri(self.GET_FACTS_PATH, self.get_facts)
        self.http_server.register_async_uri(self.CHECK_POOL_PATH, self.check_pool)
        self.http_server.register_async_uri(self.INIT_PATH, self.init)

    @replyerror
    def echo(self, req):
        logger.debug('get echoed')
        return ''

    @replyerror
    def connect(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        rsp = AgentResponse()

        return jsonobject.dumps(rsp)

    @replyerror
    def get_facts(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        rsp = AgentResponse()

        return jsonobject.dumps(rsp)

    @replyerror
    def check_pool(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        rsp = AgentResponse()

        return jsonobject.dumps(rsp)

    @replyerror
    def init(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])

        rsp = AgentResponse()

        return jsonobject.dumps(rsp)


class ZbsDaemon(daemon.Daemon):
    def __init__(self, pidfile, py_process_name):
        super(ZbsDaemon, self).__init__(pidfile, py_process_name)

    def run(self):
        self.agent = ZbsAgent()
        self.agent.http_server.start()
