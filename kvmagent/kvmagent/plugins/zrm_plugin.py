# -*- coding: utf-8 -*-
"""
ZRM agent plugin.

Registers KVM agent HTTP endpoints under /zrm/replication/*, /zrm/bitmap/*,
/zrm/checkpoint/* and /zrm/recovery/* for block replication, bitmap management,
checkpoint management and recovery flows.

The implementation is decoupled from CDP; it uses drive-mirror + NBD based
replication similar to the CDP / dual-active design (see kvmagent_implementation_design.md).
"""
from __future__ import absolute_import

import hashlib
import json
import os
import re
import socket
import threading
import uuid
try:
    import Queue as queue
except ImportError:
    import queue
try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

from kvmagent import kvmagent
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import qmp
from zstacklib.utils.qga import VmQga
import time

logger = log.get_logger(__name__)

# Python 2/3 string-type compatibility.
# On Python 2 json.loads returns unicode; basestring covers both str and unicode.
# On Python 3 basestring does not exist; str is sufficient.
try:
    _str_types = basestring
except NameError:
    _str_types = str

# Dirty bitmap name prefix used by ZR replication.
# Different from CDP's "zsbm-" prefix; per-volume bitmap name is
# "zrm-{first 16 chars of volumeUuid}".
ZRM_BITMAP_PREFIX = "zrm-"

# Number of leading characters of volumeUuid used to build the per-volume
# dirty bitmap name: ZRM_BITMAP_PREFIX + volumeUuid[:BITMAP_UUID_TRUNCATE_LEN].
BITMAP_UUID_TRUNCATE_LEN = 16

# Legacy job IDs used only the leading volume UUID characters.  Keep the
# length for backward-compatible discovery and compact log messages; new job
# IDs bind the complete volume UUID to session/target hashes.
MIRROR_JOB_UUID_TRUNCATE_LEN = 8

_MIRROR_JOB_PREFIX = "zrm-mirror-"
_MIRROR_TARGET_NODE_PREFIX = "zrm-tgt-"
_QEMU_BLOCK_NODE_NAME_MAX = 31
_MIRROR_TARGET_CLEANUP_RETRIES = 3
_MIRROR_TARGET_CLEANUP_RETRY_SECONDS = 1
_MIRROR_TARGET_LOCK_STRIPES = 64
_TARGET_RECOVERY_QMP_TIMEOUT_SECONDS = 5
_TARGET_RECOVERY_WORKERS = 4
_TARGET_RECOVERY_VM_LOCK_STRIPES = 64
_TARGET_RECOVERY_INITIAL_BACKOFF_SECONDS = 1
_TARGET_RECOVERY_MAX_BACKOFF_SECONDS = 30
_TARGET_RECOVERY_STOP_JOIN_SECONDS = 1

# A frozen guest must never depend on the management plane delivering a thaw
# request.  The lease survives a kvmagent restart under /var/run and is
# recovered by ZrmPlugin.start().
_DEFAULT_FSFREEZE_LEASE_SECONDS = 60
_FSFREEZE_RECOVERY_RETRY_SECONDS = 10
_FSFREEZE_LEASE_DIR = "/var/run/zstack/zrm/fsfreeze-leases"

# Default maximum timeout (seconds) for _wait_initial_full_sync when the
# caller does not specify one. Prevents async HTTP handler threads from
# blocking indefinitely.
_DEFAULT_MAX_WAIT_TIMEOUT = 3600

_DEFAULT_SHUTDOWN_TIMEOUT = 30

# Interval (seconds) between progress log messages inside _wait_initial_full_sync.
WAIT_INITIAL_LOG_INTERVAL = 30.0


def _to_long(v):
    """Safely convert a value to int (long). Returns None on failure."""
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return None


def execute_qmp_command_raw(domain_id, command, raise_exception=False,
                            command_timeout=None):
    """
    Execute a raw QMP command represented as a full JSON *string*.

    Delegates to the public ``qmp.execute_qmp_command_raw`` API.
    This wrapper is kept for backward compatibility and to preserve the
    default ``raise_exception=False`` used by ZRM bitmap operations.
    """
    if hasattr(qmp, 'execute_qmp_command_raw'):
        if command_timeout is None:
            return qmp.execute_qmp_command_raw(
                domain_id, command, raise_exception=raise_exception)
        return qmp.execute_qmp_command_raw(
            domain_id, command, raise_exception=raise_exception,
            command_timeout=command_timeout)
    if command_timeout is None:
        return qmp._execute_qmp_command(
            domain_id, command, raise_exception=raise_exception)
    return qmp._execute_qmp_command(
        domain_id, command, raise_exception=raise_exception,
        command_timeout=command_timeout)


class ZrmAgentRsp(object):
    """Lightweight response object aligned with Java KVMAgentCommands.AgentResponse."""
    def __init__(self, success=True, error=None, **kwargs):
        self.success = success
        self.error = error
        for k, v in (kwargs or {}).items():
            setattr(self, k, v)


