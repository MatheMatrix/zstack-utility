# Copyright (c) 2025, ZStack, Inc.
# ZSTAC-83157: Host model mount plugin for Model Center pre-mounting

import os
import re
import json
import uuid
import shlex
import threading
import traceback
from urllib.parse import urlsplit, urlunsplit
from kvmagent import kvmagent
from zstacklib.utils import log, shell, jsonobject, http

logger = log.get_logger(__name__)

# Base directory for Model Center mounts
MODEL_MOUNT_BASE = "/opt/zstack/models"

# UUID validation regex
UUID_RE = re.compile(r'^[0-9a-fA-F-]{36}$')

# Mount watchdog configuration
MOUNT_REGISTRY_FILE = os.path.join(MODEL_MOUNT_BASE, ".registry")
WATCHDOG_INTERVAL_SECS = 60
MOUNT_CHECK_TIMEOUT_SECS = 5
# Number of consecutive health check failures before triggering remount.
# This prevents false positives from momentary I/O spikes or network blips.
MOUNT_UNHEALTHY_THRESHOLD = 3

_registry_lock = threading.Lock()
_recovering = set()
_recovering_lock = threading.Lock()
_watchdog = None
# Track consecutive health check failures per mount point
# {mount_point: failure_count}
_health_failures = {}


def _load_mount_registry():
    """Load mount registry from disk.
    Format: {mcUuid: {"storageUrl": "...", "mountPoint": "..."}}
    """
    if not os.path.exists(MOUNT_REGISTRY_FILE):
        return {}
    try:
        with open(MOUNT_REGISTRY_FILE, 'r') as f:
            return json.load(f)
    except (ValueError, IOError) as e:
        logger.warning("Failed to load mount registry: %s" % str(e))
        return {}


def _write_registry(registry):
    """Write registry to disk atomically (rename is atomic on Linux)."""
    ensure_mount_base_dir()
    tmp_file = MOUNT_REGISTRY_FILE + '.tmp'
    with open(tmp_file, 'w') as f:
        json.dump(registry, f, indent=2)
    os.rename(tmp_file, MOUNT_REGISTRY_FILE)


def _save_mount_registry_entry(model_center_uuid, storage_url, mount_point):
    """Add or update a mount registry entry. Thread-safe."""
    with _registry_lock:
        registry = _load_mount_registry()
        registry[model_center_uuid] = {
            'storageUrl': storage_url,
            'mountPoint': mount_point,
        }
        _write_registry(registry)
        logger.debug("Saved mount registry entry for model center[%s]" % model_center_uuid)


def _check_mount_health(mount_point):
    """Check if a mount point is healthy using dual verification.

    1. os.path.ismount() checks VFS mount status
    2. timeout ls checks actual accessibility (detects zombie FUSE mounts)

    Returns True if mount point exists and is accessible.
    """
    if not os.path.ismount(mount_point):
        return False
    try:
        check_cmd = shell.ShellCmd("timeout %d ls %s >/dev/null 2>&1" % (
            MOUNT_CHECK_TIMEOUT_SECS, shlex.quote(mount_point)))
        check_cmd(False)
        return check_cmd.return_code == 0
    except Exception:
        return False


def remount_model_center(model_center_uuid):
    """Remount a model center's JuiceFS mount point.

    Used by both the watchdog thread (periodic health check) and the
    virtiofs attach flow (on-demand recovery).

    Returns True if mount is healthy or recovery succeeded.
    """
    # Prevent concurrent remount of the same model center
    should_cleanup = False
    with _recovering_lock:
        if model_center_uuid in _recovering:
            logger.debug("Already recovering model center[%s], skipping" % model_center_uuid)
            return False
        _recovering.add(model_center_uuid)
        should_cleanup = True

    try:
        registry = _load_mount_registry()
        if model_center_uuid not in registry:
            logger.error("Cannot remount: no registry entry for model center[%s]" % model_center_uuid)
            return False

        info = registry[model_center_uuid]
        storage_url = info.get('storageUrl', '')
        mount_point = info.get('mountPoint', '')

        if not storage_url or not mount_point:
            logger.error("Invalid registry entry for model center[%s]" % model_center_uuid)
            return False

        # Already healthy, nothing to do
        if _check_mount_health(mount_point):
            return True

        logger.warning("Mount point %s (mc=%s) is unhealthy, attempting recovery" % (
            mount_point, model_center_uuid))

        # Clean up existing mount (zombie or otherwise)
        if os.path.ismount(mount_point):
            umount_cmd = shell.ShellCmd("umount %s" % shlex.quote(mount_point))
            umount_cmd(False)
            if umount_cmd.return_code != 0:
                logger.warning("Regular umount failed for %s, trying lazy umount" % mount_point)
                lazy_cmd = shell.ShellCmd("umount -l %s" % shlex.quote(mount_point))
                lazy_cmd(False)

        # Remount
        success, error = mount_juicefs(storage_url, mount_point)
        if success:
            logger.info("Successfully remounted model center[%s] at %s" % (
                model_center_uuid, mount_point))
        else:
            logger.error("Failed to remount model center[%s]: %s" % (model_center_uuid, error))
        return success

    except Exception as e:
        logger.error("Exception during remount of model center[%s]: %s" % (model_center_uuid, str(e)))
        return False
    finally:
        if should_cleanup:
            with _recovering_lock:
                _recovering.discard(model_center_uuid)


