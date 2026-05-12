from zstacklib.utils import shell
from zstacklib.utils.version import NumericVersion
import json
import re

__QEMU_IMG_VERSION = None
__QEMU_IMG_RELEASE_VERSION = None

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
        command = "qemu-img --version 2>/dev/null | head -1 | sed -n 's/.*\\([0-9]\\{1,\\}\\.[0-9]\\{1,\\}\\.[0-9]\\{1,\\}\\).*/\\1/p'"
        __QEMU_IMG_VERSION = shell.call(command).strip('\t\r\n ,')

    return __QEMU_IMG_VERSION

# qemu-img version 4.2.0 (qemu-kvm-4.2.0-640.g70d8f25.el7)
# return 4.2.0-640
def get_release_version():
    global __QEMU_IMG_RELEASE_VERSION
    if not __QEMU_IMG_RELEASE_VERSION:
        full_output = shell.call("qemu-img --version 2>/dev/null")
        base_ver = get_version()
        if base_ver:
            match = re.search(r'%s-(\d+)' % base_ver.replace('.', '\\.'), full_output)
            if match:
                __QEMU_IMG_RELEASE_VERSION = base_ver + "-" + match.group(1)
            else:
                __QEMU_IMG_RELEASE_VERSION = base_ver
        else:
            __QEMU_IMG_RELEASE_VERSION = ""
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



