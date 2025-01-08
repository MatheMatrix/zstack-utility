import os

import tempfile
import shutil

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
        packages = ["dpdk", "ovs", "ovn"]
        dpdkNics = ovn.getAllDpdkNic()
        for nic in dpdkNics:
            if nic.driver == "mlx5_core":
                # packages = ["ofed", "dpdk", "ovs", "ovn"]
                packages = ["dpdk", "ovs", "ovn"]
                break

        temp_dir = tempfile.mkdtemp()
        for pack in packages:
            # TODO: add arch and os
            r, _, e = bash.bash_roe("wget --recursive --no-parent -q --directory-prefix=%s http://%s/chassis/%s/"
                                    % (temp_dir, controllerIp, pack))
            if r != 0:
                rsp.success = False
                rsp.error = "fail to download package {} from ovn controller, because: {}".format(pack, e)
                break

            installFile = os.path.join(temp_dir, cmd.ovnControllerIp, "chassis", pack, "install.sh")
            r, _, e = bash.bash_roe("bash -x {}".format(installFile))
            if r != 0:
                rsp.success = False
                rsp.error = "fail to install package {} from ovn controller, because: {}".format(pack, e)
                break
            else:
                logger.debug("successfully install package {} from ovn controller".format(pack))

        shutil.rmtree(temp_dir)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    @bash.in_bash
    def uninstall_ovn_package(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnUninstallPackageResponse()

        # we will not uninstall ovn package
        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    @bash.in_bash
    def start_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStartServiceResponse()

        # uio_pci_generic is used for nest virtual
        dpdkDriver = "vfio-pci"
        ret = bash.bash_r("lscpu | grep -i \"Hypervisor vendor\"")
        if ret == 0:
            dpdkDriver = "uio_pci_generic"

        ret, _, e = bash.bash_roe("modprobe {driver}".format(driver=dpdkDriver))
        if ret != 0:
            rsp.success = False
            rsp.error = "load kernel mode {driver} failed {err}".format(driver=dpdkDriver, err=e)
            return jsonobject.dumps(rsp)

        """ TODO, this code should be run in huge memory api """
        r, _, e = bash.bash_roe("sysctl -w vm.nr_hugepages={nr_hugepages}".format(nr_hugepages=cmd.hugePageNumber))
        if r != 0:
            rsp.success = False
            rsp.error = "sysctl -w vm.nr_hugepages={nr_hugepages}, failed: {err}" \
                .format(nr_hugepages=cmd.hugePageNumber, err=e)
            return jsonobject.dumps(rsp)

        # 1. bond nics to dpdk driver
        dpdkNics = ovn.getAllDpdkNic()
        targetDpdkNic = []

        logger.debug("starting change nic driver")

        for nicName in cmd.nicNames:
            found = False
            pciAddress = ""
            driver = ""
            for dpdkNic in dpdkNics:
                if dpdkNic.name == nicName:
                    found = True
                    driver = dpdkNic.driver
                    pciAddress = dpdkNic.pciAddress
                    targetDpdkNic.append(dpdkNic)
                    break

            if not found:
                rsp.success = False
                rsp.error = "nic %s is not found by dpdk-devbind.py"
                return jsonobject.dumps(rsp)

            if driver == "mlx5_core":
                # mellanox nic(like cx-5) does not need vfio driver
                continue

            if driver == dpdkDriver:
                logger.debug("nic {} already bond to dpdk driver{}".format(nicName, dpdkDriver))
                continue

            # for nested vm, the driver is should be uio_pci_generic
            r, _, e = bash.bash_roe(ovn.DevBindBin + " -b {driver} {pciAddress}"
                                    .format(driver=dpdkDriver, pciAddress=pciAddress))
            if r != 0:
                rsp.success = False
                rsp.error = ovn.DevBindBin + " -b {driver} {pciAddress} failed: {err}"\
                    .format(driver=dpdkDriver, pciAddress=pciAddress, err=e)
                return jsonobject.dumps(rsp)

            logger.debug("change change nic [pci address: {}] driver to {}".format(pciAddress, dpdkDriver))

        r, _, e = bash.bash_roe("systemctl restart ovsdb-server;systemctl start openvswitch;systemctl start "
                                "ovn-controller")
        if r != 0:
            rsp.success = False
            rsp.error = "start ovn service, fail {err}".format(err=e)
            return jsonobject.dumps(rsp)

        logger.debug("success start ovn services")
        """
        # ovs-vsctl set bridge br-int datapath_type=netdev
        # ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true
        # ovs-vsctl set Open_vSwitch . external-ids:ovn-remote="tcp:172.25.116.181:6642" external-ids:ovn-encap-ip="172.25.16.161" external-ids:ovn-encap-type=vxlan external-ids:system-id=172-25-116-181
        # ovs-ctl start
        # ovs-ctl restart
        """
        # TODO only dpdk is supported, ovs-kernel is not supported
        r, _, e = bash.bash_roe("ovs-vsctl set bridge br-int datapath_type=netdev;"
                                "ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true")
        if r != 0:
            # TODO: rollback nic driver
            rsp.success = False
            rsp.error = "init ovs config, failed: {err}".format(err=e)
            return jsonobject.dumps(rsp)

        logger.debug("set ovs-ctl parameters")

        # create external bridge: default name: br-phy
        # TODO: add ovs bond
        r, _, e = bash.bash_roe("ovs-vsctl --may-exist add-br {br_ex};"
                                "ovs-vsctl set Bridge br-phy datapath_type=netdev;"
                                "ovs-vsctl set bridge br-phy fail-mode=standalone;"
                                "ovs-vsctl add-port br-phy {nic};"
                                "ovs-vsctl set Interface {nic} type=dpdk options:dpdk-devargs={pciAddress};"
                                .format(br_ex=cmd.brExName, nic=targetDpdkNic[0].name, pciAddress=targetDpdkNic[0].pciAddress))
        if r != 0:
            # TODO: rollback nic driver
            rsp.success = False
            rsp.error = "init ovs config, failed: %s" % e
            return jsonobject.dumps(rsp)

        logger.debug("create br-phy")

        r, _, e = bash.bash_roe("ovs-vsctl set Open_vSwitch . external-ids:ovn-remote={ovn_remote} "
                                "external-ids:ovn-encap-ip={ovn_encap_ip} "
                                "external-ids:ovn-encap-type={ovn_encap_type} "
                                "external-ids:ovn-bridge-mappings=flat:{br_ex} "
                                .format(ovn_remote=cmd.ovnRemoteConnection,
                                        ovn_encap_ip=cmd.ovnEncapIP,
                                        ovn_encap_type=cmd.ovnEncapType,
                                        br_ex=cmd.brExName))
        if r != 0:
            # TODO: rollback nic driver
            rsp.success = False
            rsp.error = "init ovs config, failed: %s" % e
            return jsonobject.dumps(rsp)

        logger.debug("set ovs external-ids")

        r, _, e = bash.bash_roe("systemctl restart ovsdb-server;systemctl start openvswitch;systemctl start "
                                "ovn-controller")
        if r != 0:
            rsp.success = False
            rsp.error = "start ovn service, fail {err}".format(err=e)
            return jsonobject.dumps(rsp)

        logger.debug("restart ovs services")

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    @bash.in_bash
    def stop_ovn_service(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = OvnStopServiceResponse()

        r, _, e = bash.bash_roe("systemctl stop ovsdb-server;"
                                "systemctl stop openvswitch;"
                                "systemctl stop ovn-controller")
        if r != 0:
            rsp.success = False
            rsp.error = "stop ovn service, fail {err}".format(err=e)

        # TODO change nic driver

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