class ZrmPlugin(kvmagent.KvmAgent):
    _runtime_state_init_lock = threading.RLock()

    PATH_REPLICATION_START = "/zrm/replication/start"
    PATH_REPLICATION_STOP = "/zrm/replication/stop"
    PATH_REPLICATION_PAUSE = "/zrm/replication/pause"
    PATH_REPLICATION_RESUME = "/zrm/replication/resume"
    PATH_REPLICATION_SYNC = "/zrm/replication/sync"
    PATH_REPLICATION_WAIT_INITIAL = "/zrm/replication/wait-initial"
    PATH_BITMAP_CREATE = "/zrm/bitmap/create"
    PATH_CHECKPOINT_CREATE = "/zrm/checkpoint/create"
    PATH_RECOVERY_PREPARE = "/zrm/recovery/prepare"
    PATH_REPLICATION_THROTTLE = "/zrm/replication/throttle"
    PATH_REPLICATION_GUEST_FSFREEZE = "/zrm/replication/guest-fsfreeze"

    # Only operations that create/remove mirror target nodes need to wait for
    # startup ownership reconciliation.  In particular, guest thaw must never
    # be blocked by an unrelated target-node recovery failure.
    _TARGET_RECOVERY_GUARDED_PATHS = frozenset((
        PATH_REPLICATION_START,
        PATH_REPLICATION_STOP,
        PATH_RECOVERY_PREPARE,
    ))

    # QGA fsfreeze command names (Linux application-consistent quiesce).
    _FSFREEZE_CMD_FREEZE = "guest-fsfreeze-freeze"
    _FSFREEZE_CMD_THAW = "guest-fsfreeze-thaw"
    _FSFREEZE_CMD_STATUS = "guest-fsfreeze-status"

    def _ensure_runtime_state(self):
        """Lazily initialize state so lightweight object.__new__ tests work."""
        with self._runtime_state_init_lock:
            if not hasattr(self, "_fsfreeze_vm_locks"):
                self._fsfreeze_vm_locks = {}
            if not hasattr(self, "_fsfreeze_watchdogs"):
                self._fsfreeze_watchdogs = {}
            if not hasattr(self, "_linux_fsfreeze_counts"):
                self._linux_fsfreeze_counts = {}
            if not hasattr(self, "_mirror_job_owners"):
                self._mirror_job_owners = {}
            if not hasattr(self, "_mirror_target_nodes"):
                self._mirror_target_nodes = {}
            if not hasattr(self, "_mirror_target_nodes_lock"):
                self._mirror_target_nodes_lock = threading.RLock()
            if not hasattr(self, "_mirror_target_locks"):
                self._mirror_target_locks = [
                    threading.RLock()
                    for unused_index in range(_MIRROR_TARGET_LOCK_STRIPES)]
            if not hasattr(self, "_mirror_target_cleanup_retries"):
                self._mirror_target_cleanup_retries = {}
            if not hasattr(self, "_target_recovery_pending_vms"):
                self._target_recovery_pending_vms = set()
            if not hasattr(self, "_target_recovery_vm_locks"):
                self._target_recovery_vm_locks = [
                    threading.RLock()
                    for unused_index in range(
                        _TARGET_RECOVERY_VM_LOCK_STRIPES)]
            if not hasattr(self, "_target_recovery_errors"):
                self._target_recovery_errors = {}
            if not hasattr(self, "_target_recovery_discovery_complete"):
                self._target_recovery_discovery_complete = False
            if not hasattr(self, "_target_recovery_discovery_error"):
                self._target_recovery_discovery_error = None
            if not hasattr(self, "_target_recovery_thread"):
                self._target_recovery_thread = None
            if not hasattr(self, "_target_recovery_stop_event"):
                self._target_recovery_stop_event = threading.Event()
            if not hasattr(self, "_target_recovery_generation"):
                self._target_recovery_generation = 0
            if not hasattr(self, "_runtime_stopping"):
                self._runtime_stopping = False

    def start(self):
        self._ensure_runtime_state()
        self._runtime_stopping = False
        # Lease recovery does not invoke QMP and must finish before the
        # fsfreeze endpoint becomes reachable, otherwise a stale lease can
        # overwrite a concurrent new freeze window.
        self._recover_fsfreeze_leases()
        http_server = kvmagent.get_http_server()
        # Register first so a stuck VM cannot make the whole ZRM API surface
        # disappear.  The wrapper fails closed only for VMs whose target-node
        # ownership has not been reconciled yet.
        for path, handler in (
                (self.PATH_REPLICATION_START, self.zrm_replication_start),
                (self.PATH_REPLICATION_STOP, self.zrm_replication_stop),
                (self.PATH_REPLICATION_PAUSE, self.zrm_replication_pause),
                (self.PATH_REPLICATION_RESUME, self.zrm_replication_resume),
                (self.PATH_REPLICATION_SYNC, self.zrm_replication_sync),
                (self.PATH_REPLICATION_WAIT_INITIAL,
                 self.zrm_replication_wait_initial),
                (self.PATH_BITMAP_CREATE, self.zrm_bitmap_create),
                (self.PATH_CHECKPOINT_CREATE, self.zrm_checkpoint_create),
                (self.PATH_RECOVERY_PREPARE, self.zrm_recovery_prepare),
                (self.PATH_REPLICATION_THROTTLE,
                 self.zrm_replication_throttle),
                (self.PATH_REPLICATION_GUEST_FSFREEZE,
                 self.zrm_replication_guest_fsfreeze)):
            registered_handler = handler
            if path in self._TARGET_RECOVERY_GUARDED_PATHS:
                registered_handler = self._guard_target_recovery(handler)
            http_server.register_async_uri(path, registered_handler)
        self._start_runtime_recovery()
        logger.info("ZRM plugin started: registered /zrm/* paths as async URIs")

    def stop(self):
        self._ensure_runtime_state()
        self._runtime_stopping = True
        with self._runtime_state_init_lock:
            recovery_stop_event = self._target_recovery_stop_event
            recovery_thread = self._target_recovery_thread
        recovery_stop_event.set()
        leases = [(vm_uuid, state.get("leaseId"))
                  for vm_uuid, state in list(self._fsfreeze_watchdogs.items())]
        for vm_uuid, lease_id in leases:
            self._auto_thaw_linux_guest(vm_uuid, lease_id, retry=False)
        for state in list(self._mirror_target_cleanup_retries.values()):
            timer = state.get("timer")
            if timer:
                timer.cancel()
        self._join_target_recovery_thread(recovery_thread)

    def configure(self, config):
        self.config = config

    @staticmethod
    def _request_vm_uuid(req):
        try:
            body = req.get(http.REQUEST_BODY) if req else None
            if not body:
                return None
            parsed = json.loads(body) if isinstance(body, _str_types) else body
            if isinstance(parsed, dict):
                return (parsed.get("vmUuid") or "").strip() or None
            return (getattr(parsed, "vmUuid", None) or "").strip() or None
        except Exception:
            # Preserve each handler's existing validation/error response for
            # malformed requests instead of replacing it in the guard.
            return None

    def _is_target_recovery_ready(self, vm_uuid):
        self._ensure_runtime_state()
        with self._runtime_state_init_lock:
            if not self._target_recovery_discovery_complete:
                return False
            return vm_uuid not in self._target_recovery_pending_vms

    def _guard_target_recovery(self, handler):
        def guarded(req):
            vm_uuid = self._request_vm_uuid(req)
            if vm_uuid and not self._is_target_recovery_ready(vm_uuid):
                recovery_error = (self._target_recovery_errors.get(vm_uuid)
                                  or self._target_recovery_discovery_error)
                error = "ZRM runtime recovery is still in progress for vm %s" % vm_uuid
                if recovery_error:
                    error = "%s: %s" % (error, recovery_error)
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error=error,
                    errorCode="ZRM_RUNTIME_RECOVERY_IN_PROGRESS",
                    retryable=True))
            return handler(req)
        return guarded



    @staticmethod
    def _block_struct_contains_volume(obj, volume_uuid):
        """
        Recursively check whether any string value in a nested dict/list
        structure contains the given volume_uuid.

        Delegates to vm_plugin._block_struct_contains_volume_uuid when
        available; keeps a local fallback to avoid a hard dependency.
        """
        try:
            from kvmagent.plugins.vm_plugin import _block_struct_contains_volume_uuid
            return _block_struct_contains_volume_uuid(obj, volume_uuid)
        except ImportError:
            pass
        # Inline fallback (same logic) when vm_plugin is unavailable.
        if isinstance(obj, _str_types):
            return volume_uuid in obj
        if isinstance(obj, dict):
            for v in obj.values():
                if ZrmPlugin._block_struct_contains_volume(v, volume_uuid):
                    return True
        elif isinstance(obj, list):
            for v in obj:
                if ZrmPlugin._block_struct_contains_volume(v, volume_uuid):
                    return True
        return False

    def _get_drive_name_from_domain_xml(self, vm_uuid, volume_uuid):
        """
        Look up the disk in libvirt domain XML by volumeUuid and return a
        CDP-style drive name (drive-<alias>).

        The logic is aligned with vm_plugin.get_disk_device_name /
        _get_target_disk to ensure VMs started with -drive can be mirrored
        correctly. Returns None if the disk cannot be found or if domain XML
        is not available (to avoid hard dependency on vm_plugin / libvirt).
        """
        if not vm_uuid or not volume_uuid:
            return None
        vol_str = volume_uuid if isinstance(volume_uuid, str) else str(volume_uuid)
        try:
            from kvmagent.plugins.vm_plugin import get_vm_by_uuid
            vm = get_vm_by_uuid(vm_uuid, exception_if_not_existing=False)
            if not vm or not getattr(vm, "domain_xmlobject", None):
                return None
            disks = vm.domain_xmlobject.devices.get_child_node_as_list("disk")
            if not disks:
                return None
            for disk in disks:
                # Skip disks without a source (e.g. cdrom without media)
                if not getattr(disk, "source", None):
                    continue
                path = None
                if getattr(disk.source, "file_", None):
                    path = disk.source.file_
                elif getattr(disk.source, "dev_", None):
                    path = disk.source.dev_
                elif getattr(disk.source, "name_", None):
                    path = disk.source.name_
                elif getattr(disk.source, "path_", None):
                    path = disk.source.path_
                if not path or vol_str not in (path or ""):
                    continue
                alias = getattr(getattr(disk, "alias", None), "name_", None)
                if not alias:
                    continue
                drive_name = ("drive-" if getattr(disk, "type_", None) != "quorum" else "") + alias
                logger.debug("ZRM drive name from domain XML: volume=%s -> %s" % (vol_str[:MIRROR_JOB_UUID_TRUNCATE_LEN], drive_name))
                return drive_name
        except Exception as e:
            logger.debug("ZRM get drive from domain XML failed: %s" % e)
        return None

    def _parse_nbd_url(self, nbd_url):
        """
        Parse an NBD URL of the form nbd://host:port/export into
        (host, port, export_name).

        The port is converted to int; the export part defaults to an
        empty string when omitted. Returns None if parsing fails.
        """
        if not nbd_url or not isinstance(nbd_url, _str_types):
            return None
        s = (nbd_url or "").strip()
        # Reject characters that can create shell/log ambiguity even though QMP
        # execution itself is argv-based. Percent escapes are also rejected so
        # ownership uses one canonical spelling for a target.
        if re.search(r"[\x00-\x20\x7f'\"\\;#?%]", s):
            return None
        try:
            parsed = urlsplit(s)
            if (parsed.scheme or "").lower() != "nbd":
                return None
            if parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None:
                return None
            host = parsed.hostname
            port = parsed.port
            if not host or port is None or port < 1 or port > 65535:
                return None
            if not self._is_valid_nbd_host(host):
                return None
            path = parsed.path or ""
            export = path[1:] if path.startswith("/") else path
            if "/" in export or (export and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", export)):
                return None
            return host.lower(), port, export
        except (ValueError, AttributeError, TypeError):
            return None

    @staticmethod
    def _is_valid_nbd_host(host):
        """Accept an IPv4/IPv6 literal or a conservative DNS hostname."""
        try:
            socket.inet_pton(socket.AF_INET, host)
            return True
        except (socket.error, ValueError):
            pass
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return True
        except (socket.error, ValueError):
            pass
        if len(host) > 253:
            return False
        labels = host[:-1].split(".") if host.endswith(".") else host.split(".")
        return bool(labels) and all(
            re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$", label)
            for label in labels)

    def _normalize_nbd_base_url(self, nbd_url):
        parsed = self._parse_nbd_url(nbd_url)
        if not parsed:
            return None
        host, port, export_name = parsed
        if export_name:
            return None
        display_host = "[%s]" % host if ":" in host else host
        return "nbd://%s:%d" % (display_host, port)

    @staticmethod
    def _hash_text(value, length=12):
        if not isinstance(value, bytes):
            value = (value or "").encode("utf-8")
        return hashlib.sha256(value).hexdigest()[:length]

    def _mirror_volume_component(self, volume_uuid):
        volume_uuid = (volume_uuid or "").strip()
        component = re.sub(r"[^A-Za-z0-9_.-]", "-", volume_uuid)
        if component != volume_uuid or len(component) > 64:
            component = "h%s" % self._hash_text(volume_uuid, 32)
        return component

    def _mirror_job_id(self, volume_uuid, session_uuid, normalized_target):
        """Bind a QMP job ID to the full volume plus session/target identity."""
        volume_component = self._mirror_volume_component(volume_uuid)
        session_token = self._hash_text((session_uuid or "").strip())
        target_token = self._hash_text(normalized_target)
        return "%s%s-s%s-t%s" % (
            _MIRROR_JOB_PREFIX, volume_component, session_token, target_token)

    def _job_matches_volume(self, job_id, volume_uuid):
        if not job_id:
            return False
        new_prefix = "%s%s-s" % (_MIRROR_JOB_PREFIX, self._mirror_volume_component(volume_uuid))
        legacy_id = "%s%s" % (_MIRROR_JOB_PREFIX,
                                (volume_uuid or "")[:MIRROR_JOB_UUID_TRUNCATE_LEN])
        return job_id.startswith(new_prefix) or job_id == legacy_id

    def _job_matches_session(self, job_id, session_uuid):
        if not session_uuid or not job_id or "-s" not in job_id:
            return True
        return "-s%s-t" % self._hash_text(session_uuid.strip()) in job_id

    def _remember_mirror_job_owner(self, vm_uuid, job_id, volume_uuid,
                                   session_uuid, normalized_target):
        self._ensure_runtime_state()
        self._mirror_job_owners[(vm_uuid, job_id)] = {
            "volumeUuid": volume_uuid,
            "sessionUuid": session_uuid or "",
            "targetNbdUrl": normalized_target,
        }

    def _forget_mirror_job_owner(self, vm_uuid, job_id):
        self._ensure_runtime_state()
        self._mirror_job_owners.pop((vm_uuid, job_id), None)

    @classmethod
    def _target_node_for_job(cls, job_id):
        """Return a deterministic QEMU block node name within the 31-byte limit."""
        digest_length = _QEMU_BLOCK_NODE_NAME_MAX - len(_MIRROR_TARGET_NODE_PREFIX)
        return "%s%s" % (
            _MIRROR_TARGET_NODE_PREFIX,
            cls._hash_text(job_id or "", digest_length))

    @staticmethod
    def _legacy_target_node_for_job(job_id):
        """Return the target-node name used before job IDs were hashed."""
        suffix = (job_id[len(_MIRROR_JOB_PREFIX):]
                  if job_id and job_id.startswith(_MIRROR_JOB_PREFIX)
                  else job_id)
        return "%s%s" % (_MIRROR_TARGET_NODE_PREFIX, suffix or "")

    @classmethod
    def _target_node_candidates_for_job(cls, job_id):
        current_node = cls._target_node_for_job(job_id)
        legacy_node = cls._legacy_target_node_for_job(job_id)
        is_current_job_id = bool(re.search(
            r"-s[0-9a-f]{12}-t[0-9a-f]{12}$", job_id or ""))
        candidates = ([current_node, legacy_node] if is_current_job_id
                      else [legacy_node, current_node])
        result = []
        for candidate in candidates:
            if candidate not in result:
                result.append(candidate)
        return result

    def _get_mirror_target_lock(self, vm_uuid, node_name):
        self._ensure_runtime_state()
        lock_key = "%s\0%s" % (vm_uuid, node_name)
        lock_index = int(self._hash_text(lock_key, 8), 16)
        return self._mirror_target_locks[
            lock_index % len(self._mirror_target_locks)]

    def _remember_mirror_target_node(self, vm_uuid, job_id, node_name):
        self._ensure_runtime_state()
        with self._get_mirror_target_lock(vm_uuid, node_name):
            with self._mirror_target_nodes_lock:
                self._mirror_target_nodes[(vm_uuid, job_id)] = node_name

    def _cancel_mirror_target_cleanup_retry(self, vm_uuid, job_id, token=None):
        self._ensure_runtime_state()
        key = (vm_uuid, job_id)
        state = self._mirror_target_cleanup_retries.get(key)
        if not state or (token is not None and state.get("token") != token):
            return False
        timer = state.get("timer")
        if timer:
            timer.cancel()
        self._mirror_target_cleanup_retries.pop(key, None)
        return True

    def _cancel_mirror_target_cleanup_retries_for_node(self, vm_uuid, node_name):
        for (retry_vm_uuid, retry_job_id), state in list(
                self._mirror_target_cleanup_retries.items()):
            if retry_vm_uuid == vm_uuid and state.get("nodeName") == node_name:
                self._cancel_mirror_target_cleanup_retry(
                    retry_vm_uuid, retry_job_id, state.get("token"))

    def _schedule_mirror_target_cleanup_retry(self, vm_uuid, job_id, node_name,
                                              attempts_remaining=None, token=None):
        """Keep failed cleanup ownership and retry it a bounded number of times."""
        self._ensure_runtime_state()
        key = (vm_uuid, job_id)
        with self._get_mirror_target_lock(vm_uuid, node_name):
            old_state = self._mirror_target_cleanup_retries.get(key)
            if old_state:
                old_timer = old_state.get("timer")
                if old_timer:
                    old_timer.cancel()
            token = token or uuid.uuid4().hex
            attempts_remaining = (attempts_remaining if attempts_remaining is not None
                                  else _MIRROR_TARGET_CLEANUP_RETRIES)
            timer = threading.Timer(
                _MIRROR_TARGET_CLEANUP_RETRY_SECONDS,
                self._retry_mirror_target_cleanup,
                args=[vm_uuid, job_id, node_name, token])
            timer.daemon = True
            self._mirror_target_cleanup_retries[key] = {
                "nodeName": node_name,
                "token": token,
                "attemptsRemaining": attempts_remaining,
                "timer": timer,
            }
            timer.start()

    def _retry_mirror_target_cleanup(self, vm_uuid, job_id, node_name, token):
        key = (vm_uuid, job_id)
        with self._get_mirror_target_lock(vm_uuid, node_name):
            state = self._mirror_target_cleanup_retries.get(key)
            if not state or state.get("token") != token:
                return

            # A new start can reuse the deterministic job/node identity.  Never
            # let an old orphan-cleanup callback delete a target of a live job.
            jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if not query_error and job_id in jobs:
                self._cancel_mirror_target_cleanup_retry(vm_uuid, job_id, token)
                return

            cleaned, cleanup_error = self._cleanup_mirror_target_node(
                vm_uuid, job_id, node_name=node_name, queue_retry=False)
            if cleaned:
                self._cancel_mirror_target_cleanup_retry(vm_uuid, job_id, token)
                return

            attempts_remaining = int(state.get("attemptsRemaining") or 0) - 1
            if attempts_remaining <= 0:
                self._cancel_mirror_target_cleanup_retry(vm_uuid, job_id, token)
                logger.warn(
                    "ZRM target node cleanup retries exhausted vm=%s node=%s: %s" %
                    (vm_uuid, node_name, cleanup_error))
                return
            self._schedule_mirror_target_cleanup_retry(
                vm_uuid, job_id, node_name,
                attempts_remaining=attempts_remaining, token=token)

    def _cleanup_mirror_target_node(self, vm_uuid, job_id, node_name=None,
                                    queue_retry=True, command_timeout=None):
        """Delete a fallback block node after its mirror job has settled."""
        self._ensure_runtime_state()
        key = (vm_uuid, job_id)
        target_node = node_name
        if not target_node:
            with self._mirror_target_nodes_lock:
                target_node = self._mirror_target_nodes.get(key)
        if not target_node:
            try:
                qmp_kwargs = ({"command_timeout": command_timeout}
                              if command_timeout is not None else {})
                nodes = qmp.execute_qmp_command(
                    vm_uuid, "query-named-block-nodes",
                    raise_exception=True, **qmp_kwargs) or []
            except Exception as ex:
                return False, "cannot discover target block node for %s: %s" % (
                    job_id, ex)
            node_names = set(
                (node or {}).get("node-name") for node in nodes)
            existing_candidates = [
                candidate
                for candidate in self._target_node_candidates_for_job(job_id)
                if candidate in node_names]
            if not existing_candidates:
                return True, None

            cleanup_errors = []
            for candidate in existing_candidates:
                self._remember_mirror_target_node(
                    vm_uuid, job_id, candidate)
                cleaned, cleanup_error = self._cleanup_mirror_target_node(
                    vm_uuid, job_id, node_name=candidate,
                    queue_retry=queue_retry,
                    command_timeout=command_timeout)
                if not cleaned:
                    cleanup_errors.append(cleanup_error)
            if cleanup_errors:
                return False, "; ".join(cleanup_errors)
            return True, None
        with self._get_mirror_target_lock(vm_uuid, target_node):
            if command_timeout is None:
                jobs, job_query_error = self._query_zrm_block_jobs(vm_uuid)
            else:
                jobs, job_query_error = self._query_zrm_block_jobs(
                    vm_uuid, command_timeout=command_timeout)
            if job_query_error:
                cleanup_error = (
                    "cannot verify target block node %s is orphaned: %s" %
                    (target_node, job_query_error))
                if queue_retry:
                    self._schedule_mirror_target_cleanup_retry(
                        vm_uuid, job_id, target_node)
                return False, cleanup_error
            with self._mirror_target_nodes_lock:
                owner_job_ids = set(
                    owner_key[1] for owner_key, owned_node in
                    self._mirror_target_nodes.items()
                    if owner_key[0] == vm_uuid and owned_node == target_node)
            owner_job_ids.add(job_id)
            live_owner_ids = owner_job_ids.intersection(set(jobs.keys()))
            if live_owner_ids:
                return False, "target block node %s belongs to active job(s): %s" % (
                    target_node, ", ".join(sorted(live_owner_ids)))

            delete_error = None
            try:
                blockdev_del = {
                    "execute": "blockdev-del",
                    "arguments": {"node-name": target_node}}
                if command_timeout is None:
                    execute_qmp_command_raw(
                        vm_uuid, json.dumps(blockdev_del),
                        raise_exception=True)
                else:
                    execute_qmp_command_raw(
                        vm_uuid, json.dumps(blockdev_del),
                        raise_exception=True,
                        command_timeout=command_timeout)
            except Exception as ex:
                delete_error = str(ex)

            try:
                qmp_kwargs = ({"command_timeout": command_timeout}
                              if command_timeout is not None else {})
                nodes = qmp.execute_qmp_command(
                    vm_uuid, "query-named-block-nodes", raise_exception=True,
                    **qmp_kwargs) or []
                target_exists = any(
                    (node or {}).get("node-name") == target_node for node in nodes)
            except Exception as ex:
                cleanup_error = "cannot verify target block node %s removal: %s" % (
                    target_node, ex)
                if delete_error:
                    cleanup_error = "%s; blockdev-del failed: %s" % (
                        cleanup_error, delete_error)
                if queue_retry:
                    self._schedule_mirror_target_cleanup_retry(
                        vm_uuid, job_id, target_node)
                return False, cleanup_error

            if target_exists:
                cleanup_error = "target block node %s still exists after blockdev-del" % target_node
                if delete_error:
                    cleanup_error = "%s: %s" % (cleanup_error, delete_error)
                if queue_retry:
                    self._schedule_mirror_target_cleanup_retry(
                        vm_uuid, job_id, target_node)
                return False, cleanup_error

            # Drop ownership only after QMP proves the node is absent.
            with self._mirror_target_nodes_lock:
                for owner_key, owned_node in list(
                        self._mirror_target_nodes.items()):
                    if owner_key[0] == vm_uuid and owned_node == target_node:
                        self._mirror_target_nodes.pop(owner_key, None)
            self._cancel_mirror_target_cleanup_retries_for_node(
                vm_uuid, target_node)
            return True, None

    def _try_blockdev_mirror_to_nbd(self, vm_uuid, node_name, nbd_url, job_id, sync_mode, bitmap_name):
        """
        Fallback path when all drive-mirror attempts fail: create an NBD client
        node via blockdev-add and then run blockdev-mirror to that node.

        This is mainly used for -blockdev setups where devices are only
        addressable by node-name and drive-mirror fails with root node errors.
        node_name is the source BDS node name (for example libvirt-2-format);
        sync_mode is either 'full' or 'incremental'; bitmap_name is required
        for incremental sync. Returns ``(success, error)``.
        """
        parsed = self._parse_nbd_url(nbd_url)
        if not parsed or not node_name:
            return False, "invalid NBD URL or source node for blockdev-mirror fallback"
        host, port, export_name = parsed
        if not export_name:
            logger.warn("ZRM blockdev-mirror fallback: nbd export name empty")
            return False, "NBD export name is empty"
        if not job_id:
            logger.warn("ZRM blockdev-mirror fallback: empty job_id, skipping")
            return False, "mirror job ID is empty"

        # Derive a compact deterministic target node from the complete job ID.
        # Serialize create/cleanup for this identity so a stale retry callback
        # cannot delete a newly-created target node.
        tgt_node = self._target_node_for_job(job_id)
        with self._get_mirror_target_lock(vm_uuid, tgt_node):
            cleaned, cleanup_error = self._cleanup_mirror_target_node(
                vm_uuid, job_id, node_name=tgt_node)
            if not cleaned:
                fallback_error = (
                    "cannot prepare blockdev-mirror target %s: %s" %
                    (tgt_node, cleanup_error))
                logger.warn(fallback_error)
                return False, fallback_error
            target_add_attempted = False
            try:
                # blockdev-add: wrap the NBD client with a raw node; QEMU requires the target to be an existing node.
                blockdev_add = {
                    "execute": "blockdev-add",
                    "arguments": {
                        "driver": "raw",
                        "node-name": tgt_node,
                        "file": {
                            "driver": "nbd",
                            "server": {"type": "inet", "host": host, "port": str(port)},
                            "export": export_name
                        }
                    }
                }
                target_add_attempted = True
                execute_qmp_command_raw(vm_uuid, json.dumps(blockdev_add), raise_exception=True)
                # Record ownership immediately.  If the subsequent mirror or
                # cleanup fails, stop/recovery and the retry queue can still
                # discover this node.
                self._remember_mirror_target_node(vm_uuid, job_id, tgt_node)
                # blockdev-mirror: device is the source node-name, target is the NBD node just added.
                mirror_args = {
                    "device": node_name,
                    "target": tgt_node,
                    "sync": sync_mode,
                    "job-id": job_id,
                    "auto-finalize": False,
                    "auto-dismiss": False
                }
                if bitmap_name and sync_mode == "incremental":
                    mirror_args["bitmap"] = bitmap_name
                qmp.execute_qmp_command(vm_uuid, "blockdev-mirror", raise_exception=True, **mirror_args)
                logger.info("ZRM replication start: blockdev-mirror fallback ok for node=%s -> %s (target=%s)" % (node_name, nbd_url, tgt_node))
                return True, None
            except Exception as e:
                fallback_error = "blockdev-mirror fallback failed: %s" % e
                if target_add_attempted:
                    self._remember_mirror_target_node(
                        vm_uuid, job_id, tgt_node)
                    cleaned, cleanup_error = self._cleanup_mirror_target_node(
                        vm_uuid, job_id, node_name=tgt_node)
                    if not cleaned:
                        fallback_error = "%s; target node cleanup failed: %s" % (
                            fallback_error, cleanup_error)
                        logger.warn("ZRM blockdev-mirror fallback cleanup failed for %s: %s" %
                                    (tgt_node, cleanup_error))
                logger.warn(fallback_error)
                return False, fallback_error

    def _get_block_device_for_volume_uuid(self, domain_uuid, volume_uuid):
        """
        Locate the block device for a volume using QMP query-block.

        Delegates to ``vm_plugin.get_mirror_device_for_volume_uuid`` which
        walks the QEMU block graph for accurate root-node resolution, then
        falls back to a simple query-block scan if the import fails.

        Returns (device_name, node_name) for drive-mirror usage.
        """
        if not volume_uuid or not domain_uuid:
            return None, None
        # Prefer the authoritative implementation in vm_plugin.
        try:
            from kvmagent.plugins.vm_plugin import get_mirror_device_for_volume_uuid
            node, device = get_mirror_device_for_volume_uuid(domain_uuid, volume_uuid)
            if node or device:
                return device or node, node or device
        except Exception as e:
            logger.debug("ZRM vm_plugin.get_mirror_device_for_volume_uuid unavailable: %s" % e)

        # Lightweight fallback: scan query-block without block-graph walk.
        blocks = self._query_blocks_for_vm(domain_uuid)
        return self._find_block_entry_for_volume(blocks, volume_uuid)

    def _query_blocks_for_vm(self, domain_uuid):
        """
        Perform a single query-block for the VM and return a normalized list
        of block entries (list of dict).

        This allows _start_mirrors_for_zr to reuse results across volumes and
        avoid issuing one QMP query per volume, which would slow down API
        responses. Returns None on failure or empty result.
        """
        if not domain_uuid:
            return None
        try:
            blocks = qmp.execute_qmp_command(domain_uuid, "query-block", raise_exception=False)
        except Exception as e:
            logger.warn("ZRM query-block failed for vm[uuid:%s]: %s" % (domain_uuid, e))
            return None
        if not blocks:
            return None
        if isinstance(blocks, dict):
            blocks = list(blocks.values())
        return [b for b in (blocks or []) if isinstance(b, dict)]

    @staticmethod
    def _extract_device_node_from_block_entry(entry):
        """
        Extract (device, node_name) from a single query-block entry dict.

        Shared by _find_block_entry_for_volume and the fallback path of
        _get_block_device_for_volume_uuid to avoid duplicating the
        device/qdev/node-name resolution logic.
        Returns (device_or_None, node_name_or_None).
        """
        device = entry.get("device") or ""
        if not isinstance(device, _str_types) or not device.strip():
            device = None
        qdev = entry.get("qdev") or entry.get("Qdev") or ""
        if not isinstance(qdev, _str_types):
            qdev = str(qdev) if qdev else ""
        if (not device or not device.strip()) and qdev.strip():
            parts = qdev.strip().rstrip("/").split("/")
            for p in reversed(parts):
                if p and p not in ("virtio-backend", "machine", "peripheral", "scsi-backend"):
                    device = p
                    break
        node_name = None
        inserted = entry.get("inserted") or {}
        if isinstance(inserted, dict):
            node_name = inserted.get("node-name")
        if not node_name:
            node_name = entry.get("node-name") or entry.get("node")
        if node_name and not isinstance(node_name, _str_types):
            node_name = str(node_name)
        return device, node_name

    def _find_block_entry_for_volume(self, blocks_list, volume_uuid):
        """
        Find the query-block entry that contains the given volumeUuid from a
        pre-fetched blocks_list and return (device, node_name).

        Returns (None, None) when not found or when blocks_list is None.
        """
        if not blocks_list or not volume_uuid:
            return None, None
        vol_str = volume_uuid if isinstance(volume_uuid, str) else str(volume_uuid)
        for b in blocks_list:
            if not self._block_struct_contains_volume(b, vol_str):
                continue
            device, node_name = self._extract_device_node_from_block_entry(b)
            if device or node_name:
                return device or node_name, node_name or device
        return None, None

    def _diagnose_block_topology(self, vm_uuid, volume_uuid, node_name_used):
        """
        Diagnose libvirt/QEMU block topology for a given volume and node name.

        Uses query-block to record the inserted node-name, device and qdev for
        the volume, then delegates to ``vm_plugin._find_root_block_node`` to
        walk ``x-debug-query-block-graph`` and determine the root block-driver
        node.  Returns (suggested_root_node_name or None, summary_string).
        """
        if not vm_uuid or not volume_uuid:
            return None, ""
        vol_str = volume_uuid if isinstance(volume_uuid, str) else str(volume_uuid)
        summary_parts = []

        # 1) query-block: record inserted (root), device and qdev for the volume.
        try:
            blocks = qmp.execute_qmp_command(vm_uuid, "query-block", raise_exception=False)
        except Exception as e:
            summary_parts.append("query-block failed: %s" % e)
            return None, "; ".join(summary_parts)
        if blocks:
            if isinstance(blocks, dict):
                blocks = list(blocks.values())
            for b in (blocks or []):
                if not isinstance(b, dict) or not self._block_struct_contains_volume(b, vol_str):
                    continue
                inserted = b.get("inserted") or {}
                ins_node = inserted.get("node-name") if isinstance(inserted, dict) else None
                dev = b.get("device") or ""
                qdev = b.get("qdev") or b.get("Qdev") or ""
                summary_parts.append("query-block: inserted.node-name=%s device=%s qdev=%s" % (ins_node, dev or "(empty)", (qdev or "(empty)")[:60]))
                break
        if not summary_parts:
            summary_parts.append("query-block: no block containing volume")

        # 2) Delegate block-graph walk to vm_plugin._find_root_block_node.
        #    It handles the x-debug-query-block-graph QMP call, capability
        #    caching, and the upward traversal.  If the command is unsupported
        #    it returns node_name_used unchanged (no-op).
        suggested_root = None
        try:
            from kvmagent.plugins.vm_plugin import _find_root_block_node
            root_name = _find_root_block_node(vm_uuid, node_name_used)
            if root_name and root_name != node_name_used:
                suggested_root = root_name
                summary_parts.append("block-graph: node '%s' is NOT root; root of chain is '%s'" %
                                     (node_name_used, root_name))
            elif root_name == node_name_used:
                summary_parts.append("block-graph: node '%s' is ROOT (or graph unavailable)" % node_name_used)
        except Exception as e:
            summary_parts.append("block-graph walk failed: %s" % e)

        return suggested_root, "; ".join(summary_parts)

    def _zrm_bitmap_name(self, volume_uuid):
        """Return the fixed per-volume bitmap name for ZRM, distinct from CDP's zsbm- prefix."""
        return ZRM_BITMAP_PREFIX + (volume_uuid or "")[:BITMAP_UUID_TRUNCATE_LEN]

    def _has_dirty_bitmap(self, domain_uuid, node_name, bitmap_name):
        """Return True/False for bitmap presence, or None when QMP query fails."""
        if not node_name or not bitmap_name:
            return False
        try:
            nodes = qmp.execute_qmp_command(
                domain_uuid, "query-named-block-nodes", raise_exception=True) or []
            for node in nodes:
                if (node or {}).get("node-name") != node_name:
                    continue
                bitmaps = (node or {}).get("dirty-bitmaps") or []
                return any((bitmap or {}).get("name") == bitmap_name for bitmap in bitmaps)

            # Some older QEMU versions expose bitmaps only under query-block's
            # inserted node.  A successful query with no matching node means
            # the bitmap is absent; a query failure must propagate as unknown.
            blocks = qmp.execute_qmp_command(
                domain_uuid, "query-block", raise_exception=True) or []
            for entry in blocks:
                inserted = (entry or {}).get("inserted") or (entry or {}).get("image") or {}
                current_node = inserted.get("node-name") or (entry or {}).get("device")
                if current_node != node_name:
                    continue
                bitmaps = inserted.get("dirty-bitmaps") or []
                return any((bitmap or {}).get("name") == bitmap_name for bitmap in bitmaps)
            return False
        except Exception as ex:
            logger.warn("ZRM dirty bitmap query failed: vm=%s node=%s name=%s error=%s" %
                        (domain_uuid, node_name, bitmap_name, ex))
            return None

    def _add_dirty_bitmap(self, domain_uuid, node_name, bitmap_name):
        """Create a dirty bitmap on the given block node using QMP block-dirty-bitmap-add."""
        if not node_name or not bitmap_name:
            return False
        try:
            # Use a full arguments dict to avoid collisions with qmp.execute_qmp_command's name parameter.
            qmp_cmd = {"execute": "block-dirty-bitmap-add", "arguments": {"node": node_name, "name": bitmap_name}}
            execute_qmp_command_raw(domain_uuid, json.dumps(qmp_cmd), raise_exception=True)
            logger.info("ZRM bitmap added: vm=%s node=%s name=%s" % (domain_uuid, node_name, bitmap_name))
            return True
        except Exception as e:
            logger.warn("ZRM block-dirty-bitmap-add failed: %s" % e)
            return False

    def _remove_dirty_bitmap(self, domain_uuid, node_name, bitmap_name):
        """Remove a dirty bitmap from the given block node using QMP block-dirty-bitmap-remove."""
        if not node_name or not bitmap_name:
            return False
        try:
            qmp_cmd = {"execute": "block-dirty-bitmap-remove", "arguments": {"node": node_name, "name": bitmap_name}}
            execute_qmp_command_raw(domain_uuid, json.dumps(qmp_cmd), raise_exception=True)
            logger.info("ZRM bitmap removed: vm=%s node=%s name=%s" % (domain_uuid, node_name, bitmap_name))
            return True
        except Exception as e:
            logger.warn("ZRM block-dirty-bitmap-remove failed: %s" % e)
            return False

    def _get_zrm_block_jobs(self, vm_uuid):
        """
        Query all ZR mirror jobs on the VM (devices starting with zrm-mirror-).

        Returns a mapping device -> job object that is used by the replication
        state machine to evaluate ready/running states.
        """
        by_dev = qmp.query_block_jobs_by_device(vm_uuid)
        if not by_dev:
            return {}
        return {k: v for k, v in by_dev.items() if k and (k.startswith("zrm-mirror-"))}

    def _query_zrm_block_jobs(self, vm_uuid, command_timeout=None):
        """
        Query all ZR mirror jobs and preserve observation failures.

        Returns a tuple ``(jobs, error_text)`` so callers that must distinguish
        "job missing" from "query path temporarily blocked" do not have to
        infer that from an empty map.
        """
        try:
            if command_timeout is None:
                by_dev = qmp.query_block_jobs_by_device(vm_uuid)
            else:
                by_dev = qmp.query_block_jobs_by_device(
                    vm_uuid, command_timeout=command_timeout)
        except Exception as e:
            err = str(e)
            logger.debug("ZRM query-block-jobs failed for vm %s: %s" % (vm_uuid, err))
            return {}, err
        if not by_dev:
            return {}, None
        return ({k: v for k, v in by_dev.items() if k and (k.startswith("zrm-mirror-"))}, None)

    def _cancel_and_settle_mirror_job(self, vm_uuid, job_id, timeout_seconds=5):
        """Cancel/dismiss one mirror job and prove that it disappeared."""
        jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
        if query_error:
            return False, "query-block-jobs failed before cancel: %s" % query_error
        current = jobs.get(job_id)
        if current:
            status = (current.get("status") or "").lower()
            if status == "concluded":
                qmp.execute_qmp_command(
                    vm_uuid, "job-dismiss", raise_exception=True, id=job_id)
            else:
                qmp.block_job_cancel(vm_uuid, job_id)

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return False, "query-block-jobs failed while settling %s: %s" % (job_id, query_error)
            current = jobs.get(job_id)
            if not current or (current.get("status") or "").lower() == "null":
                cleaned, cleanup_error = self._cleanup_mirror_target_node(vm_uuid, job_id)
                if not cleaned:
                    return False, "target node cleanup failed for %s: %s" % (job_id, cleanup_error)
                self._forget_mirror_job_owner(vm_uuid, job_id)
                return True, None
            status = (current.get("status") or "").lower()
            try:
                if status == "pending":
                    qmp.execute_qmp_command(
                        vm_uuid, "job-finalize", raise_exception=True, id=job_id)
                elif status == "concluded":
                    qmp.execute_qmp_command(
                        vm_uuid, "job-dismiss", raise_exception=True, id=job_id)
            except Exception as ex:
                logger.debug("ZRM mirror job %s settlement command failed: %s" % (job_id, ex))
            time.sleep(0.3)
        return False, "mirror job %s did not settle before timeout" % job_id

    def _collect_bitmap_status(self, vm_uuid):
        """
        Collect dirty bitmap status for all ZRM bitmaps on this VM.

        Returns a list of dicts, each containing:
          - name: bitmap name (e.g. "zrm-0e9d21d9c80046cf")
          - recording: True if the bitmap is actively recording writes
          - node: the block node name the bitmap is attached to

        This information helps the ZRM server decide whether incremental
        recovery is possible (bitmap intact) or a full sync is needed.
        """
        result = []
        try:
            block_info = qmp.execute_qmp_command(vm_uuid, "query-block", raise_exception=False)
            if not block_info:
                return result
            if isinstance(block_info, dict):
                block_info = list(block_info.values())
            for entry in (block_info or []):
                inserted = entry.get("inserted") or entry.get("image") or {}
                dirty_bitmaps = inserted.get("dirty-bitmaps") or []
                node_name = inserted.get("node-name") or entry.get("device") or ""
                for bm in dirty_bitmaps:
                    bm_name = bm.get("name") or ""
                    if bm_name.startswith(ZRM_BITMAP_PREFIX):
                        result.append({
                            "name": bm_name,
                            "recording": bm.get("recording", False),
                            "node": node_name
                        })
        except Exception as e:
            logger.debug("ZRM _collect_bitmap_status failed for vm %s: %s" % (vm_uuid, e))
        return result

    def _wait_initial_full_sync(self, vm_uuid, volume_uuids, timeout_seconds):
        """
        Wait for initial full mirror completion of the specified volumes.

        All zrm-mirror-* jobs for the volumes must reach a ready state
        (job.ready is True or status == "ready"). Returns a ZrmAgentRsp so
        the caller can distinguish ordinary timeout/not-ready from terminal
        concluded-job failures and missing-job conditions.
        """
        if isinstance(volume_uuids, (str, bytes)):
            volume_uuids = [volume_uuids] if volume_uuids else []
        vols = [v.strip() for v in (volume_uuids or []) if (v or "").strip()]
        if not vols:
            return ZrmAgentRsp(success=False, error="no volumeUuids specified for initial full sync wait")
        job_labels = ["zrm-mirror-%s" % v[:MIRROR_JOB_UUID_TRUNCATE_LEN] for v in vols]
        # Enforce a deadline to prevent indefinite thread blocking.
        effective_timeout = timeout_seconds if (timeout_seconds and timeout_seconds > 0) else _DEFAULT_MAX_WAIT_TIMEOUT
        deadline = time.time() + effective_timeout
        last_log_ts = 0.0
        query_retry_count = 0
        query_failure_start_ts = None
        while True:
            jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                now = time.time()
                query_retry_count += 1
                if query_failure_start_ts is None:
                    query_failure_start_ts = now
                if now >= deadline:
                    err = "initial full sync observation failed for vm=%s: query-block-jobs error=%s" % (
                        vm_uuid, query_error)
                    logger.warn("ZRM initial full sync wait: %s" % err)
                    total_query_failure_duration = now - query_failure_start_ts if query_failure_start_ts is not None else 0
                    return ZrmAgentRsp(
                        success=False,
                        error=err,
                        queryBlockJobsFailed=True,
                        queryBlockJobsError=query_error,
                        queryBlockJobsRetriable=True,
                        queryRetryCount=query_retry_count,
                        totalQueryFailureDuration=total_query_failure_duration,
                        readyJobCount=0,
                        runningJobCount=0,
                        concludedJobCount=0,
                        concludedJobErrors=[],
                        not_ready=[],
                        missing=[]
                    )
                if now - last_log_ts >= WAIT_INITIAL_LOG_INTERVAL:
                    logger.info("ZRM initial full sync wait: vm=%s query-block-jobs observation failed: %s" %
                                (vm_uuid, query_error))
                    last_log_ts = now
                time.sleep(1.0)
                continue
            query_retry_count = 0
            query_failure_start_ts = None
            not_ready = []
            missing = []
            ready_count = 0
            running_count = 0
            concluded_count = 0
            concluded_errors = []
            synced_bytes = 0
            target_bytes = 0
            for volume_uuid, job_label in zip(vols, job_labels):
                matching_job_ids = [job_id for job_id in jobs
                                    if self._job_matches_volume(job_id, volume_uuid)]
                if len(matching_job_ids) != 1:
                    missing.append(job_label if not matching_job_ids else
                                   "%s(ambiguous:%s)" % (job_label, matching_job_ids))
                    continue
                job_id = matching_job_ids[0]
                job = jobs[job_id]
                status = (job.get("status") or "").lower()
                ready = job.get("ready") is True or status == "ready"
                off = _to_long(job.get("offset"))
                ln = _to_long(job.get("len"))
                if off is not None and off > 0:
                    synced_bytes += off
                if ln is not None and ln > 0:
                    target_bytes += ln
                if not ready:
                    not_ready.append(job_id)
                    if status == "running":
                        running_count += 1
                    elif status == "concluded":
                        concluded_count += 1
                        err_text = job.get("error") or "no error detail"
                        concluded_errors.append({"device": job_id, "error": str(err_text)})
                        try:
                            qmp.execute_qmp_command(vm_uuid, "block-job-dismiss",
                                                    raise_exception=False, id=job_id)
                        except Exception:
                            pass
                else:
                    ready_count += 1
            if concluded_count > 0:
                err = "mirror job concluded during initial full sync for vm=%s: %s" % (
                    vm_uuid, concluded_errors)
                logger.warn("ZRM initial full sync wait: %s" % err)
                return ZrmAgentRsp(
                    success=False,
                    error=err,
                    lastSyncDataBytes=synced_bytes if synced_bytes > 0 else 0,
                    lastSyncBytes=synced_bytes if synced_bytes > 0 else 0,
                    totalSyncTargetBytes=target_bytes if target_bytes > 0 else 0,
                    readyJobCount=ready_count,
                    runningJobCount=running_count,
                    concludedJobCount=concluded_count,
                    concludedJobErrors=concluded_errors,
                    totalJobs=len(job_labels),
                    not_ready=not_ready,
                    missing=missing
                )
            now = time.time()
            if not not_ready and not missing:
                logger.info("ZRM initial full sync wait: all jobs ready for vm=%s volumes=%s" %
                            (vm_uuid, ",".join([v[:MIRROR_JOB_UUID_TRUNCATE_LEN] for v in vols])))
                return ZrmAgentRsp(
                    success=True,
                    lastSyncDataBytes=synced_bytes if synced_bytes > 0 else 0,
                    lastSyncBytes=synced_bytes if synced_bytes > 0 else 0,
                    totalSyncTargetBytes=target_bytes if target_bytes > 0 else 0,
                    readyJobCount=ready_count,
                    runningJobCount=running_count,
                    concludedJobCount=0,
                    concludedJobErrors=[],
                    totalJobs=len(job_labels)
                )
            if now >= deadline:
                err = "initial full sync timeout for vm=%s, not_ready=%s, missing=%s" % (
                    vm_uuid, ",".join(not_ready), ",".join(missing))
                logger.warn("ZRM initial full sync wait: %s" % err)
                return ZrmAgentRsp(
                    success=False,
                    error=err,
                    lastSyncDataBytes=synced_bytes if synced_bytes > 0 else 0,
                    lastSyncBytes=synced_bytes if synced_bytes > 0 else 0,
                    totalSyncTargetBytes=target_bytes if target_bytes > 0 else 0,
                    readyJobCount=ready_count,
                    runningJobCount=running_count,
                    concludedJobCount=concluded_count,
                    concludedJobErrors=concluded_errors,
                    totalJobs=len(job_labels),
                    not_ready=not_ready,
                    missing=missing
                )
            if now - last_log_ts >= WAIT_INITIAL_LOG_INTERVAL:
                logger.info("ZRM initial full sync wait: vm=%s not_ready=%s missing=%s" %
                            (vm_uuid, ",".join(not_ready), ",".join(missing)))
                last_log_ts = now
            time.sleep(1.0)

    def _build_mirror_candidates(self, vm_uuid, vol_uuid, device, node_name, blocks_cache):
        """
        Build an ordered list of QEMU device/node identifiers to try for
        drive-mirror, from most specific to most generic:

          1. BDS node-name (from _get_block_device_for_volume_uuid, which
             already delegates to vm_plugin's block-graph walker)
          2. Domain XML drive name (drive-<alias>)
          3. qdev path from query-block
          4. drive-<device> heuristic
          5. Raw device name

        Returns a non-empty list.
        """
        candidates = []

        def _add(c):
            if c and c not in candidates:
                candidates.append(c)

        # 1. Node-name is the most reliable identifier for -blockdev VMs.
        _add(node_name)
        # 2. Domain XML drive name (libvirt alias).
        _add(self._get_drive_name_from_domain_xml(vm_uuid, vol_uuid))
        # 3. qdev path from cached query-block entry.
        if blocks_cache:
            for _b in blocks_cache:
                if self._block_struct_contains_volume(_b, vol_uuid):
                    qdev_path = _b.get("qdev") or _b.get("Qdev")
                    if isinstance(qdev_path, _str_types) and qdev_path:
                        _add(qdev_path)
                    break
        # 4. drive-<device> heuristic (for -drive style VMs).
        _dev = device or node_name
        if _dev and not _dev.startswith("drive-") and not _dev.startswith("#") and "format" not in _dev:
            _add("drive-" + _dev)
        # 5. Raw device name.
        _add(device)

        return candidates if candidates else [node_name or device]

    @staticmethod
    def _normalize_qmp_volume_uuids(qmp_volume_uuids):
        """Return only explicit export-volume -> QMP-volume string mappings."""
        if isinstance(qmp_volume_uuids, dict):
            entries = qmp_volume_uuids.items()
        elif hasattr(qmp_volume_uuids, "__dict__"):
            # jsonobject.loads produces JsonObject for JSON maps.
            entries = qmp_volume_uuids.__dict__.items()
        else:
            return {}
        result = {}
        for export_uuid, qmp_uuid in entries:
            if not isinstance(export_uuid, _str_types) or not isinstance(qmp_uuid, _str_types):
                continue
            export_uuid = export_uuid.strip()
            qmp_uuid = qmp_uuid.strip()
            if export_uuid and qmp_uuid and export_uuid != qmp_uuid:
                result[export_uuid] = qmp_uuid
        return result

    def _start_mirrors_for_zr(self, vm_uuid, volume_uuids, target_nbd_base_url,
                              sync_mode_hint=None, qmp_volume_uuids=None,
                              session_uuid=None):
        """
        Start drive-mirror replication to the target NBD for each volume.

        target_nbd_base_url is of the form nbd://host:port; the ZR server
        exports each volume as vol-{volumeUuid}. If a volume already has a
        dirty bitmap, use sync=incremental to send only dirty blocks; otherwise
        add a bitmap and start with sync=full. The state machine completes any
        ready ZR jobs (block-job-complete) before starting a new mirror, and
        reuses running jobs.

        sync_mode_hint: optional hint from ZRM:
          - 'INCREMENTAL': prefer incremental sync via dirty bitmap; error if bitmap not found
          - 'FULL_SYNC': force full sync, remove existing bitmap first
          - None/empty: auto-detect (existing behavior)
        """
        if isinstance(volume_uuids, (_str_types, bytes)):
            volume_uuids = [volume_uuids] if volume_uuids else []
        if not volume_uuids:
            return "no volumeUuids or volumeUuid in command"
        base = self._normalize_nbd_base_url(target_nbd_base_url)
        if not base:
            return "targetNbdUrl must be nbd://host:port with a valid host and integer port"
        # Reuse a single query-block result for all volumes to keep API latency low.
        blocks_cache = self._query_blocks_for_vm(vm_uuid)
        # Pre-query all ZR jobs on this VM for use by the per-volume state machine.
        zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
        qmp_volume_uuids = self._normalize_qmp_volume_uuids(qmp_volume_uuids)
        first_error = None
        for vol_uuid in volume_uuids:
            vol_uuid = (vol_uuid or "").strip()
            if not vol_uuid:
                continue
            # ZR exports the recovery inventory UUID.  A recovered REGISTER_VM
            # can still expose the original source UUID in QMP, so use the
            # explicitly verified mapping for local block-node lookup only.
            qmp_vol_uuid = qmp_volume_uuids.get(vol_uuid, vol_uuid)
            # Bind the QMP job to this complete volume/session/target tuple.
            # A job from another session or NBD target must never be reused.
            job_id = self._mirror_job_id(vol_uuid, session_uuid, base)
            related_jobs = [(existing_id, existing_job)
                            for existing_id, existing_job in zrm_jobs.items()
                            if self._job_matches_volume(existing_id, vol_uuid)]
            ownership_error = None
            for existing_id, unused_job in related_jobs:
                if existing_id == job_id:
                    continue
                settled, settle_error = self._cancel_and_settle_mirror_job(
                    vm_uuid, existing_id)
                if not settled:
                    ownership_error = (
                        "cannot replace mirror job %s for volume %s: %s" %
                        (existing_id, vol_uuid, settle_error))
                    break
                zrm_jobs.pop(existing_id, None)
            if ownership_error:
                if first_error is None:
                    first_error = ownership_error
                continue
            existing = zrm_jobs.get(job_id)
            if existing:
                status = (existing.get("status") or "").lower()
                ready = existing.get("ready") is True or status == "ready"
                paused = existing.get("paused") is True
                err_text = existing.get("error")
                reusable_running = ((status == "running") and (not paused) and (not err_text)) or (ready and (not err_text) and status != "concluded")
                if reusable_running:
                    self._remember_mirror_job_owner(
                        vm_uuid, job_id, vol_uuid, session_uuid, base)
                    logger.info("ZRM replication start: volume %s already has running mirror job %s, reuse" % (vol_uuid[:MIRROR_JOB_UUID_TRUNCATE_LEN], job_id))
                    continue
                else:
                    settled, settle_error = self._cancel_and_settle_mirror_job(vm_uuid, job_id)
                    if not settled:
                        err = "cannot restart mirror job %s: %s" % (job_id, settle_error)
                        if first_error is None:
                            first_error = err
                        continue
                    logger.info("ZRM replication start: cleared stale mirror job %s for volume %s (status=%s paused=%s error=%s)" %
                                (job_id, vol_uuid[:MIRROR_JOB_UUID_TRUNCATE_LEN], status, paused, err_text if err_text else ""))
            nbd_url = "%s/vol-%s" % (base, vol_uuid)
            # Resolve device/node_name -- _get_block_device_for_volume_uuid already
            # delegates to vm_plugin.get_mirror_device_for_volume_uuid internally.
            device, node_name = self._find_block_entry_for_volume(blocks_cache, qmp_vol_uuid) if blocks_cache else (None, None)
            if not device and not node_name:
                device, node_name = self._get_block_device_for_volume_uuid(vm_uuid, qmp_vol_uuid)
            if not device and not node_name:
                err = "no block device found for volume %s (QMP volume %s) on vm %s (query-block)" % (vol_uuid, qmp_vol_uuid, vm_uuid)
                logger.warn("ZRM replication start: %s" % err)
                if first_error is None:
                    first_error = err
                continue
            mirror_candidates = self._build_mirror_candidates(
                vm_uuid, qmp_vol_uuid, device, node_name, blocks_cache)
            bitmap_node = node_name or device
            logger.debug("ZRM replication volume=%s qmp_volume=%s mirror_candidates=%s bitmap_node=%s" %
                         (vol_uuid[:MIRROR_JOB_UUID_TRUNCATE_LEN],
                          qmp_vol_uuid[:MIRROR_JOB_UUID_TRUNCATE_LEN],
                          mirror_candidates, bitmap_node))
            bitmap_name = self._zrm_bitmap_name(vol_uuid)
            has_bitmap = self._has_dirty_bitmap(vm_uuid, bitmap_node, bitmap_name)
            if has_bitmap is None:
                err = "unable to verify dirty bitmap %s for volume %s" % (bitmap_name, vol_uuid)
                logger.warn("ZRM replication start: %s" % err)
                if first_error is None:
                    first_error = err
                continue
            hint = (sync_mode_hint or "").strip().upper()
            if hint == "FULL_SYNC":
                # Force full sync: remove existing bitmap so we start clean.
                if has_bitmap:
                    self._remove_dirty_bitmap(vm_uuid, bitmap_node, bitmap_name)
                    logger.info("ZRM replication start: FULL_SYNC forced, removed existing bitmap for %s" % vol_uuid)
                    has_bitmap = False
                # Create fresh bitmap to track writes from this point.
                if not self._add_dirty_bitmap(vm_uuid, bitmap_node, bitmap_name):
                    logger.warn("ZRM replication start: add bitmap failed for %s" % vol_uuid)
                sync_mode = "full"
            elif hint == "INCREMENTAL":
                if has_bitmap:
                    sync_mode = "incremental"
                    logger.info("ZRM replication start: INCREMENTAL mode, bitmap found for %s" % vol_uuid)
                else:
                    err = "syncMode=INCREMENTAL but no dirty bitmap found for volume %s -- bitmap must exist before incremental sync" % vol_uuid
                    logger.warn("ZRM replication start: %s" % err)
                    if first_error is None:
                        first_error = err
                    continue
            else:
                # AUTO: use bitmap if exists, otherwise full
                if has_bitmap:
                    sync_mode = "incremental"
                    logger.info("ZRM replication start: auto-detected existing bitmap for %s, using incremental" % vol_uuid)
                else:
                    if not self._add_dirty_bitmap(vm_uuid, bitmap_node, bitmap_name):
                        logger.warn("ZRM replication start: add bitmap failed for %s, continue with sync=full" % vol_uuid)
                    sync_mode = "full"
            base_mirror_kw = dict(
                job_id=job_id, target=nbd_url, mode="existing", format="nbd", sync=sync_mode,
                auto_finalize=False, auto_dismiss=False
            )
            if sync_mode == "incremental" and bitmap_name:
                base_mirror_kw["bitmap"] = bitmap_name
            last_err = RuntimeError("no usable mirror device for volume %s" % vol_uuid)
            for mirror_device in mirror_candidates:
                if not mirror_device:
                    continue
                mirror_kw = dict(device=mirror_device, **base_mirror_kw)
                try:
                    qmp.execute_qmp_command(vm_uuid, "drive-mirror", raise_exception=True, **mirror_kw)
                    logger.info("ZRM replication start: drive-mirror %s for volume %s -> %s (device=%s)" % (sync_mode, vol_uuid, nbd_url, mirror_device))
                    last_err = None
                    break
                except Exception as e:
                    err_str = str(e)
                    # Retry with next candidate when device is not found or root node is required.
                    if "Cannot find device" in err_str or "Need a root block node" in err_str:
                        logger.debug("ZRM drive-mirror device=%s failed (%s), try next candidate" % (mirror_device, err_str[:80]))
                        last_err = e
                        continue
                    last_err = e
                    break
            # If all drive-mirror candidates fail, diagnose block topology, then try the suggested root or blockdev fallback.
            if last_err is not None:
                suggested_root, topo_summary = self._diagnose_block_topology(
                    vm_uuid, qmp_vol_uuid, node_name or device)
                logger.warn("ZRM replication topology diagnosis volume=%s: %s" % (vol_uuid[:MIRROR_JOB_UUID_TRUNCATE_LEN], topo_summary))
                if suggested_root and suggested_root not in mirror_candidates:
                    try:
                        mirror_kw = dict(device=suggested_root, **base_mirror_kw)
                        qmp.execute_qmp_command(vm_uuid, "drive-mirror", raise_exception=True, **mirror_kw)
                        logger.info("ZRM replication start: drive-mirror ok with topology-suggested device=%s" % suggested_root)
                        last_err = None
                    except Exception as e:
                        logger.debug("ZRM drive-mirror device=%s (from topology) failed: %s" % (suggested_root, e))
            if last_err is not None and node_name:
                fallback_ok, fallback_error = self._try_blockdev_mirror_to_nbd(
                    vm_uuid, node_name, nbd_url, job_id, sync_mode, bitmap_name)
                if fallback_ok:
                    last_err = None
                elif fallback_error:
                    # Surface cleanup failures to the control plane instead of
                    # hiding them behind the preceding drive-mirror error.
                    last_err = RuntimeError(fallback_error)
            if last_err is not None:
                err = "drive-mirror failed for volume %s: %s" % (vol_uuid, last_err)
                logger.warn("ZRM replication start: %s" % err)
                if first_error is None:
                    first_error = err
            else:
                self._remember_mirror_job_owner(
                    vm_uuid, job_id, vol_uuid, session_uuid, base)
        return first_error

    def _replication_start(self, req):
        """
        Start replication: validate targetNbdUrl and issue drive-mirror to the
        target NBD for each volume in volumeUuids/volumeUuid so that VM writes
        flow to the ZR server.

        Note: jsonobject.loads returns a JsonObject which does not implement
        .get; use getattr(cmd, 'key', None) to access fields.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            target_nbd_url = (getattr(cmd, "targetNbdUrl", None) or "").strip()
            if not target_nbd_url:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="targetNbdUrl required for replication (call target ZR session/prepare and addvolume first)"
                ))
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            volume_uuids = getattr(cmd, "volumeUuids", None) or []
            if not volume_uuids:
                single = getattr(cmd, "volumeUuid", None)
                volume_uuids = [single] if single else []
            sync_mode_hint = (getattr(cmd, "syncMode", None) or "").strip()
            qmp_volume_uuids = getattr(cmd, "qmpVolumeUuids", None)
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            err = self._start_mirrors_for_zr(
                vm_uuid, volume_uuids, target_nbd_url, sync_mode_hint,
                qmp_volume_uuids, session_uuid=session_uuid)
            if err:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error=err))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication start failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    @kvmagent.replyerror
    def zrm_replication_start(self, req):
        return self._replication_start(req)

    def _replication_stop(self, req):
        """
        Stop all ZR mirror jobs on the VM by issuing block-job-cancel for
        devices whose names start with zrm-mirror-.

        The request body must contain vmUuid (and an optional sessionUuid).
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error))
            zrm_jobs = {device: job for device, job in zrm_jobs.items()
                        if self._job_matches_session(device, session_uuid)}
            cancelled_devices = []
            cancel_failed_jobs = []
            for device in zrm_jobs:
                try:
                    qmp.block_job_cancel(vm_uuid, device)
                    cancelled_devices.append(device)
                    logger.info("ZRM replication stop: cancel requested for job %s on vm %s" % (device, vm_uuid))
                except Exception as cancel_err:
                    err_msg = str(cancel_err)
                    cancel_failed_jobs.append({"device": device, "error": err_msg})
                    logger.warn("ZRM replication stop: cancel failed for %s: %s" % (device, err_msg))
            # Wait for cancelled jobs to disappear.  ZR mirrors are created with
            # auto-finalize=False, so a successful cancel can legitimately leave
            # the job in pending until job-finalize is issued.  A finalized job
            # then remains concluded because auto-dismiss is also disabled.
            # block_job_cancel suppresses QMP command errors, so the post-cancel
            # query is the authoritative proof that recovery can safely continue.
            stale_jobs = []
            if cancelled_devices:
                post_cancel_query_error = None
                _stop_deadline = time.time() + 10
                while time.time() < _stop_deadline:
                    remaining, query_error = self._query_zrm_block_jobs(vm_uuid)
                    if query_error:
                        post_cancel_query_error = query_error
                        break
                    unsettled = []
                    for d in cancelled_devices:
                        if d not in remaining:
                            continue
                        status = (remaining[d].get("status") or "").lower()
                        if status == "null":
                            continue
                        unsettled.append(d)
                        if status == "pending":
                            try:
                                qmp.execute_qmp_command(vm_uuid, "job-finalize",
                                                        raise_exception=True, id=d)
                                logger.info("ZRM replication stop: finalized pending job %s on vm %s" %
                                            (d, vm_uuid))
                            except Exception as finalize_err:
                                # The job can change state between query and command;
                                # the next query remains the source of truth.
                                logger.debug("ZRM replication stop: finalize pending job %s on vm %s failed: %s" %
                                             (d, vm_uuid, finalize_err))
                        elif status == "concluded":
                            try:
                                qmp.execute_qmp_command(vm_uuid, "job-dismiss",
                                                        raise_exception=True, id=d)
                                logger.info("ZRM replication stop: dismissed concluded job %s on vm %s" %
                                            (d, vm_uuid))
                            except Exception as dismiss_err:
                                logger.debug("ZRM replication stop: dismiss concluded job %s on vm %s failed: %s" %
                                             (d, vm_uuid, dismiss_err))
                    if not unsettled:
                        break
                    time.sleep(0.5)
                if post_cancel_query_error:
                    return jsonobject.dumps(ZrmAgentRsp(
                        success=False,
                        error="query-block-jobs failed after cancel: %s" % post_cancel_query_error,
                        queryBlockJobsFailed=True,
                        queryBlockJobsError=post_cancel_query_error,
                        cancelRequestedDevices=cancelled_devices))
                # Detect stale jobs that survived the cancel deadline.
                remaining, query_error = self._query_zrm_block_jobs(vm_uuid)
                if query_error:
                    return jsonobject.dumps(ZrmAgentRsp(
                        success=False,
                        error="query-block-jobs failed after cancel: %s" % query_error,
                        queryBlockJobsFailed=True,
                        queryBlockJobsError=query_error,
                        cancelRequestedDevices=cancelled_devices))
                for d in cancelled_devices:
                    if d in remaining:
                        st = (remaining[d].get("status") or "unknown").lower()
                        if st == "null":
                            continue
                        stale_jobs.append({"device": d, "status": st})
                        logger.warn("ZRM replication stop: stale job %s (status=%s) on vm %s after cancel deadline" %
                                    (d, st, vm_uuid))
                if not stale_jobs:
                    logger.info("ZRM replication stop: all cancel requests settled for vm %s" % vm_uuid)
            cleanup_failures = []
            stale_devices = set(item["device"] for item in stale_jobs)
            for device in cancelled_devices:
                if device in stale_devices:
                    continue
                cleaned, cleanup_error = self._cleanup_mirror_target_node(vm_uuid, device)
                if not cleaned:
                    cleanup_failures.append({"device": device, "error": cleanup_error})
                else:
                    self._forget_mirror_job_owner(vm_uuid, device)

            rsp = ZrmAgentRsp()
            if cancel_failed_jobs:
                rsp.success = False
                rsp.error = "failed to cancel ZRM mirror jobs: %s" % cancel_failed_jobs
                rsp.cancelFailedJobs = cancel_failed_jobs
            if stale_jobs:
                rsp.success = False
                stale_error = "stale ZRM mirror jobs remain after cancel deadline: %s" % stale_jobs
                rsp.error = "%s; %s" % (rsp.error, stale_error) if rsp.error else stale_error
                rsp.staleJobs = stale_jobs
            if cleanup_failures:
                rsp.success = False
                cleanup_error = "failed to delete settled mirror target nodes: %s" % cleanup_failures
                rsp.error = "%s; %s" % (rsp.error, cleanup_error) if rsp.error else cleanup_error
                rsp.targetNodeCleanupFailures = cleanup_failures
            return jsonobject.dumps(rsp)
        except Exception as e:
            logger.exception("ZRM replication stop failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _replication_pause(self, req):
        """
        Pause all running ZRM mirror jobs on the VM by issuing block-job-pause
        for each zrm-mirror-* device.

        QMP ``block-job-pause`` suspends write mirroring; dirty writes are
        still tracked by the bitmap so that a subsequent resume can catch up
        without a full re-sync.

        Request body: vmUuid (required), sessionUuid (optional).
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error))
            zrm_jobs = {device: job for device, job in zrm_jobs.items()
                        if self._job_matches_session(device, session_uuid)}
            if not zrm_jobs:
                logger.info("ZRM replication pause: no zrm mirror jobs on vm %s" % vm_uuid)
                return jsonobject.dumps(ZrmAgentRsp())
            paused_devices = []
            errors = []
            for device, job in zrm_jobs.items():
                status = (job.get("status") or "").lower()
                already_paused = job.get("paused") is True
                if already_paused:
                    logger.debug("ZRM replication pause: job %s already paused on vm %s" % (device, vm_uuid))
                    paused_devices.append(device)
                    continue
                if status not in ("running", "ready"):
                    logger.debug("ZRM replication pause: skipping job %s (status=%s) on vm %s" % (device, status, vm_uuid))
                    continue
                try:
                    qmp.execute_qmp_command(vm_uuid, "block-job-pause", device=device)
                    paused_devices.append(device)
                    logger.info("ZRM replication pause: paused job %s on vm %s" % (device, vm_uuid))
                except Exception as pause_err:
                    err_msg = "failed to pause job %s: %s" % (device, pause_err)
                    logger.warn("ZRM replication pause: %s" % err_msg)
                    errors.append(err_msg)
            if errors:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="; ".join(errors)))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication pause failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _replication_resume(self, req):
        """
        Resume all paused ZRM mirror jobs on the VM by issuing block-job-resume
        for each paused zrm-mirror-* device.

        After resume, QEMU will re-sync any dirty regions tracked by the
        bitmap while the job was paused.

        Request body: vmUuid (required), sessionUuid (optional).
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error))
            zrm_jobs = {device: job for device, job in zrm_jobs.items()
                        if self._job_matches_session(device, session_uuid)}
            if not zrm_jobs:
                logger.info("ZRM replication resume: no zrm mirror jobs on vm %s" % vm_uuid)
                return jsonobject.dumps(ZrmAgentRsp())
            resumed_devices = []
            errors = []
            for device, job in zrm_jobs.items():
                paused = job.get("paused") is True
                if not paused:
                    logger.debug("ZRM replication resume: job %s not paused on vm %s, skip" % (device, vm_uuid))
                    continue
                try:
                    qmp.execute_qmp_command(vm_uuid, "block-job-resume", device=device)
                    resumed_devices.append(device)
                    logger.info("ZRM replication resume: resumed job %s on vm %s" % (device, vm_uuid))
                except Exception as resume_err:
                    err_msg = "failed to resume job %s: %s" % (device, resume_err)
                    logger.warn("ZRM replication resume: %s" % err_msg)
                    errors.append(err_msg)
            if errors:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="; ".join(errors)))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication resume failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _replication_sync(self, req):
        """
        Acknowledge sync for current ZR mirror jobs without pivoting VM disks.

        The request body must contain vmUuid (and an optional sessionUuid).
        volumeUuids are not required.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error))
            zrm_jobs = {device: job for device, job in zrm_jobs.items()
                        if self._job_matches_session(device, session_uuid)}
            ready_count = 0
            running_count = 0
            concluded_count = 0
            concluded_errors = []
            synced_bytes = 0
            target_bytes = 0

            for device, job in zrm_jobs.items():
                status = (job.get("status") or "").lower()
                ready = job.get("ready") is True or status == "ready"
                if ready:
                    ready_count += 1
                elif status == "running":
                    running_count += 1
                elif status == "concluded":
                    # A concluded mirror job means the job has finished -- possibly
                    # with an error (e.g. NBD target disconnected). We must report
                    # this to the ZRM so it can trigger recovery, and dismiss the
                    # job to clean up QEMU state (same as _start_mirrors_for_zr).
                    concluded_count += 1
                    err_text = job.get("error") or "no error detail"
                    concluded_errors.append({"device": device, "error": str(err_text)})
                    try:
                        qmp.execute_qmp_command(vm_uuid, "block-job-dismiss",
                                                raise_exception=False, id=device)
                    except Exception:
                        pass

                # query-block-jobs fields:
                #   offset: copied bytes so far for this mirror round
                #   len:    total bytes of this mirror round
                off = _to_long(job.get("offset"))
                ln = _to_long(job.get("len"))
                if off is not None and off > 0:
                    synced_bytes += off
                if ln is not None and ln > 0:
                    target_bytes += ln

            if concluded_count > 0:
                logger.warn("ZRM replication sync: vm=%s has %s CONCLUDED mirror jobs (errors: %s)" %
                            (vm_uuid, concluded_count, concluded_errors))
                # Collect bitmap status to help ZRM decide recovery strategy:
                # if bitmaps are intact, incremental sync is possible without full copy.
                bitmap_status = self._collect_bitmap_status(vm_uuid)
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="ZRM mirror job concluded during sync: %s" % concluded_errors,
                    lastSyncDataBytes=synced_bytes if synced_bytes > 0 else 0,
                    lastSyncBytes=synced_bytes if synced_bytes > 0 else 0,
                    totalSyncTargetBytes=target_bytes if target_bytes > 0 else 0,
                    readyJobCount=ready_count,
                    runningJobCount=running_count,
                    concludedJobCount=concluded_count,
                    concludedJobErrors=concluded_errors,
                    totalJobs=len(zrm_jobs),
                    bitmapStatus=bitmap_status
                ))
            if len(zrm_jobs) == 0:
                logger.warn("ZRM replication sync: vm=%s has no active zrm mirror jobs" % vm_uuid)
                bitmap_status = self._collect_bitmap_status(vm_uuid)
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="no active ZRM mirror jobs found for vm=%s" % vm_uuid,
                    lastSyncDataBytes=0,
                    lastSyncBytes=0,
                    totalSyncTargetBytes=0,
                    readyJobCount=0,
                    runningJobCount=0,
                    concludedJobCount=0,
                    concludedJobErrors=[],
                    totalJobs=0,
                    bitmapStatus=bitmap_status
                ))
            logger.info("ZRM replication sync: vm=%s ready_jobs=%s running_jobs=%s concluded_jobs=%s total_zrm_jobs=%s" %
                        (vm_uuid, ready_count, running_count, concluded_count, len(zrm_jobs)))
            return jsonobject.dumps(ZrmAgentRsp(
                success=True,
                lastSyncDataBytes=synced_bytes if synced_bytes > 0 else 0,
                lastSyncBytes=synced_bytes if synced_bytes > 0 else 0,
                totalSyncTargetBytes=target_bytes if target_bytes > 0 else 0,
                readyJobCount=ready_count,
                runningJobCount=running_count,
                concludedJobCount=concluded_count,
                concludedJobErrors=concluded_errors,
                totalJobs=len(zrm_jobs)
            ))
        except Exception as e:
            logger.exception("ZRM replication sync failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _replication_wait_initial(self, req):
        """
        Wait for initial full sync completion: block until all zrm-mirror-*
        jobs for the specified volumes reach ready state or timeout.

        Request body: vmUuid, volumeUuid/volumeUuids, timeoutSeconds (optional).
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            vol_uuid = getattr(cmd, "volumeUuid", None)
            vol_uuids = getattr(cmd, "volumeUuids", None)
            if vol_uuids is None and vol_uuid is not None:
                vol_uuids = [vol_uuid] if vol_uuid else []
            if vol_uuids is None:
                vol_uuids = []
            timeout_seconds = getattr(cmd, "timeoutSeconds", None)
            if timeout_seconds is None:
                timeout_seconds = 0
            rsp = self._wait_initial_full_sync(vm_uuid, vol_uuids,
                                               int(timeout_seconds) if timeout_seconds else 0)
            return jsonobject.dumps(rsp or ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication wait-initial failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    @kvmagent.replyerror
    def zrm_replication_stop(self, req):
        return self._replication_stop(req)

    @kvmagent.replyerror
    def zrm_replication_pause(self, req):
        return self._replication_pause(req)

    @kvmagent.replyerror
    def zrm_replication_resume(self, req):
        return self._replication_resume(req)

    @kvmagent.replyerror
    def zrm_replication_sync(self, req):
        return self._replication_sync(req)

    @kvmagent.replyerror
    def zrm_replication_wait_initial(self, req):
        return self._replication_wait_initial(req)

    def _bitmap_create(self, req):
        """
        Create dirty bitmaps for the specified VM volumes (similar to CDP/backup
        block-dirty-bitmap-add) so that subsequent replication/start calls can
        use sync=incremental.

        Request body: vmUuid, volumeUuid/volumeUuids, bitmapName (optional).
        Note: cmd is a JsonObject; use getattr(cmd, 'key', None) for fields.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            vol_uuid = getattr(cmd, "volumeUuid", None)
            vol_uuids = getattr(cmd, "volumeUuids", None)
            if vol_uuids is None and vol_uuid is not None:
                vol_uuids = [vol_uuid] if vol_uuid else []
            if vol_uuids is None:
                vol_uuids = []
            if isinstance(vol_uuids, (str, bytes)):
                vol_uuids = [vol_uuids] if vol_uuids else []
            bitmap_name_override = (getattr(cmd, "bitmapName", None) or "").strip()
            first_error = None
            for vu in vol_uuids:
                vu = (vu or "").strip()
                if not vu:
                    continue
                device, node_name = self._get_block_device_for_volume_uuid(vm_uuid, vu)
                if not node_name:
                    node_name = device
                if not node_name:
                    err = "no block device for volume %s on vm %s" % (vu, vm_uuid)
                    if first_error is None:
                        first_error = err
                    continue
                name = bitmap_name_override or self._zrm_bitmap_name(vu)
                has_bitmap = self._has_dirty_bitmap(vm_uuid, node_name, name)
                if has_bitmap is None:
                    err = "unable to verify dirty bitmap %s for volume %s" % (name, vu)
                    if first_error is None:
                        first_error = err
                    continue
                if has_bitmap:
                    logger.info("ZRM bitmap already exists: vm=%s vol=%s name=%s" % (vm_uuid, vu, name))
                    continue
                if not self._add_dirty_bitmap(vm_uuid, node_name, name):
                    err = "block-dirty-bitmap-add failed for volume %s" % vu
                    if first_error is None:
                        first_error = err
            if first_error:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error=first_error))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM bitmap create failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    @kvmagent.replyerror
    def zrm_bitmap_create(self, req):
        return self._bitmap_create(req)

    @kvmagent.replyerror
    def zrm_checkpoint_create(self, req):
        """
        Source-side checkpoint gate: ensure mirrors are converged before
        asking ZR Server to create an atomic checkpoint on the target.

        Sequence:
          A. Set mirror speed=0 (unlimited) and poll until allReady
          B. POST /zr/checkpoint/create to ZR Server
          C. Restore original mirror speed (best-effort)

        Request fields:
          vmUuid          - source VM UUID (required)
          sessionUuid     - ZR replication session UUID (required)
          checkpointUuid  - new checkpoint UUID (required)
          zrServerUrl     - ZR Server base URL, e.g. http://host:6800 (required)
          waitReadyTimeout - seconds to wait for mirror convergence (default 30)
          originalSpeed   - mirror speed (bytes/s) to restore after checkpoint.
                            0 means unlimited (no throttle); this is also the
                            default when the field is omitted. Pass the pre-
                            checkpoint throttle value if mirrors were rate-limited.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)

            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()
            checkpoint_uuid = (getattr(cmd, "checkpointUuid", None) or "").strip()
            zr_server_url = (getattr(cmd, "zrServerUrl", None) or "").strip()
            wait_timeout = int(getattr(cmd, "waitReadyTimeout", None) or 30)
            original_speed = int(getattr(cmd, "originalSpeed", None) or 0)

            if not all([vm_uuid, session_uuid, checkpoint_uuid, zr_server_url]):
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="vmUuid, sessionUuid, checkpointUuid, zrServerUrl are all required"))

            throttle_req = {
                http.REQUEST_BODY: json.dumps({
                    "vmUuid": vm_uuid,
                    "sessionUuid": session_uuid,
                    "speed": 0,
                    "waitReadyTimeout": wait_timeout
                })
            }
            result = None
            checkpoint_created = False
            restore_error = None
            restore_failures = None

            try:
                throttle_rsp_json = self._replication_throttle(throttle_req)
                throttle_rsp = jsonobject.loads(throttle_rsp_json)

                if not getattr(throttle_rsp, "success", True):
                    result = ZrmAgentRsp(
                        success=False,
                        error="mirror convergence failed: %s" % (getattr(throttle_rsp, "error", "") or ""))

                elif int(getattr(throttle_rsp, "totalJobs", 0) or 0) <= 0:
                    result = ZrmAgentRsp(
                        success=False,
                        error="mirror convergence failed: no active ZRM mirror jobs")

                elif not getattr(throttle_rsp, "allReady", False):
                    result = ZrmAgentRsp(
                        success=False,
                        error="mirrors not ready after %ds (ready=%s total=%s)" % (
                            wait_timeout,
                            getattr(throttle_rsp, "readyCount", "?"),
                            getattr(throttle_rsp, "totalJobs", "?")))
                else:
                    # Step B: POST to ZR Server /zr/checkpoint/create
                    url = zr_server_url.rstrip("/") + "/zr/checkpoint/create"
                    cp_body = json.dumps({"sessionUuid": session_uuid, "checkpointUuid": checkpoint_uuid})
                    zr_rsp_raw = http.json_post(url, body=cp_body, fail_soon=True)
                    zr_rsp = jsonobject.loads(zr_rsp_raw)

                    if not getattr(zr_rsp, "success", False):
                        result = ZrmAgentRsp(
                            success=False,
                            error="ZR Server checkpoint/create failed: %s" % (getattr(zr_rsp, "error", "") or ""))
                    else:
                        checkpoint_created = True
                        logger.info("zrm_checkpoint_create: vm=%s session=%s checkpoint=%s success" %
                                    (vm_uuid, session_uuid, checkpoint_uuid))
                        result = ZrmAgentRsp(checkpointUuid=checkpoint_uuid)
            except Exception as op_ex:
                logger.exception("zrm_checkpoint_create operation failed")
                result = ZrmAgentRsp(success=False, error=str(op_ex))
            finally:
                # Step C: restore original mirror speed; report failures to the caller.
                try:
                    restore_req = {
                        http.REQUEST_BODY: json.dumps({
                            "vmUuid": vm_uuid,
                            "sessionUuid": session_uuid,
                            "speed": original_speed,
                            "waitReadyTimeout": 0
                        })
                    }
                    restore_rsp_json = self._replication_throttle(restore_req)
                    try:
                        restore_body = json.loads(restore_rsp_json)
                    except Exception as parse_ex:
                        restore_body = None
                        restore_error = "unable to parse mirror speed restoration response: %s" % parse_ex
                    if restore_body is not None and not isinstance(restore_body, dict):
                        restore_error = "unexpected mirror speed restoration response: %s" % restore_body
                    elif restore_body is not None and not restore_body.get("success", True):
                        restore_error = restore_body.get("error") or "unknown mirror speed restoration failure"
                        restore_failures = restore_body.get("speedSetFailures")
                except Exception as restore_ex:
                    restore_error = str(restore_ex)
                if restore_error:
                    if checkpoint_created:
                        logger.error("zrm_checkpoint_create: failed to restore mirror speed for vm %s: %s "
                                     "(checkpoint %s created)" % (vm_uuid, restore_error, checkpoint_uuid))
                    else:
                        logger.warn("zrm_checkpoint_create: failed to restore mirror speed for vm %s: %s" %
                                    (vm_uuid, restore_error))

            if restore_error:
                original_error = getattr(result, "error", None) if result is not None else None
                error_msg = "mirror speed restoration failed: %s" % restore_error
                if checkpoint_created:
                    error_msg = (
                        "checkpoint %s created successfully but mirror speed restoration failed: %s. "
                        "Checkpoint is usable. ACTION REQUIRED: retry speed throttle to restore replication rate." % (
                            checkpoint_uuid, restore_error))
                elif original_error:
                    error_msg = error_msg + "; original checkpoint error: " + original_error
                rsp = ZrmAgentRsp(
                    success=(True if checkpoint_created else False),
                    error=error_msg,
                    checkpointUuid=checkpoint_uuid,
                    degraded=(True if checkpoint_created else False),
                    speedRestoreFailed=True,
                    speedRestoreError=restore_error)
                if restore_failures is not None:
                    rsp.speedRestoreFailures = restore_failures
                if original_error:
                    rsp.checkpointError = original_error
                return jsonobject.dumps(rsp)

            if result is None:
                logger.error(
                    "zrm_checkpoint_create: unexpected nil result for vm %s session %s checkpoint %s "
                    "(checkpoint_created=%s, restore_error=%s, restore_failures=%s)" % (
                        vm_uuid, session_uuid, checkpoint_uuid,
                        checkpoint_created, restore_error, restore_failures))
                result = ZrmAgentRsp(success=False, error="checkpoint operation did not produce response")
            return jsonobject.dumps(result)

        except Exception as e:
            logger.exception("zrm_checkpoint_create failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _vm_shutdown_and_isolate(self, vm_uuid, shutdown_timeout=_DEFAULT_SHUTDOWN_TIMEOUT, force_isolate=False):
        import libvirt
        import xml.etree.ElementTree as ET
        from kvmagent.plugins.vm_plugin import get_vm_by_uuid

        vm = get_vm_by_uuid(vm_uuid, exception_if_not_existing=False)
        if not vm or not getattr(vm, "domain", None):
            logger.info("_vm_shutdown_and_isolate: vm %s not found, treating as stopped" % vm_uuid)
            return True, None

        domain = vm.domain

        def _is_no_domain_error(ex):
            try:
                get_error_code = getattr(ex, "get_error_code", None)
                return bool(get_error_code) and get_error_code() == libvirt.VIR_ERR_NO_DOMAIN
            except Exception:
                return False

        if not force_isolate:
            try:
                state, _ = domain.state()
                if state == libvirt.VIR_DOMAIN_SHUTOFF:
                    logger.info("_vm_shutdown_and_isolate: vm %s already SHUTOFF" % vm_uuid)
                    return True, None
            except Exception as e:
                if _is_no_domain_error(e):
                    logger.info("_vm_shutdown_and_isolate: vm %s disappeared while checking state" % vm_uuid)
                    return True, None
                return False, "vm state check failed: %s" % e

            try:
                domain.shutdown()
            except Exception as e:
                logger.warn("_vm_shutdown_and_isolate: shutdown() failed for %s: %s, proceeding to poll" % (vm_uuid, e))

            deadline = time.time() + shutdown_timeout
            while time.time() < deadline:
                try:
                    state, _ = domain.state()
                    if state == libvirt.VIR_DOMAIN_SHUTOFF:
                        logger.info("_vm_shutdown_and_isolate: vm %s shut down cleanly" % vm_uuid)
                        return True, None
                except Exception as e:
                    if _is_no_domain_error(e):
                        logger.info("_vm_shutdown_and_isolate: vm %s disappeared while waiting for shutdown" % vm_uuid)
                        return True, None
                    return False, "vm state check failed: %s" % e
                time.sleep(1)

            logger.warn("_vm_shutdown_and_isolate: vm %s did not shut down in %ds, isolating network" %
                        (vm_uuid, shutdown_timeout))

        try:
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            ifaces = root.findall(".//devices/interface")
            if not ifaces:
                logger.info("_vm_shutdown_and_isolate: no interfaces to detach on vm %s" % vm_uuid)
                return True, None

            detached_count = 0
            detach_errors = []
            for iface in ifaces:
                iface_xml = ET.tostring(iface, encoding="unicode")
                try:
                    domain.detachDeviceFlags(iface_xml, libvirt.VIR_DOMAIN_AFFECT_LIVE)
                    detached_count += 1
                    logger.info("_vm_shutdown_and_isolate: detached vNIC on vm %s" % vm_uuid)
                except Exception as de:
                    detach_errors.append(str(de))
                    logger.warn("_vm_shutdown_and_isolate: detach vNIC failed on vm %s: %s (continuing)" %
                                (vm_uuid, de))
            if detach_errors:
                # Re-read XML to check whether NICs are actually still present.
                # A detach API error can fire for an NIC that was already absent
                # (e.g. concurrent removal); in that case isolation is still achieved.
                try:
                    remaining_ifaces = ET.fromstring(domain.XMLDesc(0)).findall(".//devices/interface")
                except Exception:
                    remaining_ifaces = ifaces  # conservative: assume still present on XML read failure
                if remaining_ifaces:
                    return False, "network isolation failed: %d vNIC(s) remain on vm %s; detach errors: %s" % (
                        len(remaining_ifaces), vm_uuid, "; ".join(detach_errors))
                logger.info("_vm_shutdown_and_isolate: all vNICs gone on vm %s (detach errors were for already-absent NICs)" % vm_uuid)
            return True, None

        except Exception as e:
            return False, "network isolation failed: " + str(e)

    @kvmagent.replyerror
    def zrm_recovery_prepare(self, req):
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)

            vm_uuid          = (getattr(cmd, "vmUuid", None) or "").strip()
            _timeout_val = getattr(cmd, "shutdownTimeout", None)
            shutdown_timeout = int(_timeout_val) if _timeout_val is not None else _DEFAULT_SHUTDOWN_TIMEOUT
            force_isolate    = bool(getattr(cmd, "forceIsolate", False))

            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))

            stop_rsp_json = self._replication_stop(req)
            try:
                stop_rsp = jsonobject.loads(stop_rsp_json)
                stop_success = getattr(stop_rsp, "success", True)
                stale_jobs = getattr(stop_rsp, "staleJobs", None)
                if not stop_success:
                    err = getattr(stop_rsp, "error", "unknown error")
                    rsp = ZrmAgentRsp(success=False,
                        error="replication_stop failed: %s" % err)
                    if getattr(stop_rsp, "queryBlockJobsFailed", False):
                        rsp.queryBlockJobsFailed = True
                        rsp.queryBlockJobsError = getattr(stop_rsp, "queryBlockJobsError", None)
                        cancel_requested_devices = getattr(stop_rsp, "cancelRequestedDevices", None)
                        if cancel_requested_devices is not None:
                            rsp.cancelRequestedDevices = cancel_requested_devices
                    return jsonobject.dumps(rsp)
                if stale_jobs:
                    return jsonobject.dumps(ZrmAgentRsp(success=False,
                        error="replication_stop: stale mirror jobs remain: %s" % stale_jobs))
            except Exception as e:
                return jsonobject.dumps(ZrmAgentRsp(success=False,
                    error="replication_stop response parse error: %s" % e))

            ok, err = self._vm_shutdown_and_isolate(vm_uuid, shutdown_timeout, force_isolate)
            if not ok:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error=err))

            logger.info("zrm_recovery_prepare: vm %s isolated (mirrors stopped, vm shutdown/isolated)" % vm_uuid)
            return jsonobject.dumps(ZrmAgentRsp())

        except Exception as e:
            logger.exception("zrm_recovery_prepare failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    @kvmagent.replyerror
    def zrm_replication_throttle(self, req):
        return self._replication_throttle(req)

    @kvmagent.replyerror
    def zrm_replication_guest_fsfreeze(self, req):
        return self._replication_guest_fsfreeze(req)

    def _get_vm_qga(self, vm_uuid):
        """Return a connected VmQga for vm_uuid, or (None, error_message) on failure."""
        try:
            from kvmagent.plugins.vm_plugin import get_vm_by_uuid
            vm = get_vm_by_uuid(vm_uuid)
            if not vm or not getattr(vm, "domain", None):
                return None, "unable to find vm domain: " + vm_uuid
            qga = VmQga(vm.domain)
            if qga.state != VmQga.QGA_STATE_RUNNING:
                return None, "QEMU Guest Agent not in running state for vm " + vm_uuid
            return qga, None
        except Exception as ex:
            return None, str(ex)

    def _guest_fsfreeze_response(self, success, fs_status, filesystem_count=0,
                                 error_message=None, guest_os_type=None,
                                 quiesce_provider=None, error_code=None):
        """Build agent response body compatible with ZRM GuestFsFreezeResult."""
        fields = {
            "success": success,
            "fsFreezeStatus": fs_status,
            "filesystemCount": filesystem_count,
        }
        if error_message is not None:
            fields["errorMessage"] = error_message
        if guest_os_type is not None:
            fields["guestOsType"] = guest_os_type
        if quiesce_provider is not None:
            fields["quiesceProvider"] = quiesce_provider
        if error_code is not None:
            fields["errorCode"] = error_code
        return jsonobject.dumps(ZrmAgentRsp(**fields))

    def _qga_supports_fsfreeze(self, qga):
        """Return whether QGA exposes and enables fsfreeze-related commands."""
        required = (
            self._FSFREEZE_CMD_FREEZE,
            self._FSFREEZE_CMD_THAW,
            self._FSFREEZE_CMD_STATUS,
        )
        for cmd in required:
            if cmd not in qga.supported_commands:
                return False, "QGA command not supported: " + cmd
            if not qga.supported_commands.get(cmd):
                return False, "QGA command disabled: " + cmd
        return True, None

    def _get_cached_linux_fsfreeze_count(self, qga):
        vm_uuid = getattr(qga, "vm_uuid", None)
        cache = getattr(self, "_linux_fsfreeze_counts", None) or {}
        try:
            return int(cache.get(vm_uuid, 0) or 0)
        except Exception:
            return 0

    def _set_cached_linux_fsfreeze_count(self, qga, fs_count):
        vm_uuid = getattr(qga, "vm_uuid", None)
        if not vm_uuid:
            return
        cache = getattr(self, "_linux_fsfreeze_counts", None)
        if cache is None:
            cache = {}
            self._linux_fsfreeze_counts = cache
        cache[vm_uuid] = fs_count if isinstance(fs_count, int) else 0

    def _clear_cached_linux_fsfreeze_count(self, qga):
        vm_uuid = getattr(qga, "vm_uuid", None)
        cache = getattr(self, "_linux_fsfreeze_counts", None)
        if vm_uuid and cache:
            cache.pop(vm_uuid, None)

    def _get_fsfreeze_vm_lock(self, vm_uuid):
        self._ensure_runtime_state()
        with self._runtime_state_init_lock:
            vm_lock = self._fsfreeze_vm_locks.get(vm_uuid)
            if vm_lock is None:
                vm_lock = threading.RLock()
                self._fsfreeze_vm_locks[vm_uuid] = vm_lock
            return vm_lock

    def _fsfreeze_lease_path(self, vm_uuid):
        return os.path.join(
            _FSFREEZE_LEASE_DIR,
            "%s.json" % self._hash_text(vm_uuid, 32))

    def _persist_fsfreeze_lease(self, vm_uuid, lease_id, deadline):
        if os.name == "nt":
            return
        if not os.path.isdir(_FSFREEZE_LEASE_DIR):
            try:
                os.makedirs(_FSFREEZE_LEASE_DIR)
            except OSError:
                if not os.path.isdir(_FSFREEZE_LEASE_DIR):
                    raise
        lease_path = self._fsfreeze_lease_path(vm_uuid)
        temp_path = "%s.%s.tmp" % (lease_path, lease_id)
        with open(temp_path, "w") as lease_file:
            json.dump({
                "vmUuid": vm_uuid,
                "leaseId": lease_id,
                "deadline": deadline,
            }, lease_file)
            lease_file.flush()
            os.fsync(lease_file.fileno())
        os.rename(temp_path, lease_path)

    def _remove_fsfreeze_lease_file(self, vm_uuid, lease_id):
        if os.name == "nt":
            return True
        lease_path = self._fsfreeze_lease_path(vm_uuid)
        if not os.path.exists(lease_path):
            return True
        try:
            with open(lease_path, "r") as lease_file:
                persisted_lease = json.load(lease_file)
            if persisted_lease.get("leaseId") != lease_id:
                return False
            os.remove(lease_path)
            return True
        except Exception as ex:
            logger.warn("ZRM failed to remove matching fsfreeze lease vm=%s lease=%s: %s" %
                        (vm_uuid, lease_id, ex))
            return False

    def _arm_fsfreeze_watchdog(self, vm_uuid, lease_seconds=None,
                               lease_id=None, deadline=None, persist=True):
        self._ensure_runtime_state()
        lease_seconds = max(5, int(lease_seconds or _DEFAULT_FSFREEZE_LEASE_SECONDS))
        lease_id = lease_id or uuid.uuid4().hex
        deadline = deadline if deadline is not None else time.time() + lease_seconds
        if persist:
            try:
                self._persist_fsfreeze_lease(vm_uuid, lease_id, deadline)
            except Exception as ex:
                # Never freeze a guest unless restart recovery has first been
                # made durable.  Do not install an in-memory-only watchdog.
                raise RuntimeError("failed to persist fsfreeze lease: %s" % ex)

        old_state = self._fsfreeze_watchdogs.get(vm_uuid)
        if old_state and old_state.get("timer"):
            old_state["timer"].cancel()
        delay = max(0.1, deadline - time.time())
        timer = threading.Timer(
            delay, self._auto_thaw_linux_guest, args=[vm_uuid, lease_id])
        timer.daemon = True
        self._fsfreeze_watchdogs[vm_uuid] = {
            "leaseId": lease_id,
            "deadline": deadline,
            "timer": timer,
        }
        timer.start()
        return lease_id

    def _cancel_fsfreeze_watchdog(self, vm_uuid, lease_id=None):
        self._ensure_runtime_state()
        state = self._fsfreeze_watchdogs.get(vm_uuid)
        if not state or (lease_id is not None and state.get("leaseId") != lease_id):
            return False
        removed_lease_id = state.get("leaseId")
        timer = state.get("timer")
        if timer:
            timer.cancel()
        self._fsfreeze_watchdogs.pop(vm_uuid, None)
        self._remove_fsfreeze_lease_file(vm_uuid, removed_lease_id)
        return True

    def _reschedule_auto_thaw(self, vm_uuid, lease_id):
        self._ensure_runtime_state()
        state = self._fsfreeze_watchdogs.get(vm_uuid)
        if not state or state.get("leaseId") != lease_id:
            return
        timer = threading.Timer(
            _FSFREEZE_RECOVERY_RETRY_SECONDS,
            self._auto_thaw_linux_guest,
            args=[vm_uuid, lease_id])
        timer.daemon = True
        state["timer"] = timer
        timer.start()

    def _best_effort_thaw_qga(self, qga, timeout_seconds):
        try:
            status = qga.call_qga_command(
                self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
            if status == "frozen":
                qga.call_qga_command(
                    self._FSFREEZE_CMD_THAW, timeout=timeout_seconds)
                status = qga.call_qga_command(
                    self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
            return status == "thawed", status
        except Exception as ex:
            logger.warn("ZRM emergency guest thaw failed for vm=%s: %s" %
                        (getattr(qga, "vm_uuid", "unknown"), ex))
            return False, str(ex)

    def _auto_thaw_linux_guest(self, vm_uuid, lease_id, retry=True):
        self._ensure_runtime_state()
        with self._get_fsfreeze_vm_lock(vm_uuid):
            # Validate only after acquiring the per-VM lock.  An expired timer
            # may have been waiting while a request replaced its lease.
            state = self._fsfreeze_watchdogs.get(vm_uuid)
            if not state or state.get("leaseId") != lease_id:
                return
            qga, qga_error = self._get_vm_qga(vm_uuid)
            if qga is None:
                logger.warn("ZRM fsfreeze lease auto-thaw waiting for vm=%s QGA: %s" %
                            (vm_uuid, qga_error))
                if retry:
                    self._reschedule_auto_thaw(vm_uuid, lease_id)
                return
            thawed, status = self._best_effort_thaw_qga(qga, 10)
            if thawed:
                self._clear_cached_linux_fsfreeze_count(qga)
                self._cancel_fsfreeze_watchdog(vm_uuid, lease_id)
                logger.warn("ZRM fsfreeze lease expired; automatically thawed vm=%s" % vm_uuid)
            elif retry:
                logger.warn("ZRM fsfreeze lease auto-thaw will retry vm=%s status=%s" %
                            (vm_uuid, status))
                self._reschedule_auto_thaw(vm_uuid, lease_id)

    def _recover_fsfreeze_leases(self):
        if os.name == "nt" or not os.path.isdir(_FSFREEZE_LEASE_DIR):
            return

        def read_lease(path):
            with open(path, "r") as lease_file:
                lease = json.load(lease_file)
            vm_uuid = (lease.get("vmUuid") or "").strip()
            lease_id = (lease.get("leaseId") or "").strip()
            deadline = float(lease.get("deadline"))
            if not vm_uuid or not lease_id:
                raise ValueError("invalid fsfreeze lease")
            return vm_uuid, lease_id, deadline

        for filename in os.listdir(_FSFREEZE_LEASE_DIR):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(_FSFREEZE_LEASE_DIR, filename)
            try:
                initial_vm_uuid = read_lease(path)[0]
            except Exception as ex:
                logger.warn("ZRM failed to recover fsfreeze lease %s: %s" % (path, ex))
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue

            # The initial read only identifies the lock.  Re-read under that
            # lock so a concurrent freeze that replaced lease A with B cannot
            # be overwritten by stale recovery state.
            with self._get_fsfreeze_vm_lock(initial_vm_uuid):
                try:
                    vm_uuid, lease_id, deadline = read_lease(path)
                except Exception as ex:
                    logger.warn("ZRM failed to re-read fsfreeze lease %s: %s" %
                                (path, ex))
                    continue
                if vm_uuid != initial_vm_uuid:
                    logger.warn("ZRM fsfreeze lease VM changed during recovery path=%s old=%s new=%s" %
                                (path, initial_vm_uuid, vm_uuid))
                    continue
                current_state = self._fsfreeze_watchdogs.get(vm_uuid)
                if current_state:
                    if current_state.get("leaseId") != lease_id:
                        logger.warn("ZRM ignored stale fsfreeze recovery vm=%s diskLease=%s activeLease=%s" %
                                    (vm_uuid, lease_id, current_state.get("leaseId")))
                    continue
                try:
                    self._arm_fsfreeze_watchdog(
                        vm_uuid, lease_id=lease_id,
                        deadline=deadline, persist=False)
                except Exception as ex:
                    logger.warn("ZRM failed to arm recovered fsfreeze lease %s: %s" %
                                (path, ex))

    @staticmethod
    def _target_recovery_vm_uuids():
        from kvmagent.plugins.vm_plugin import get_all_vm_states
        return sorted(list((get_all_vm_states() or {}).keys()))

    def _recover_mirror_target_nodes_for_vm(self, vm_uuid):
        """Reconcile one VM using only QMP calls with a hard deadline."""
        command_timeout = _TARGET_RECOVERY_QMP_TIMEOUT_SECONDS
        jobs, query_error = self._query_zrm_block_jobs(
            vm_uuid, command_timeout=command_timeout)
        if query_error:
            raise RuntimeError(query_error)

        nodes = qmp.execute_qmp_command(
            vm_uuid, "query-named-block-nodes", raise_exception=True,
            command_timeout=command_timeout) or []
        target_nodes = set(
            node.get("node-name") for node in nodes
            if (node.get("node-name") or "").startswith("zrm-tgt-"))
        owned_nodes = set()
        for job_id in jobs:
            for target_node in self._target_node_candidates_for_job(job_id):
                if target_node in target_nodes:
                    self._remember_mirror_target_node(
                        vm_uuid, job_id, target_node)
                    owned_nodes.add(target_node)
                    break

        cleanup_errors = []
        for orphan_node in target_nodes.difference(owned_nodes):
            orphan_job_id = "orphan-%s" % self._hash_text(orphan_node)
            self._remember_mirror_target_node(
                vm_uuid, orphan_job_id, orphan_node)
            cleaned, cleanup_error = self._cleanup_mirror_target_node(
                vm_uuid, orphan_job_id, node_name=orphan_node,
                queue_retry=False, command_timeout=command_timeout)
            if not cleaned:
                cleanup_errors.append("%s: %s" %
                                      (orphan_node, cleanup_error))
        if cleanup_errors:
            raise RuntimeError("; ".join(cleanup_errors))

    def _recover_mirror_target_nodes(self):
        """Synchronously reconcile all VMs; retained for diagnostics/tests."""
        try:
            vm_uuids = self._target_recovery_vm_uuids()
        except Exception as ex:
            logger.debug("ZRM mirror target recovery skipped: %s" % ex)
            return {"discovery": str(ex)}
        failures = {}
        for vm_uuid in vm_uuids:
            try:
                self._recover_mirror_target_nodes_for_vm(vm_uuid)
            except Exception as ex:
                failures[vm_uuid] = str(ex)
                logger.debug("ZRM mirror target recovery failed for vm=%s: %s" % (vm_uuid, ex))
        return failures

    def _is_target_recovery_generation_current(self, generation=None,
                                               stop_event=None):
        if generation is None:
            return True
        with self._runtime_state_init_lock:
            return (
                self._target_recovery_generation == generation and
                self._target_recovery_stop_event is stop_event)

    def _target_recovery_should_stop(self, stop_event=None, generation=None):
        if not self._is_target_recovery_generation_current(
                generation, stop_event):
            return True
        if stop_event is not None:
            if hasattr(stop_event, "is_set"):
                return stop_event.is_set()
            return stop_event.isSet()
        return self._runtime_stopping

    def _wait_for_target_recovery_retry(self, delay, stop_event=None,
                                        generation=None):
        if stop_event is not None:
            stop_event.wait(delay)
        else:
            time.sleep(delay)
        return self._target_recovery_should_stop(stop_event, generation)

    def _get_target_recovery_vm_lock(self, vm_uuid):
        lock_index = int(self._hash_text(vm_uuid or "", 8), 16)
        return self._target_recovery_vm_locks[
            lock_index % len(self._target_recovery_vm_locks)]

    def _recover_pending_target_vms(self, vm_uuids, stop_event=None,
                                    generation=None):
        """Recover a batch with bounded concurrency and per-VM readiness."""
        if not vm_uuids:
            return

        work_queue = queue.Queue()
        for vm_uuid in vm_uuids:
            work_queue.put(vm_uuid)

        def recover_worker():
            while not self._target_recovery_should_stop(
                    stop_event, generation):
                try:
                    vm_uuid = work_queue.get_nowait()
                except queue.Empty:
                    return
                with self._get_target_recovery_vm_lock(vm_uuid):
                    if self._target_recovery_should_stop(
                            stop_event, generation):
                        return
                    try:
                        self._recover_mirror_target_nodes_for_vm(vm_uuid)
                    except Exception as ex:
                        with self._runtime_state_init_lock:
                            if not self._is_target_recovery_generation_current(
                                    generation, stop_event):
                                return
                            self._target_recovery_errors[vm_uuid] = str(ex)
                        logger.warn(
                            "ZRM target recovery failed vm=%s: %s" %
                            (vm_uuid, ex))
                    else:
                        # Clear readiness immediately for this VM; other workers
                        # may still be reconciling unhealthy VMs.
                        with self._runtime_state_init_lock:
                            if not self._is_target_recovery_generation_current(
                                    generation, stop_event):
                                return
                            self._target_recovery_pending_vms.discard(vm_uuid)
                            self._target_recovery_errors.pop(vm_uuid, None)

        worker_count = min(_TARGET_RECOVERY_WORKERS, len(vm_uuids))
        workers = []
        for worker_index in range(worker_count):
            worker = threading.Thread(
                target=recover_worker,
                name="zrm-target-node-recovery-%s" % worker_index)
            worker.daemon = True
            try:
                worker.start()
            except Exception as ex:
                logger.warn("ZRM target recovery worker failed to start: %s" % ex)
                continue
            workers.append(worker)
        for worker in workers:
            worker.join()

    def _run_mirror_target_recovery(self, stop_event=None, generation=None):
        discovery_attempt = 0
        retry_delay = _TARGET_RECOVERY_INITIAL_BACKOFF_SECONDS
        while not self._target_recovery_should_stop(stop_event, generation):
            discovery_attempt += 1
            try:
                vm_uuids = self._target_recovery_vm_uuids()
                break
            except Exception as ex:
                with self._runtime_state_init_lock:
                    if not self._is_target_recovery_generation_current(
                            generation, stop_event):
                        return
                    self._target_recovery_discovery_error = str(ex)
                logger.warn(
                    "ZRM target recovery VM discovery failed attempt=%s: %s" %
                    (discovery_attempt, ex))
                if self._wait_for_target_recovery_retry(
                        retry_delay, stop_event, generation):
                    return
                retry_delay = min(
                    retry_delay * 2,
                    _TARGET_RECOVERY_MAX_BACKOFF_SECONDS)
        else:
            return

        if self._target_recovery_should_stop(stop_event, generation):
            return

        with self._runtime_state_init_lock:
            if not self._is_target_recovery_generation_current(
                    generation, stop_event):
                return
            self._target_recovery_pending_vms = set(vm_uuids)
            self._target_recovery_errors = {}
            self._target_recovery_discovery_error = None
            self._target_recovery_discovery_complete = True

        # Retry for the plugin lifetime with capped backoff.  A transient
        # monitor failure must not leave a VM permanently pending while the
        # response still claims the operation is retryable.
        retry_delay = _TARGET_RECOVERY_INITIAL_BACKOFF_SECONDS
        while not self._target_recovery_should_stop(stop_event, generation):
            with self._runtime_state_init_lock:
                if not self._is_target_recovery_generation_current(
                        generation, stop_event):
                    return
                pending_vms = sorted(self._target_recovery_pending_vms)
            if not pending_vms:
                return
            self._recover_pending_target_vms(
                pending_vms, stop_event, generation)
            with self._runtime_state_init_lock:
                if not self._is_target_recovery_generation_current(
                        generation, stop_event):
                    return
                still_pending = bool(self._target_recovery_pending_vms)
            if not still_pending:
                return
            if self._target_recovery_should_stop(stop_event, generation):
                return
            if self._wait_for_target_recovery_retry(
                    retry_delay, stop_event, generation):
                return
            retry_delay = min(
                retry_delay * 2,
                _TARGET_RECOVERY_MAX_BACKOFF_SECONDS)

    @staticmethod
    def _thread_is_alive(thread):
        if hasattr(thread, "is_alive"):
            return thread.is_alive()
        return thread.isAlive()

    def _join_target_recovery_thread(self, recovery_thread):
        if (not recovery_thread or
                recovery_thread is threading.current_thread() or
                not self._thread_is_alive(recovery_thread)):
            return
        recovery_thread.join(_TARGET_RECOVERY_STOP_JOIN_SECONDS)

    def _start_runtime_recovery(self):
        self._ensure_runtime_state()
        with self._runtime_state_init_lock:
            old_stop_event = self._target_recovery_stop_event
            old_recovery_thread = self._target_recovery_thread
        old_stop_event.set()
        self._join_target_recovery_thread(old_recovery_thread)

        stop_event = threading.Event()
        with self._runtime_state_init_lock:
            self._target_recovery_generation += 1
            generation = self._target_recovery_generation
            self._target_recovery_pending_vms = set()
            self._target_recovery_errors = {}
            self._target_recovery_discovery_complete = False
            self._target_recovery_discovery_error = None
            self._target_recovery_stop_event = stop_event
        recovery_thread = threading.Thread(
            target=lambda: self._run_mirror_target_recovery(
                stop_event, generation),
            name="zrm-target-node-recovery")
        recovery_thread.daemon = True
        with self._runtime_state_init_lock:
            self._target_recovery_thread = recovery_thread
        recovery_thread.start()

    def _linux_guest_fsfreeze(self, qga, action, timeout_seconds,
                              lease_timeout_seconds=None):
        """Linux path: freeze/thaw via QGA fsfreeze commands."""
        ok, reason = self._qga_supports_fsfreeze(qga)
        if not ok:
            return self._guest_fsfreeze_response(
                False, "error", 0, reason, guest_os_type="linux",
                quiesce_provider="none", error_code="QGA_COMMAND_IS_DISABLED")

        timeout_seconds = max(3, int(timeout_seconds or 30))
        lease_timeout_seconds = max(
            5, int(lease_timeout_seconds or _DEFAULT_FSFREEZE_LEASE_SECONDS))
        freeze_attempted = False
        freeze_lease_id = None
        try:
            if action == "freeze":
                status = qga.call_qga_command(
                    self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
                if status == "frozen":
                    fs_count = self._get_cached_linux_fsfreeze_count(qga)
                    freeze_attempted = True
                    freeze_lease_id = self._arm_fsfreeze_watchdog(
                        qga.vm_uuid, lease_timeout_seconds)
                    return self._guest_fsfreeze_response(
                        True, "frozen", fs_count, guest_os_type="linux",
                        quiesce_provider="qga-fsfreeze")

                # Persist restart recovery and arm the timer before issuing the
                # command that can freeze the guest.  A process exit after QGA
                # returns can therefore still be recovered on startup.
                freeze_lease_id = self._arm_fsfreeze_watchdog(
                    qga.vm_uuid, lease_timeout_seconds)
                freeze_attempted = True
                fs_count = qga.call_qga_command(
                    self._FSFREEZE_CMD_FREEZE, timeout=timeout_seconds)
                if not isinstance(fs_count, int):
                    fs_count = 0
                status = qga.call_qga_command(
                    self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
                if status != "frozen":
                    thawed, unused_status = self._best_effort_thaw_qga(qga, timeout_seconds)
                    if thawed:
                        self._clear_cached_linux_fsfreeze_count(qga)
                        self._cancel_fsfreeze_watchdog(
                            qga.vm_uuid, freeze_lease_id)
                    return self._guest_fsfreeze_response(
                        False, "error", fs_count,
                        "unexpected fsfreeze status after freeze: " + str(status),
                        guest_os_type="linux", quiesce_provider="qga-fsfreeze",
                        error_code="QGA_RETURN_VALUE_ERROR")
                self._set_cached_linux_fsfreeze_count(qga, fs_count)
                return self._guest_fsfreeze_response(
                    True, "frozen", fs_count, guest_os_type="linux",
                    quiesce_provider="qga-fsfreeze")

            if action == "thaw":
                status = qga.call_qga_command(
                    self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
                if status == "thawed":
                    self._clear_cached_linux_fsfreeze_count(qga)
                    self._cancel_fsfreeze_watchdog(qga.vm_uuid)
                    return self._guest_fsfreeze_response(
                        True, "thawed", 0, guest_os_type="linux",
                        quiesce_provider="qga-fsfreeze")
                fs_count = qga.call_qga_command(
                    self._FSFREEZE_CMD_THAW, timeout=timeout_seconds)
                if not isinstance(fs_count, int):
                    fs_count = 0
                status = qga.call_qga_command(
                    self._FSFREEZE_CMD_STATUS, timeout=timeout_seconds)
                if status != "thawed":
                    return self._guest_fsfreeze_response(
                        False, "error", fs_count,
                        "unexpected fsfreeze status after thaw: " + str(status),
                        guest_os_type="linux", quiesce_provider="qga-fsfreeze",
                        error_code="QGA_RETURN_VALUE_ERROR")
                self._clear_cached_linux_fsfreeze_count(qga)
                self._cancel_fsfreeze_watchdog(qga.vm_uuid)
                return self._guest_fsfreeze_response(
                    True, "thawed", fs_count, guest_os_type="linux",
                    quiesce_provider="qga-fsfreeze")

            return self._guest_fsfreeze_response(
                False, "error", 0, "unsupported action: " + str(action),
                guest_os_type="linux", quiesce_provider="qga-fsfreeze",
                error_code="QGA_COMMAND_ERROR")
        except Exception as ex:
            if action == "freeze" and freeze_attempted:
                thawed, unused_status = self._best_effort_thaw_qga(qga, timeout_seconds)
                if thawed:
                    self._clear_cached_linux_fsfreeze_count(qga)
                    if freeze_lease_id:
                        self._cancel_fsfreeze_watchdog(
                            qga.vm_uuid, freeze_lease_id)
                    else:
                        self._cancel_fsfreeze_watchdog(qga.vm_uuid)
                elif not freeze_lease_id:
                    try:
                        self._arm_fsfreeze_watchdog(qga.vm_uuid, lease_timeout_seconds)
                    except Exception as watchdog_ex:
                        logger.warn("ZRM failed to arm emergency fsfreeze watchdog for vm=%s: %s" %
                                    (qga.vm_uuid, watchdog_ex))
            logger.warn("ZRM guest-fsfreeze linux action=%s vm=%s failed: %s" %
                        (action, qga.vm_uuid, ex))
            return self._guest_fsfreeze_response(
                False, "error", 0, str(ex), guest_os_type="linux",
                quiesce_provider="qga-fsfreeze", error_code="QGA_COMMAND_EXEC_ERROR")

    def _windows_guest_fsfreeze(self, qga, action, timeout_seconds):
        """Windows path: GuestTools zs-tools VSS; degrades when zs-tools is not installed."""
        timeout_seconds = max(3, int(timeout_seconds or 30))
        if not qga.guest_file_is_exist(VmQga.ZS_TOOLS_PATN_WIN):
            return self._guest_fsfreeze_response(
                False, "error", 0, "zstack-guest-tools zs-tools.exe not installed",
                guest_os_type="windows", quiesce_provider="none",
                error_code="GUESTTOOLS_NOT_INSTALLED")
        operate = "freeze" if action == "freeze" else "thaw" if action == "thaw" else None
        if operate is None:
            return self._guest_fsfreeze_response(
                False, "error", 0, "unsupported action: " + str(action),
                guest_os_type="windows", quiesce_provider="guesttools-vss",
                error_code="QGA_COMMAND_ERROR")
        exit_code, output = qga.guest_exec_zs_tools(operate, "{}", output=True)
        if exit_code != 0:
            return self._guest_fsfreeze_response(
                False, "error", 0, output or ("zs-tools " + operate + " failed"),
                guest_os_type="windows", quiesce_provider="guesttools-vss",
                error_code="VSS_WRITER_FAILED")
        fs_status = "frozen" if operate == "freeze" else "thawed"
        return self._guest_fsfreeze_response(
            True, fs_status, 1, guest_os_type="windows",
            quiesce_provider="guesttools-vss")

    def _replication_guest_fsfreeze(self, req):
        """
        Guest quiesce endpoint invoked by ZRM createCheckpointInternal before checkpoint.

        Request: vmUuid, action (freeze|thaw), timeoutSeconds
        Response: success, fsFreezeStatus, filesystemCount, errorMessage, guestOsType, quiesceProvider, errorCode
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            action = (getattr(cmd, "action", None) or "").strip().lower()
            timeout_seconds = getattr(cmd, "timeoutSeconds", None)
            lease_timeout_seconds = getattr(cmd, "leaseTimeoutSeconds", None)
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            if action not in ("freeze", "thaw"):
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="action must be freeze or thaw"))

            with self._get_fsfreeze_vm_lock(vm_uuid):
                qga, qga_err = self._get_vm_qga(vm_uuid)
                if qga is None:
                    return self._guest_fsfreeze_response(
                        False, "error", 0, qga_err, guest_os_type="unknown",
                        quiesce_provider="none", error_code="QGA_NOT_RUNNING")

                guest_os = (qga.os or "").lower()
                if guest_os == VmQga.VM_OS_WINDOWS or "windows" in guest_os:
                    return self._windows_guest_fsfreeze(qga, action, timeout_seconds)
                return self._linux_guest_fsfreeze(
                    qga, action, timeout_seconds, lease_timeout_seconds)
        except Exception as e:
            logger.exception("ZRM guest-fsfreeze failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    def _replication_throttle(self, req):
        """
        Set mirror job speed for all zrm-mirror-* block jobs on the VM.

        Caller semantics (API layer, NOT QEMU semantics):
          - speed=0  → "quiesce": remove speed limit (QEMU speed=0 = unlimited)
                        so mirrors converge as fast as possible, then poll until
                        all jobs reach ready state or waitReadyTimeout expires.
          - speed>0  → set QEMU speed to that value (bytes/s throttle) and return.
          - speed=-1 → same as speed=0 (unlimited), but do NOT poll for ready.

        QEMU block-job-set-speed semantics:
          speed=0  → unlimited (no throttle, maximum rate)
          speed>0  → limit to N bytes/s

        Request body: vmUuid, speed, waitReadyTimeout (seconds, default 10).
        Response: allReady, readyCount, runningCount, totalJobs.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if not body:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="missing body"))
            cmd = jsonobject.loads(body)
            vm_uuid = (getattr(cmd, "vmUuid", None) or "").strip()
            if not vm_uuid:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="vmUuid required"))
            session_uuid = (getattr(cmd, "sessionUuid", None) or "").strip()

            speed = getattr(cmd, "speed", None)
            if speed is None:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="speed required"))
            speed = int(speed)
            wait_timeout = int(getattr(cmd, "waitReadyTimeout", None) or 10)

            # Map API speed to QEMU speed:
            #   API  0 (quiesce)   → QEMU 0 (unlimited, converge fastest)
            #   API -1 (unlimited) → QEMU 0 (unlimited)
            #   API >0 (throttle)  → QEMU N (that exact value)
            qemu_speed = 0 if speed <= 0 else speed

            all_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error))
            all_jobs = {device: job for device, job in all_jobs.items()
                        if self._job_matches_session(device, session_uuid)}
            # Filter out concluded/completed jobs -- QEMU rejects set-speed on them
            zrm_jobs = {d: j for d, j in all_jobs.items()
                        if (j.get("status") or "").lower() not in ("concluded", "null")}
            total_jobs = len(zrm_jobs)
            expected_job_ids = set(zrm_jobs.keys())

            # Set speed on active mirror jobs only
            speed_set_failures = []
            speed_set_devices = []
            for device in zrm_jobs:
                try:
                    qmp.block_job_set_speed(vm_uuid, device, qemu_speed)
                    speed_set_devices.append(device)
                except Exception as ex:
                    err = str(ex)
                    speed_set_failures.append({"device": device, "error": err})
                    logger.warn("ZRM throttle: set-speed failed for %s on vm %s: %s" % (device, vm_uuid, err))

            if speed_set_failures:
                rsp = ZrmAgentRsp(
                    success=False,
                    error="failed to set speed for ZRM mirror jobs: %s" % (
                        "; ".join(["%s: %s" % (f["device"], f["error"]) for f in speed_set_failures])),
                    speedSetFailed=True,
                    speedSetFailures=speed_set_failures,
                    speedSetDevices=speed_set_devices)
                rsp.readyCount = 0
                rsp.runningCount = total_jobs
                rsp.totalJobs = total_jobs
                return jsonobject.dumps(rsp)

            if total_jobs == 0:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="no active ZRM mirror jobs found for vm=%s" % vm_uuid,
                    allReady=False,
                    readyCount=0,
                    runningCount=0,
                    totalJobs=0))

            # When quiescing (speed==0), poll until all mirrors ready or timeout.
            # speed==-1 also sets QEMU unlimited but skips the wait.
            if speed == 0 and wait_timeout > 0:
                deadline = time.time() + wait_timeout
                while time.time() < deadline:
                    zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
                    if query_error:
                        return jsonobject.dumps(ZrmAgentRsp(
                            success=False,
                            error="query-block-jobs failed: %s" % query_error,
                            queryBlockJobsFailed=True,
                            queryBlockJobsError=query_error,
                            speedSetDevices=speed_set_devices,
                            totalJobs=total_jobs))
                    missing_jobs = sorted(expected_job_ids.difference(set(zrm_jobs.keys())))
                    terminal_jobs = []
                    ready_count = 0
                    running_count = 0
                    for device in expected_job_ids:
                        job = zrm_jobs.get(device)
                        if not job:
                            continue
                        status = (job.get("status") or "").lower()
                        if status in ("concluded", "null") or job.get("error"):
                            terminal_jobs.append({
                                "device": device,
                                "status": status or "unknown",
                                "error": str(job.get("error") or "")
                            })
                            continue
                        ready = job.get("ready") is True or status == "ready"
                        if ready:
                            ready_count += 1
                        elif status == "running":
                            running_count += 1
                    if missing_jobs or terminal_jobs:
                        return jsonobject.dumps(ZrmAgentRsp(
                            success=False,
                            error="mirror job set changed during convergence: missing=%s terminal=%s" %
                                  (missing_jobs, terminal_jobs),
                            allReady=False,
                            readyCount=ready_count,
                            runningCount=running_count,
                            totalJobs=total_jobs,
                            missingJobs=missing_jobs,
                            terminalJobs=terminal_jobs,
                            speedSetDevices=speed_set_devices))
                    if ready_count == total_jobs:
                        rsp = ZrmAgentRsp()
                        rsp.allReady = True
                        rsp.readyCount = ready_count
                        rsp.runningCount = running_count
                        rsp.totalJobs = total_jobs
                        logger.info("ZRM throttle: vm=%s all %d mirrors ready (quiesce)" % (vm_uuid, ready_count))
                        return jsonobject.dumps(rsp)
                    time.sleep(0.5)

            # Final state snapshot
            zrm_jobs, query_error = self._query_zrm_block_jobs(vm_uuid)
            if query_error:
                return jsonobject.dumps(ZrmAgentRsp(
                    success=False,
                    error="query-block-jobs failed: %s" % query_error,
                    queryBlockJobsFailed=True,
                    queryBlockJobsError=query_error,
                    speedSetDevices=speed_set_devices,
                    totalJobs=total_jobs))
            missing_jobs = sorted(expected_job_ids.difference(set(zrm_jobs.keys())))
            ready_count = 0
            running_count = 0
            for device in expected_job_ids:
                job = zrm_jobs.get(device)
                if not job:
                    continue
                status = (job.get("status") or "").lower()
                ready = job.get("ready") is True or status == "ready"
                if ready:
                    ready_count += 1
                elif status == "running":
                    running_count += 1

            rsp = ZrmAgentRsp()
            rsp.allReady = not missing_jobs and ready_count == total_jobs
            rsp.readyCount = ready_count
            rsp.runningCount = running_count
            rsp.totalJobs = total_jobs
            if missing_jobs:
                rsp.missingJobs = missing_jobs
            logger.info("ZRM throttle: vm=%s speed=%d qemu_speed=%d ready=%d running=%d total=%d allReady=%s" %
                        (vm_uuid, speed, qemu_speed, ready_count, running_count, total_jobs, rsp.allReady))
            return jsonobject.dumps(rsp)
        except Exception as e:
            logger.exception("ZRM replication throttle failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))
