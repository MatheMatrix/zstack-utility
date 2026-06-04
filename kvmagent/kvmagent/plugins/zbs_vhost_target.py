import os
import socket

from zstacklib.utils import bash
from zstacklib.utils import log

logger = log.get_logger(__name__)

HUGEPAGE_NR_PATH = "/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
DEFAULT_SOCKET_DIR = "/var/tmp/vhost-sockets"
DEFAULT_CONTROL_SOCK = "/var/tmp/vhost-sockets/vhost.sock"
DEFAULT_CLIENT_CONF = "/etc/zbs/client.conf"
DEFAULT_CONTAINER_NAME = "zbs-vhost"
# vhost target needs ~320MB; 2MiB pages -> 160. keep headroom.
DEFAULT_HUGEPAGE_NR = 256


def ensure_hugepages(nr=DEFAULT_HUGEPAGE_NR):
    current = _read_hugepage_nr()
    if current >= nr:
        return current

    # memory on busy hosts is fragmented; compaction lets the kernel
    # satisfy the contiguous 2MiB allocations the target needs.
    bash.bash_o("sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory")
    bash.bash_o("echo %d > %s" % (nr, HUGEPAGE_NR_PATH))
    got = _read_hugepage_nr()
    if got < nr:
        raise Exception("failed to allocate %d hugepages, only got %d; free up memory on the host" % (nr, got))
    return got


def _read_hugepage_nr():
    if not os.path.exists(HUGEPAGE_NR_PATH):
        raise Exception("hugepage sysfs not found: %s" % HUGEPAGE_NR_PATH)
    return int(bash.bash_o("cat %s" % HUGEPAGE_NR_PATH).strip() or "0")


def image_present(image):
    return bash.bash_r("docker image inspect %s >/dev/null 2>&1" % image) == 0


def load_image(image, image_tar):
    if image_present(image):
        return
    if not image_tar or not os.path.exists(image_tar):
        raise Exception("zbs-vhost image[%s] absent and no image tar[%s] to load" % (image, image_tar))
    bash.bash_errorout("docker load -i %s" % image_tar)


def is_running(name=DEFAULT_CONTAINER_NAME):
    out = bash.bash_o("docker ps --filter name=^/%s$ --filter status=running -q" % name).strip()
    return out != ""


def ensure_target(image, cores, socket_dir=DEFAULT_SOCKET_DIR, control_sock=DEFAULT_CONTROL_SOCK,
                   client_conf=DEFAULT_CLIENT_CONF, name=DEFAULT_CONTAINER_NAME,
                   hugepage_nr=DEFAULT_HUGEPAGE_NR, image_tar=None):
    if is_running(name):
        return

    load_image(image, image_tar)
    ensure_hugepages(hugepage_nr)
    if not os.path.exists(socket_dir):
        os.makedirs(socket_dir)

    # drop any dead container with the same name before starting.
    bash.bash_r("docker rm -f %s >/dev/null 2>&1" % name)
    # target is down: every socket left in the dir is an orphan (stale control
    # sock + controllers from a previous run). clear them so readiness waits on
    # the genuinely new control sock, not a stale file.
    _clean_sockets(socket_dir)

    cmd = ("docker run -d --name {name} --privileged --network host --restart always"
           " -v {sock_dir}:{sock_dir}"
           " -v /dev/hugepages:/dev/hugepages"
           " -v {conf}:{conf}"
           " {image}"
           " /usr/local/bin/vhost -m '{cores}' -S {sock_dir} -r {ctrl} -z {conf}").format(
        name=name, sock_dir=socket_dir, conf=client_conf, image=image, cores=cores, ctrl=control_sock)
    bash.bash_errorout(cmd)

    if not _wait_control_sock(control_sock):
        log_tail = bash.bash_o("docker logs --tail 20 %s 2>&1" % name)
        raise Exception("zbs-vhost target started but control sock[%s] not ready; logs:\n%s" % (control_sock, log_tail))


def _clean_sockets(socket_dir):
    if os.path.isdir(socket_dir):
        bash.bash_r("rm -f %s/*" % socket_dir)


def _wait_control_sock(control_sock, retries=40):
    for _ in range(retries):
        if _control_sock_ready(control_sock):
            return True
        bash.bash_o("sleep 0.5")
    return _control_sock_ready(control_sock)


def _control_sock_ready(control_sock):
    if not os.path.exists(control_sock):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(control_sock)
        return True
    except (socket.error, OSError):
        return False
    finally:
        s.close()


def stop_target(name=DEFAULT_CONTAINER_NAME):
    bash.bash_r("docker rm -f %s >/dev/null 2>&1" % name)