class _MountWatchdog(object):
    """Background daemon thread that periodically checks mount point health
    and automatically recovers broken mounts.

    Started by HostModelMountPlugin.start(), stopped by stop().
    Uses threading.Event.wait() for graceful shutdown.
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name='mount-watchdog')
        self._thread.start()
        logger.info("Mount watchdog started, interval=%ds" % WATCHDOG_INTERVAL_SECS)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Mount watchdog stopped")

    def _run(self):
        # Initial check on startup (recovers mounts lost after host reboot)
        self._check_all_mounts()

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=WATCHDOG_INTERVAL_SECS)
            if not self._stop_event.is_set():
                self._check_all_mounts()

    def _check_all_mounts(self):
        global _health_failures
        registry = _load_mount_registry()
        if not registry:
            return
        for mc_uuid, info in registry.items():
            mount_point = info.get('mountPoint', '')
            if not mount_point:
                continue
            if _check_mount_health(mount_point):
                # Healthy: reset failure counter
                _health_failures.pop(mc_uuid, None)
            else:
                # Unhealthy: increment failure counter
                _health_failures[mc_uuid] = _health_failures.get(mc_uuid, 0) + 1
                failure_count = _health_failures[mc_uuid]
                if failure_count >= MOUNT_UNHEALTHY_THRESHOLD:
                    logger.warning("Watchdog: mount point %s (mc=%s) unhealthy for %d consecutive checks, "
                                   "triggering recovery" % (mount_point, mc_uuid, failure_count))
                    success = remount_model_center(mc_uuid)
                    if success:
                        _health_failures.pop(mc_uuid, None)
                else:
                    logger.info("Watchdog: mount point %s (mc=%s) check failed (%d/%d), "
                                "waiting for more failures before recovery" % (
                                    mount_point, mc_uuid, failure_count, MOUNT_UNHEALTHY_THRESHOLD))


def _start_watchdog():
    global _watchdog
    if _watchdog is not None:
        return
    _watchdog = _MountWatchdog()
    _watchdog.start()


def _stop_watchdog():
    global _watchdog
    if _watchdog is not None:
        _watchdog.stop()
        _watchdog = None


def _mask_url(url):
    """Mask sensitive info in URL for logging."""
    try:
        parts = urlsplit(url)
        if '@' not in parts.netloc:
            return url
        auth, host = parts.netloc.rsplit('@', 1)
        if ':' in auth:
            user, _ = auth.split(':', 1)
            masked_auth = ('%s:***' % user) if user else ':***'
        else:
            masked_auth = '***'
        return urlunsplit((parts.scheme, '%s@%s' % (masked_auth, host),
                          parts.path, parts.query, parts.fragment))
    except Exception:
        return '***'


class MountModelCenterCmd(jsonobject.JsonObject):
    """Command to mount Model Center storage to host"""
    modelCenterUuid = str
    storageUrl = str     # JuiceFS meta URL (e.g., redis://redis-host:6379/0)


class MountModelCenterResponse(jsonobject.JsonObject):
    success = bool
    error = str
    mountPoint = str


class ListModelCentersResponse(jsonobject.JsonObject):
    success = bool
    error = str
    mounts = list


def ensure_mount_base_dir():
    """Ensure the base mount directory exists"""
    if not os.path.exists(MODEL_MOUNT_BASE):
        os.makedirs(MODEL_MOUNT_BASE, exist_ok=True)
        logger.info("Created model mount base directory: %s" % MODEL_MOUNT_BASE)


def check_juicefs_installed():
    """Check if juicefs binary is available

    Returns: (juicefs_path_or_None, error_message)
    """
    # Check common installation paths
    juicefs_paths = [
        "/usr/local/bin/juicefs",
        "/usr/bin/juicefs",
        "/opt/zstack/bin/juicefs"
    ]

    for path in juicefs_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            logger.debug("Found juicefs binary at %s" % path)
            return path, None

    # Try to find in PATH using shell.ShellCmd
    which_cmd = shell.ShellCmd("which juicefs")
    which_cmd(False)
    if which_cmd.return_code == 0:
        juicefs_path = which_cmd.stdout.strip()
        logger.debug("Found juicefs in PATH: %s" % juicefs_path)
        return juicefs_path, None

    error_msg = ("juicefs binary not found. Please install juicefs to "
                 "/usr/local/bin/juicefs or any location in PATH. "
                 "Download from: https://github.com/juicedata/juicefs/releases")
    return None, error_msg


def mount_juicefs(zdfs_url, mount_point):
    """Mount JuiceFS models directory to the specified mount point

    JuiceFS directory structure:
    /                           <- JuiceFS root
    ├── models/                 <- Models directory (physical host mounts this)
    │   └── {model_name}/
    │       └── {version}/
    │           └── model.yaml
    └── datasets/               <- Datasets directory (not needed on physical host)

    Model Center VM:
        - Mounts entire JuiceFS to /root/bentoml
        - Models at: /root/bentoml/models/{model_name}/

    Physical Host:
        - Mounts only models/ subdirectory using --subdir models
        - Mount point: /opt/zstack/models/{mcUuid}
        - Models at: /opt/zstack/models/{mcUuid}/{model_name}/
    """
    try:
        # Check if already mounted
        if os.path.ismount(mount_point):
            logger.info("Mount point %s is already mounted" % mount_point)
            return True, None

        # Create mount point
        os.makedirs(mount_point, exist_ok=True)

        # Check if juicefs binary is available
        juicefs_path, error_msg = check_juicefs_installed()
        if not juicefs_path:
            logger.error(error_msg)
            return False, error_msg

        # JuiceFS mount command
        # Mount only the models/ subdirectory using --subdir models
        # The zdfs_url is the meta URL (e.g., redis://redis-host:6379/0)
        cache_dir = "/var/cache/virtiofs/juicefs"
        # Use shlex.quote to prevent shell injection
        # Use full path to juicefs binary to avoid PATH issues
        cmd = "%s mount %s %s --read-only -d --subdir models --cache-dir %s" % (
            shlex.quote(juicefs_path), shlex.quote(zdfs_url), shlex.quote(mount_point), shlex.quote(cache_dir))

        logger.info("Executing mount command for Model Center, mount_point=%s, url=%s" % (
            mount_point, _mask_url(zdfs_url)))

        mount_cmd = shell.ShellCmd(cmd)
        mount_cmd(False)
        if mount_cmd.return_code != 0:
            error_msg = mount_cmd.stderr or "Mount command failed"
            logger.error("Failed to mount JuiceFS: %s" % error_msg)
            return False, error_msg

        logger.info("Successfully mounted JuiceFS at %s" % mount_point)
        return True, None

    except Exception as e:
        logger.error("Exception during JuiceFS mount: %s" % str(e))
        return False, str(e)


class HostModelMountPlugin(kvmagent.KvmAgent):
    """Host model mount plugin for Model Center pre-mounting"""

    MOUNT_PATH = "/modelcenter/mount"
    LIST_PATH = "/modelcenter/list"

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.MOUNT_PATH, self.mount_model_center)
        http_server.register_async_uri(self.LIST_PATH, self.list_model_centers)
        _start_watchdog()

    def stop(self):
        _stop_watchdog()

    @kvmagent.replyerror
    def mount_model_center(self, req):
        """Mount Model Center storage to host"""
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = MountModelCenterResponse()
        rsp.success = False

        try:
            logger.info("Mounting Model Center[%s] with URL: %s" % (
                cmd.modelCenterUuid, _mask_url(cmd.storageUrl)))

            if not cmd.modelCenterUuid:
                rsp.error = "invalid modelCenterUuid"
                return jsonobject.dumps(rsp)

            # Ensure base directory exists
            ensure_mount_base_dir()

            # Build mount point path with boundary check
            mount_point = os.path.abspath(os.path.join(MODEL_MOUNT_BASE, cmd.modelCenterUuid))
            base_real = os.path.realpath(MODEL_MOUNT_BASE)
            target_real = os.path.realpath(mount_point)

            if os.path.commonpath([base_real, target_real]) != base_real:
                rsp.error = "invalid mount path"
                return jsonobject.dumps(rsp)

            rsp.mountPoint = mount_point

            # Mount
            success, error = mount_juicefs(cmd.storageUrl, mount_point)
            if success:
                rsp.success = True
                _save_mount_registry_entry(cmd.modelCenterUuid, cmd.storageUrl, mount_point)
                logger.info("Successfully mounted Model Center[%s] at %s" % (
                    cmd.modelCenterUuid, mount_point))
            else:
                rsp.error = error

        except Exception as e:
            logger.error("Failed to mount Model Center: %s\n%s" % (
                str(e), traceback.format_exc()))
            rsp.error = str(e)

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def list_model_centers(self, req):
        """List mounted Model Centers"""
        rsp = ListModelCentersResponse()
        rsp.success = True
        rsp.mounts = []

        try:
            if os.path.exists(MODEL_MOUNT_BASE):
                for name in os.listdir(MODEL_MOUNT_BASE):
                    if name.startswith('.'):
                        continue
                    mount_point = os.path.join(MODEL_MOUNT_BASE, name)
                    is_mounted = os.path.ismount(mount_point)
                    rsp.mounts.append({
                        "modelCenterUuid": name,
                        "mountPoint": mount_point,
                        "isMounted": is_mounted
                    })
        except Exception as e:
            logger.error("Failed to list model centers: %s" % str(e))
            rsp.error = str(e)
            rsp.success = False

        return jsonobject.dumps(rsp)
