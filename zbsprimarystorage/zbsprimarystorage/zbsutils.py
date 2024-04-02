__author__ = 'Xingwei Yu'

from zstacklib.utils.bash import *

logger = log.get_logger(__name__)


def do_query_mds_status_info():
    return shell.call("zbs status mds --format json")


def do_query_logical_pool_info():
    return shell.call("zbs list logical-pool --format json")


def do_query_volume_info(path):
    return shell.call("zbs query file --path %s --format json" % path)


def do_query_volume(path):
    return shell.run("zbs query file --path %s" % path)


def do_create_volume(path, size):
    return shell.call("zbs create file --path %s --size %s --user zbs --format json" % (path, size))


def do_delete_volume(path):
    if shell.run("zbs query file --path %s" % path) != 0:
        return
    shell.call("zbs delete file --path %s" % path)


def normalize_install_path(path):
    if path is None:
        raise Exception("install path can not be null.")
    return path.split(":")[1].split("/", 1)[1]