'''

@author: haibiao.xiao
'''
import os
import shutil
import time
import yaml
import glob
import uuid
import re
from enum import Enum, unique

from zstacklib.utils import log
from zstacklib.utils import shell
from zstacklib.utils import bash

logger = log.get_logger(__name__)

CtlBin = "/usr/bin/ovs-vsctl "
DevBindBin = "/usr/bin/dpdk-devbind.py "


class OvsError(Exception):
    '''ovs error'''


class OvsDpdkNic:
    def __init__(self):
        self.name = ""
        self.pciAddress = ""
        self.driver = ""


@bash.in_bash
def getAllDpdkNic():
    ret = []
    r, o, e = bash.bash_roe(DevBindBin + " --status-dev net | grep drv= | grep -v 'Virtual Function'")
    if r != 0:
        logger.debug(DevBindBin + " --status-dev net | grep drv=, failed {err}".format(err=e))
        return ret

    lines = o.split("\n")
    for line in lines:
        line = line.strip()
        if line == "":
            continue

        nic = OvsDpdkNic()
        items = line.split(" ")
        nic.pciAddress = items[0]
        for item in items:
            if item.startswith("if="):
                nic.name = item.split("=")[1]
            if item.startswith("drv="):
                nic.driver = item.split("=")[1]

        logger.debug("dpdk nic[%s] name: %s, driver: %s" % (nic.pciAddress, nic.name, nic.driver))
        ret.append(nic)

    return ret


@bash.in_bash
def changeNicToDpdkDriver(nicNamePciAddressMap):
    # uio_pci_generic is used for nest virtual
    dpdkDriver = "vfio-pci"
    ret = bash.bash_r("lscpu | grep -i \"Hypervisor vendor\"")
    if ret == 0:
        dpdkDriver = "uio_pci_generic"

    ret, _, e = bash.bash_roe("modprobe {driver}".format(driver=dpdkDriver))
    if ret != 0:
        return ret, e

    dpdkNics = getAllDpdkNic()
    targetDpdkNic = []

    logger.debug("starting change nic driver")

    for nicName, pciAddress in nicNamePciAddressMap.__dict__.items():
        found = False
        driver = ""
        for dpdkNic in dpdkNics:
            if dpdkNic.pciAddress == pciAddress:
                found = True
                driver = dpdkNic.driver
                targetDpdkNic.append(dpdkNic)
                break

        if not found:
            return 1, "nic [pci address: %s] is not found by dpdk-devbind.py".format(pciAddress)

        if driver == "mlx5_core":
            # mellanox nic(like cx-5) does not need vfio driver
            continue

        if driver == dpdkDriver:
            logger.debug("nic {} already bond to dpdk driver{}".format(nicName, dpdkDriver))
            continue

        # for nested vm, the driver is should be uio_pci_generic
        r, _, e = bash.bash_roe(DevBindBin + " -b {driver} {pciAddress}"
                                .format(driver=dpdkDriver, pciAddress=pciAddress))
        if r != 0:
            return r, e

        logger.debug("change change nic [pci address: {}] driver to {}".format(pciAddress, dpdkDriver))

    return 0, ""

@bash.in_bash
def restoreNicDriver(nicNamePciAddressMap, nicNameDriverMap):
    dpdkNics = getAllDpdkNic()
    targetDpdkNic = []

    logger.debug("starting change nic driver")

    for nicName, pciAddress in nicNamePciAddressMap.__dict__.items():
        found = False
        driver = ""
        for dpdkNic in dpdkNics:
            if dpdkNic.pciAddress == pciAddress:
                found = True
                driver = dpdkNic.driver
                targetDpdkNic.append(dpdkNic)
                break

        if not found:
            continue

        targetDriver = nicNameDriverMap.__dict__[nicName]
        if driver == "mlx5_core" or driver == targetDriver:
            # mellanox nic(like cx-5) does not need vfio driver
            continue

        # for nested vm, the driver is should be uio_pci_generic
        r, _, e = bash.bash_roe(DevBindBin + " -b {driver} {pciAddress}"
                                .format(driver=targetDriver, pciAddress=pciAddress))
        if r != 0:
            logger.debug(
                "change change nic [pci address: {}] driver to {} failed: {}}"
                .format(pciAddress, targetDriver, e))
        else:
            logger.debug(
                "successfully change change nic [pci address: {}] driver to {}".format(pciAddress, targetDriver))

        bash.bash_r("ip link set up dev {}".format(nicName))

    return 0, ""

