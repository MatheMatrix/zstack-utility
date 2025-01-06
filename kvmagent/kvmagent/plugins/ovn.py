import os

import tempfile

from kvmagent import kvmagent
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import http
from zstacklib.utils import ovn
from zstacklib.utils import bash

OVN_INSTALL_PACKAGE = '/network/ovn/install'
OVN_UNINSTALL_PACKAGE = '/network/ovn/uninstall'
OVN_START_SERVICE = '/network/ovn/start'
OVN_STOP_SERVICE = '/network/ovn/stop'
OVN_ADD_PORT = '/network/ovn/addport'
OVN_DEL_PORT = '/network/ovn/delport'

logger = log.get_logger(__name__)


class OvnInstallPackageCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnInstallPackageCmd, self).__init__()
        self.ovnControllerIp = None


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


class OvnAddPortCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnAddPortCmd, self).__init__()
        self.vswitchType = None
        self.nicMap = None


class OvnAddPortResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnAddPortResponse, self).__init__()


class OvnDelPortCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(OvnDelPortCmd, self).__init__()
        self.vswitchType = None
        self.nicMap = None


class OvnDelPortResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(OvnDelPortResponse, self).__init__()


class OvnNetworkPlugin(kvmagent.KvmAgent):

    @kvmagent.replyerror
    @bash.in_bash
    def install_ovn_package(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnInstallPackageResponse()

        controllerIp = cmd.ovnControllerIp
        '''
            4 bundle of packages need to be installed: ofed, dpdk, ovs, ovn
        '''
        packages = ["ofed", "dpdk", "ovs", "ovn"]
        temp_dir = tempfile.mkdtemp()
        for pack in packages:
            # TODO: add arch and os
            r, _, e = bash.bash_roe("wget --recursive --no-parent  --directory-prefix=%s http://%s/%s/"
                                    % (temp_dir, controllerIp, pack))
            if r != 0:
                rsp.success = False
                rsp.error = "fail to download package % from ovn controller, because: %s" % (pack, e)
                break

            installFile = os.path.join(temp_dir, pack, "install.sh")
            r, _, e = bash.bash_roe("bash -x %s" % installFile)
            if r != 0:
                rsp.success = False
                rsp.error = "fail to install package % from ovn controller, because: %s" % (pack, e)
                break
            else:
                logger.debug("successfully install package from ovn controller" % pack)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def uninstall_ovn_package(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnUninstallPackageResponse()

        # we will not uninstall ovn package
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def start_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStartServiceResponse()

        # 1. bond nics to vfio driver
        r, o, e = bash.bash_roe("dpdk-devbind.py --status-dev net | grep if=")
        if r != 0:
            rsp.success = False
            rsp.error = "dpdk-devbind.py --status-dev net | grep if=, failed %s" % e
            return jsonobject.dumps(rsp)

        nicDriverMap = {}
        lines = o.spit("\n")
        for l in lines:
            l = l.strip()
            if l == "":
                continue

            name = ""
            driver = ""
            items = l.spilt(" ")
            for item in items:
                if item.startWith("if="):
                    name = item.split("=")[1]
                if item.startWith("drv="):
                    driver = item.split("=")[1]
            logger.debug("ethernet nic[%s] pci: %s, driver: %s" % (items[0], name, driver))
            nicDriverMap[name] = driver

        r, _, e = bash.bash_roe("sysctl -w vm.nr_hugepages=%d" % cmd.nr_hugepages)
        if r != 0:
            rsp.success = False
            rsp.error = "sysctl -w vm.nr_hugepages=%d, failed: %s" % (cmd.nr_hugepages, e)
            return jsonobject.dumps(rsp)

        for nic in cmd.nics:
            if nic not in nicDriverMap:
                rsp.success = False
                rsp.error = "nic %s is not found by dpdk-devbind.py"
                return jsonobject.dumps(rsp)

            driver = nicDriverMap[nic]
            if driver == "mlx5_core":
                # mellanox nic(like cx-5) does not need vfio driver
                continue

            r, _, e = bash.bash_roe("dpdk-devbind.py -b vfio-pci %s" % nic)
            if r != 0:
                rsp.success = False
                rsp.error = "dpdk-devbind.py -b vfio-pci %s, fail %s" % (nic, e)
                return jsonobject.dumps(rsp)

            logger.debug("dpdk-devbind.py -b vfio-pci %s successfully" % nic)

        r, _, e = bash.bash_roe("systemctl restart ovsdb-server;systemctl start openvswitch;systemctl start "
                                "ovn-controller")
        if r != 0:
            rsp.success = False
            rsp.error = "start ovn service, fail %s" % (nic, e)
            return jsonobject.dumps(rsp)

        """
        # sysctl -w vm.nr_hugepages=8192
        # ovs-vsctl set bridge br-int datapath_type=netdev
        # ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true
        # ovs-vsctl set Open_vSwitch . external-ids:ovn-remote="tcp:172.25.116.181:6642" external-ids:ovn-encap-ip="172.25.16.161" external-ids:ovn-encap-type=vxlan external-ids:system-id=172-25-116-181
        # ovs-ctl start
        # ovs-ctl restart
        """
        r, _, e = bash.bash_roe("ovs-vsctl set bridge br-int datapath_type=netdev;ovs-vsctl --no-wait set "
                                "Open_vSwitch . other_config:dpdk-init=true" % cmd.nr_hugepages)
        if r != 0:
            # TODO: rollback nic driver
            rsp.success = False
            rsp.error = "init ovs config, failed: %s" % e
            return jsonobject.dumps(rsp)

        r, _, e = bash.bash_roe("ovs-vsctl set bridge br-int datapath_type=netdev;ovs-vsctl --no-wait set "
                                "Open_vSwitch . other_config:dpdk-init=true")
        if r != 0:
            # TODO: rollback nic driver
            rsp.success = False
            rsp.error = "init ovs config, failed: %s" % e
            return jsonobject.dumps(rsp)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def stop_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStopServiceResponse()

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def ovn_add_port(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        logger.debug("cmd: %s: %s" % (cmd, cmd.__dict__))
        logger.debug("cmd nicMap: %s: %s" % (cmd.nicMap, cmd.nicMap.__dict__))
        vsctl = ovn.VsCtl()
        for nicName, srcPath in cmd.nicMap.__dict__.items():
            vsctl.addVnic(nicName, srcPath)
        rsp = OvnAddPortResponse()

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def ovn_del_port(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnDelPortResponse()

        logger.debug("cmd: %s: %s" % (cmd, cmd.__dict__))
        logger.debug("cmd nicMap: %s: %s" % (cmd.nicMap, cmd.nicMap.__dict__))
        vsctl = ovn.VsCtl()
        for nicName, _ in cmd.nicMap.__dict__.items():
            vsctl.delVnic(nicName)

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
        http_server.register_async_uri(
            OVN_ADD_PORT, self.ovn_add_port)
        http_server.register_async_uri(
            OVN_DEL_PORT, self.ovn_del_port)

    def stop(self):
        http.AsyncUirHandler.STOP_WORLD = True
