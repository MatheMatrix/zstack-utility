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
from zstacklib.utils import iproute
from zstacklib.utils import lock
from zstacklib.utils import linux
from zstacklib.utils import thread
from zstacklib.utils import http

logger = log.get_logger(__name__)

CtlBin = "/usr/local/bin/ovs-vsctl "


class OvsError(Exception):
    '''ovs error'''


class VsCtl(object):
    def __init__(self):
        pass

    def addVnic(self, nicName, srcPath, brName="br-int", nicType="dpdkvhostuserclient"):
        """
        TODO: replace external-ids with vmnic uuid
        """
        try:
            cmd = CtlBin + \
                'add-port {} {} -- set Interface {} type={} options:vhost-server-path={} '\
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