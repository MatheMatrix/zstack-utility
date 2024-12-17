

import os

from kvmagent import kvmagent
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import http

OVN_INSTALL_PACKAGE = '/network/ovn/install'
OVN_UNINSTALL_PACKAGE = '/network/ovn/uninstall'
OVN_START_SERVICE = '/network/ovn/start'
OVN_STOP_SERVICE = '/network/ovn/stop'

logger = log.get_logger(__name__)


class OvnInstallPackageCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnInstallPackageCmd, self).__init__()


class OvnInstallPackageResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnInstallPackageResponse, self).__init__()


class OvnUninstallPackageCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnUninstallPackageCmd, self).__init__()


class OvnUninstallPackageResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnUninstallPackageResponse, self).__init__()


class OvnStartServiceCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnStartServiceCmd, self).__init__()
        self.physicalInterfaceName = None
        self.bridgeName = None


class OvnStartServiceResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnStartServiceResponse, self).__init__()


class OvnStopServiceCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnStopServiceCmd, self).__init__()
        self.physicalInterfaceName = None
        self.bridgeName = None


class OvnStopServiceResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnStopServiceResponse, self).__init__()


class OvnNetworkPlugin(kvmagent.KvmAgent):

    @kvmagent.replyerror
    def install_ovn_package(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnInstallPackageResponse()

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def uninstall_ovn_package(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnUninstallPackageResponse()

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def start_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStartServiceResponse()

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def stop_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStopServiceResponse()

        return jsonobject.dumps(rsp)

    def start(self):

        http_server = kvmagent.get_http_server()

        http_server.register_async_uri(
            OVN_INSTALL_PACKAGE, self.install_ovn_package)
        http_server.register_async_uri(
            OVN_UNINSTALL_PACKAGE, self.uninstall_ovn_package)
        http_server.register_async_uri(
            OVN_START_SERVICE, self.start_ovn_service)
        http_server.register_async_uri(
            OVN_STOP_SERVICE, self.stop_ovn_service)

    def stop(self):
        http.AsyncUirHandler.STOP_WORLD = True



