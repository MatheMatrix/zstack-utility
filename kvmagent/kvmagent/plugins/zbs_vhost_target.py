import functools
import json
import os
import shlex
import socket
import threading
import xml.etree.ElementTree as ET

from zstacklib.utils import bash
from zstacklib.utils import log

logger = log.get_logger(__name__)

_TARGET_LOCK = threading.RLock()


def _locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _TARGET_LOCK:
            return fn(*args, **kwargs)
    return wrapper

HUGEPAGE_DIR = "/sys/kernel/mm/hugepages/hugepages-2048kB"
HUGEPAGE_NR_PATH = HUGEPAGE_DIR + "/nr_hugepages"
HUGEPAGE_FREE_PATH = HUGEPAGE_DIR + "/free_hugepages"
DEFAULT_VHOST_TARGET_HUGEPAGE_DIR = "/dev/hugepages2m"
DEFAULT_SOCKET_DIR = "/var/tmp/vhost-sockets"
DEFAULT_CONTROL_SOCK = "/var/tmp/vhost-sockets/vhost.sock"
DEFAULT_CLIENT_CONF = "/etc/zbs/client.conf"
DEFAULT_CONTAINER_NAME = "zbs-vhost"
DEFAULT_HUGEPAGE_NR = 256
DEFAULT_VHOST_TARGET_HUGEPAGE_NR = 1024
HUGEPAGE_SIZE_BYTES = 2 * 1024 * 1024
DEFAULT_CORE_COUNT = 2
DOCKER_CE_INSTALL_CMD = "yum --disablerepo=zstack-local --enablerepo=zstack-mn install -y docker-ce docker-ce-cli containerd.io"
DOCKER_ENGINE_INSTALL_CMD = "yum --disablerepo=zstack-local --enablerepo=zstack-mn install -y docker-engine"


def host_cpu_num():
    return int(bash.bash_o("nproc").strip() or "1")


def compute_cores(count=DEFAULT_CORE_COUNT):
    total = host_cpu_num()
    count = max(1, min(count, total))
    cores = list(range(total - count, total))
    return "[%s]" % ",".join(str(c) for c in cores)


def download_image(url, dest_tar):
    bash.bash_errorout(
        "curl -fSL --connect-timeout 10 --retry 3 --retry-delay 2 -o %s %s"
        % (shlex.quote(dest_tar), shlex.quote(url)))
    return dest_tar


def image_registry(image):
    if "/" not in image:
        return None
    head = image.split("/", 1)[0]
    if "." in head or ":" in head or head == "localhost":
        return head
    return None


def ensure_insecure_registry(registry):
    path = "/etc/docker/daemon.json"
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                cfg = json.load(f) or {}
        except ValueError:
            cfg = {}
    regs = cfg.get("insecure-registries", [])
    if registry in regs:
        return
    regs.append(registry)
    cfg["insecure-registries"] = regs
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    bash.bash_errorout("systemctl reload docker")


_INSECURE_REGISTRY_MARKERS = ("server gave http response", "tls", "x509", "certificate")


def pull_image(image):
    registry = image_registry(image)
    try:
        bash.bash_errorout("docker pull %s" % shlex.quote(image))
        return
    except Exception as e:
        err = str(e).lower()
        if not registry or not any(m in err for m in _INSECURE_REGISTRY_MARKERS):
            raise
        logger.warn("docker pull %s failed with tls/protocol error, retrying registry[%s] as insecure: %s"
                    % (image, registry, e))
    ensure_insecure_registry(registry)
    bash.bash_errorout("docker pull %s" % shlex.quote(image))


def mem_to_pages(nbytes):
    return (int(nbytes) + HUGEPAGE_SIZE_BYTES - 1) // HUGEPAGE_SIZE_BYTES


_MEM_UNIT_BYTES = {
    "b": 1, "bytes": 1,
    "k": 1024, "kib": 1024, "kb": 1024,
    "m": 1024 ** 2, "mib": 1024 ** 2, "mb": 1024 ** 2,
    "g": 1024 ** 3, "gib": 1024 ** 3, "gb": 1024 ** 3,
    "t": 1024 ** 4, "tib": 1024 ** 4, "tb": 1024 ** 4,
}


def domain_vhostuser_present(domain_xml):
    try:
        root = ET.fromstring(domain_xml)
    except ET.ParseError:
        return False
    return any(d.get("type") == "vhostuser" for d in root.iter("disk"))


def domain_memory_bytes(domain_xml):
    mem = ET.fromstring(domain_xml).find("memory")
    if mem is None or not (mem.text or "").strip():
        return 0
    unit = (mem.get("unit") or "k").lower()
    return int(mem.text.strip()) * _MEM_UNIT_BYTES.get(unit, 1024)


def _read_hugepage_nr():
    if not os.path.exists(HUGEPAGE_NR_PATH):
        raise Exception("hugepage sysfs not found: %s" % HUGEPAGE_NR_PATH)
    return int(bash.bash_o("cat %s" % HUGEPAGE_NR_PATH).strip() or "0")


def _read_hugepage_free():
    # per-pool sysfs, not /proc/meminfo: meminfo's HugePages_Free reports only the
    # kernel default hugepage size, which on aarch64 (64KB base page) is 512MB, not the
    # 2MB pool this target uses; reading meminfo makes the 2MB grow look like it failed.
    if not os.path.exists(HUGEPAGE_FREE_PATH):
        raise Exception("hugepage sysfs not found: %s" % HUGEPAGE_FREE_PATH)
    return int(bash.bash_o("cat %s" % HUGEPAGE_FREE_PATH).strip() or "0")


def _compact_memory():
    bash.bash_o("sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory")


