from zstacklib.utils import shell
from zstacklib.utils.version import NumericVersion
from enum import Enum
import json
import re
from shlex import quote

__QEMU_IMG_VERSION = None
__QEMU_IMG_RELEASE_VERSION = None

class QemuImgOutputFormat(Enum):
    CBD = "cbd"
    ISCSI = "iscsi"
    QCOW2 = "qcow2"
    RAW = "raw"
    RBD = "rbd"

class CheckResult(object):
    def __init__(self, offset, t_clusters, check_erorrs, a_clusters, filename, format):
        self.image_end_offset = offset
        self.total_clusters = t_clusters
        self.check_errors = check_erorrs
        self.allocated_clusters = a_clusters
        self.filename = filename
        self.format = format

def get_version():
    global __QEMU_IMG_VERSION
    if not __QEMU_IMG_VERSION:
        command = "qemu-img --version | grep 'qemu-img version' | cut -d ' ' -f 3 | cut -d '(' -f 1"
        __QEMU_IMG_VERSION = shell.call(command).strip('\t\r\n ,')

    return __QEMU_IMG_VERSION

# qemu-img version 4.2.0 (qemu-kvm-4.2.0-640.g70d8f25.el7)
# return 4.2.0-640
def get_release_version():
    global __QEMU_IMG_RELEASE_VERSION
    if not __QEMU_IMG_RELEASE_VERSION:
        version = shell.call("qemu-img --version | grep 'qemu-img version' | cut -d ' ' -f 4")
        __QEMU_IMG_RELEASE_VERSION = get_version() + "-" + re.search(r'%s-(\d+)' % get_version(), version).group(1)
    return __QEMU_IMG_RELEASE_VERSION

def subcmd(subcmd):
    options = ''
    if NumericVersion(get_version()) >= NumericVersion('2.10.0'):
        if subcmd in ['info', 'check', 'compare', 'convert', 'rebase', 'measure']:
            options += ' --force-share '
    return 'qemu-img %s %s ' % (subcmd, options)


def get_check_result(path):
    check_cmd = "%s --out json %s" % (subcmd('check'), path)
    result = json.loads(shell.call(check_cmd))
    return CheckResult(result.get("image-end-offset"), result.get("total-clusters"),
                       result.get("check-errors"), result.get("allocated-clusters"),
                       result.get("filename"), result.get("format"))

def take_default_backing_fmt_for_convert():
    return NumericVersion(get_version()) <= NumericVersion("6.0.0")

def resize_backing_before_rebase():
    return NumericVersion(get_release_version()) < NumericVersion("6.2.0-227")


def get_qcow2_bitmaps(path):
    cmd = shell.ShellCmd("%s --output=json %s" % (subcmd('info'), quote(path)))
    cmd(False)
    if cmd.return_code != 0:
        raise Exception("failed to get qcow2 bitmaps for image[%s], because %s" % (path, cmd.stderr))
    info = json.loads(cmd.stdout)
    return info.get("format-specific", {}).get("data", {}).get("bitmaps", [])
