# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

QGA_EXEC_WAIT_INTERVAL = 1
QGA_EXEC_WAIT_RETRY = 30
ZS_TOOLS_WAIT_RETRY = 120

QGA_CHANNEL_STATE_CONNECTED = 'connected'
QGA_CHANNEL_STATE_DISCONNECTED = 'disconnected'


class QgaState(str, Enum):
    RUNNING = "Running"
    NOT_RUNNING = "NotRunning"


class GuestOS(str, Enum):
    LINUX_KYLIN = "kylin"
    LINUX_UOS = "uos"
    LINUX_UBUNTU = "ubuntu"
    LINUX_CENTOS = "centos"
    LINUX_OPENSUSE = "opensuse-leap"
    LINUX_SUSE_SERVER = "sles"
    LINUX_SUSE_DESKTOP = "sled"
    LINUX_ORACLE = "ol"
    LINUX_REDHAT = "rhel"
    WINDOWS = "mswindows"


ZS_TOOLS_PATH_WIN = r"C:\Program Files\GuestTools\zs-tools\zs-tools.exe"
