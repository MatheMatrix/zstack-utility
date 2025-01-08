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

CtlBin = "/usr/local/bin/ovs-vsctl "
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
    r, o, e = bash.bash_roe(DevBindBin + " --status-dev net | grep drv=")
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

class VsCtl(object):
    def __init__(self):
        pass

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

    def delVnic(self, nicName, brName="br-int"):
        try:
            shell.call(CtlBin + 'del-port {} {}'.format(brName, nicName))
        except Exception as err:
            logger.error(
                "Delete port of bridge {} failed. {}".format(brName, err))