class VsCtl(object):
    def __init__(self):
        pass

    @bash.in_bash
    def addVnic(self, nicName, srcPath, brName="br-int", nicType="dpdkvhostuserclient"):
        """
        TODO: replace external-ids with vmnic uuid
        """
        try:
            cmd = CtlBin + \
                  'add-port {} {} -- set Interface {} type={} options:vhost-server-path={} ' \
                  ' -- set interface {} external-ids:iface-id={}'.format(
                      brName, nicName, nicName, nicType, srcPath, nicName, nicName)
            shell.call(cmd)
        except Exception as err:
            logger.error(
                "Add port for brdige {} failed. {}".format(brName, err))

    @bash.in_bash
    def delVnic(self, nicName, brName="br-int"):
        try:
            shell.call(CtlBin + 'del-port {} {}'.format(brName, nicName))
        except Exception as err:
            logger.error(
                "Delete port of bridge {} failed. {}".format(brName, err))

    @bash.in_bash
    def getUplink(self, brName="br-phy"):
        r, o, e = bash.bash_roe(CtlBin + " br-exists {}".format(brName))
        if r != 0:
            return []

        r, o, e = bash.bash_roe(CtlBin + " list-ports {}".format(brName))
        if r != 0:
            logger.debug(CtlBin + " list-ports {}, failed {}".format(brName, e))
            return r

        ret = []
        lines = o.split("\n")
        for l in lines:
            l = l.strip()
            if l.startswith("vnic"):
                continue
            if l.startswith("patch"):
                continue
            ret.append(l)

        return ret

    @bash.in_bash
    def addUplink(self, portPciMap, brName="br-phy", bondName="dpdkbond"):
        bash.bash_roe(CtlBin + " --may-exist add-br {};"
                               "ovs-vsctl set Bridge br-phy datapath_type=netdev;"
                               "ovs-vsctl set bridge br-phy fail-mode=standalone".format(brName))

        uplinks = self.getUplink(brName)
        for link in uplinks:
            bash.bash_roe(CtlBin + " del-port {} {}".format(brName, link))

        if len(portPciMap.__dict__) == 1:
            for nicName, pciAddress in portPciMap.__dict__.items():
                r, _, e = bash.bash_roe(CtlBin + " add-port {brName} {nic} "
                                                 "-- set Interface {nic} type=dpdk options:dpdk-devargs={pci};"
                                        .format(brName=brName, nic=nicName, pci=pciAddress))
                if r != 0:
                    logger.debug(CtlBin + " add-port {} {} failed: {}".format(brName, nicName, e))
                    return r, e
        else:
            cmd = CtlBin + "add-bond {} {} ".format(brName, bondName)
            for nicName, pciAddress in portPciMap.__dict__.items():
                cmd = cmd + " {} ".format(nicName)
            r, _, e = bash.bash_roe(cmd)
            if r != 0:
                logger.debug("{} faild {}".format(cmd, e))
                return r, e
            for nicName, pciAddress in portPciMap.__dict__.items():
                r, _, e = bash.bash_roe(CtlBin + " set Interface {nic} type=dpdk options:dpdk-devargs={pci} "
                                        .format(nic=nicName, pci=pciAddress))
                if r != 0:
                    logger.debug("ovs-vsctl set Interface {} type=dpdk options:dpdk-devargs={} faild {}"
                                 .format(nicName, pciAddress, e))
                    return r, e

        return 0, ""