@_locked
def ensure_free_hugepages(need_pages):
    free = _read_hugepage_free()
    if free >= need_pages:
        return
    total = _read_hugepage_nr()
    target = total + (need_pages - free)
    _compact_memory()
    bash.bash_o("echo %d > %s" % (target, HUGEPAGE_NR_PATH))
    got = _read_hugepage_free()
    if got < need_pages:
        raise Exception("failed to free %d hugepages, only %d free after growing to %d; "
                        "free up memory on the host" % (need_pages, got, target))


def find_2m_hugetlbfs_mount():
    out = bash.bash_o("findmnt -rn -t hugetlbfs -o TARGET,OPTIONS")
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and "pagesize=2M" in parts[1].split(","):
            return parts[0]
    return None


def ensure_2m_hugetlbfs_mount(mount_dir=DEFAULT_VHOST_TARGET_HUGEPAGE_DIR):
    existing = find_2m_hugetlbfs_mount()
    if existing:
        return existing

    if not os.path.exists(mount_dir):
        os.makedirs(mount_dir)
    if bash.bash_r("findmnt -n -T %s -t hugetlbfs -o OPTIONS | grep -qw pagesize=2M" %
                   shlex.quote(mount_dir)) == 0:
        return mount_dir
    bash.bash_errorout("mount -t hugetlbfs -o pagesize=2M none %s" % shlex.quote(mount_dir))
    return mount_dir


def ensure_hugepages_for_domain(domain_xml):
    if not domain_vhostuser_present(domain_xml):
        return
    ensure_free_hugepages(mem_to_pages(domain_memory_bytes(domain_xml)))


@_locked
def reclaim_hugepages(slack=0):
    free = _read_hugepage_free()
    total = _read_hugepage_nr()
    keep = (total - free) + slack
    if keep < total:
        bash.bash_o("echo %d > %s" % (keep, HUGEPAGE_NR_PATH))


def image_present(image):
    return bash.bash_r("docker image inspect %s >/dev/null 2>&1" % shlex.quote(image)) == 0


def docker_ready():
    return bash.bash_r("command -v docker >/dev/null 2>&1") == 0 and \
           bash.bash_r("systemctl is-active --quiet docker") == 0


def ensure_docker():
    if docker_ready():
        return
    ce_r, ce_o, ce_e = bash.bash_roe(DOCKER_CE_INSTALL_CMD)
    if ce_r != 0:
        logger.warn("docker-ce install failed, falling back to docker-engine, stdout: %s, stderr: %s" % (ce_o, ce_e))
        engine_r, engine_o, engine_e = bash.bash_roe(DOCKER_ENGINE_INSTALL_CMD)
        if engine_r != 0:
            raise Exception("failed to install docker provider from zstack-mn, "
                            "docker-ce stdout: %s, stderr: %s; docker-engine stdout: %s, stderr: %s"
                            % (ce_o, ce_e, engine_o, engine_e))
    bash.bash_errorout("systemctl enable --now docker")
    if not docker_ready():
        raise Exception("docker still not running after install on this host")


def load_image(image, image_tar=None, image_url=None):
    if image_present(image):
        return
    errors = []
    if image_registry(image):
        try:
            pull_image(image)
            return
        except Exception as e:
            logger.warn("registry pull of %s failed, trying offline sources: %s" % (image, e))
            errors.append("registry pull: %s" % e)
    if image_tar and os.path.exists(image_tar):
        try:
            bash.bash_errorout("docker load -i %s" % shlex.quote(image_tar))
            return
        except Exception as e:
            logger.warn("docker load of local tar %s failed: %s" % (image_tar, e))
            errors.append("local tar[%s]: %s" % (image_tar, e))
    if image_url:
        tmp_tar = image_tar if image_tar else "/var/lib/zstack/zbs-vhost-image.tar"
        try:
            download_image(image_url, tmp_tar)
            bash.bash_errorout("docker load -i %s" % shlex.quote(tmp_tar))
            return
        except Exception as e:
            logger.warn("fetch/load of image url %s failed: %s" % (image_url, e))
            errors.append("url[%s]: %s" % (image_url, e))
    if errors:
        raise Exception("zbs-vhost image[%s] unavailable from all sources: %s" % (image, "; ".join(errors)))
    raise Exception("zbs-vhost image[%s] absent: no registry in ref, no local tar[%s], no image url" % (image, image_tar))


def is_running(name=DEFAULT_CONTAINER_NAME):
    out = bash.bash_o("docker ps --filter name=^/%s$ --filter status=running -q" % name).strip()
    return out != ""


@_locked
def ensure_target(image, cores=None, socket_dir=DEFAULT_SOCKET_DIR, control_sock=DEFAULT_CONTROL_SOCK,
                  client_conf=DEFAULT_CLIENT_CONF, name=DEFAULT_CONTAINER_NAME,
                  hugepage_nr=DEFAULT_HUGEPAGE_NR, image_tar=None, image_url=None, core_count=DEFAULT_CORE_COUNT):
    if is_running(name):
        return

    if not cores:
        cores = compute_cores(core_count)

    load_image(image, image_tar, image_url)
    ensure_free_hugepages(hugepage_nr)
    if not os.path.exists(socket_dir):
        os.makedirs(socket_dir)

    bash.bash_r("docker rm -f %s >/dev/null 2>&1" % name)
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


def container_exists(name=DEFAULT_CONTAINER_NAME):
    out = bash.bash_o("docker ps -a --filter name=^/%s$ -q" % name).strip()
    return out != ""


def target_running(control_sock, name):
    return container_exists(name) and is_running(name) and _control_sock_ready(control_sock)
