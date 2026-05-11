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

import json
from kvmagent import kvmagent
from zstacklib.utils import http
from zstacklib.utils import jsonobject
from zstacklib.utils import log
from zstacklib.utils import qmp
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

# Default maximum timeout (seconds) for _wait_initial_full_sync when the
# caller does not specify one. Prevents async HTTP handler threads from
# blocking indefinitely.
_DEFAULT_MAX_WAIT_TIMEOUT = 3600


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


def execute_qmp_command_raw(domain_id, command, raise_exception=False):
    """
    Execute a raw QMP command represented as a full JSON *string*.

    This helper is needed when QMP arguments contain a ``name`` field (e.g.
    block-dirty-bitmap-add/query) which would clash with the ``name``
    positional parameter of :func:`qmp.execute_qmp_command`.  The public
    ``qmp.execute_qmp_command(domain, name, **kwargs)`` API has no way to
    pass ``arguments.name`` without this collision, so we fall back to the
    raw ``_execute_qmp_command`` that accepts a pre-serialised JSON string.

    Note: ``command`` must be a JSON *str* (not bytes).  On Python 2 str and
    bytes are equivalent; on Python 3 callers must pass ``str``.
    """
    if isinstance(command, bytes):
        command = command.decode("utf-8")
    return qmp._execute_qmp_command(domain_id, command, raise_exception=raise_exception)


class ZrmAgentRsp(object):
    """Lightweight response object aligned with Java KVMAgentCommands.AgentResponse."""
    def __init__(self, success=True, error=None, **kwargs):
        self.success = success
        self.error = error
        for k, v in (kwargs or {}).items():
            setattr(self, k, v)


class ZrmPlugin(kvmagent.KvmAgent):
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

    def start(self):
        http_server = kvmagent.get_http_server()
        # All ZRM paths are invoked via KVMHostAsyncHttpCallMsg and must be registered as async URIs.
        http_server.register_async_uri(self.PATH_REPLICATION_START, self.zrm_replication_start)
        http_server.register_async_uri(self.PATH_REPLICATION_STOP, self.zrm_replication_stop)
        http_server.register_async_uri(self.PATH_REPLICATION_PAUSE, self.zrm_replication_pause)
        http_server.register_async_uri(self.PATH_REPLICATION_RESUME, self.zrm_replication_resume)
        http_server.register_async_uri(self.PATH_REPLICATION_SYNC, self.zrm_replication_sync)
        http_server.register_async_uri(self.PATH_REPLICATION_WAIT_INITIAL, self.zrm_replication_wait_initial)
        http_server.register_async_uri(self.PATH_BITMAP_CREATE, self.zrm_bitmap_create)
        http_server.register_async_uri(self.PATH_CHECKPOINT_CREATE, self.zrm_checkpoint_create)
        http_server.register_async_uri(self.PATH_RECOVERY_PREPARE, self.zrm_recovery_prepare)
        http_server.register_async_uri(self.PATH_REPLICATION_THROTTLE, self.zrm_replication_throttle)
        logger.info("ZRM plugin started: registered /zrm/* paths as async URIs")

    def stop(self):
        pass

    def configure(self, config):
        self.config = config

    def _mock_ok(self, req):
        """
        Parse request body and return a success response.

        Used by pause/resume/checkpoint/recovery paths that are registered
        but not yet fully implemented.  A warning is logged so that stub
        invocations are visible in kvmagent logs.
        """
        try:
            body = req.get(http.REQUEST_BODY)
            if body:
                jsonobject.loads(body)
            logger.warn("ZRM stub endpoint called (not yet implemented): body_len=%s" %
                        (len(body) if body else 0))
        except Exception as e:
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))
        return jsonobject.dumps(ZrmAgentRsp())

    def _block_struct_contains_volume(self, obj, volume_uuid):
        """
        Recursively check whether any string value in a nested dict/list
        structure contains the given volume_uuid.

        This is used to match volume-related paths or image names in QMP
        responses.
        """
        if isinstance(obj, _str_types):
            return volume_uuid in obj
        if isinstance(obj, dict):
            for v in obj.values():
                if self._block_struct_contains_volume(v, volume_uuid):
                    return True
        elif isinstance(obj, list):
            for v in obj:
                if self._block_struct_contains_volume(v, volume_uuid):
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
                logger.debug("ZRM drive name from domain XML: volume=%s -> %s" % (vol_str[:8], drive_name))
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
        if not s.startswith("nbd://"):
            return None
        try:
            rest = s[6:]
            slash = rest.find("/")
            if slash >= 0:
                host_port, export = rest[:slash], rest[slash + 1:]
            else:
                host_port, export = rest, ""
            colon = host_port.rfind(":")
            if colon <= 0:
                return None
            host = host_port[:colon]
            port_str = host_port[colon + 1:]
            port = int(port_str)
            return (host, port, export or "")
        except (ValueError, AttributeError):
            return None

    def _try_blockdev_mirror_to_nbd(self, vm_uuid, node_name, nbd_url, job_id, sync_mode, bitmap_name):
        """
        Fallback path when all drive-mirror attempts fail: create an NBD client
        node via blockdev-add and then run blockdev-mirror to that node.

        This is mainly used for -blockdev setups where devices are only
        addressable by node-name and drive-mirror fails with root node errors.
        node_name is the source BDS node name (for example libvirt-2-format);
        sync_mode is either 'full' or 'incremental'; bitmap_name is required
        for incremental sync. Returns True on success, otherwise False.
        """
        parsed = self._parse_nbd_url(nbd_url)
        if not parsed or not node_name:
            return False
        host, port, export_name = parsed
        if not export_name:
            logger.warn("ZRM blockdev-mirror fallback: nbd export name empty")
            return False
        # Derive target node name from job_id; delete any stale node before re-adding.
        job_suffix = job_id.replace("zrm-mirror-", "") if job_id else ""
        if not job_suffix:
            logger.warn("ZRM blockdev-mirror fallback: empty job_id suffix, skipping")
            return False
        tgt_node = "zrm-tgt-%s" % job_suffix
        try:
            # Best-effort removal of any previous node with the same name to avoid duplicate nodes.
            blockdev_del = {"execute": "blockdev-del", "arguments": {"node-name": tgt_node}}
            execute_qmp_command_raw(vm_uuid, json.dumps(blockdev_del), raise_exception=False)
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
            execute_qmp_command_raw(vm_uuid, json.dumps(blockdev_add), raise_exception=True)
            # blockdev-mirror: device is the source node-name, target is the NBD node just added.
            mirror_args = {
                "device": node_name,
                "target": tgt_node,
                "sync": sync_mode,
                "job-id": job_id or tgt_node,
                "auto-finalize": False,
                "auto-dismiss": False
            }
            if bitmap_name and sync_mode == "incremental":
                mirror_args["bitmap"] = bitmap_name
            qmp.execute_qmp_command(vm_uuid, "blockdev-mirror", raise_exception=True, **mirror_args)
            logger.info("ZRM replication start: blockdev-mirror fallback ok for node=%s -> %s (target=%s)" % (node_name, nbd_url, tgt_node))
            return True
        except Exception as e:
            logger.warn("ZRM blockdev-mirror fallback failed: %s" % e)
            return False

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
        vol_str = volume_uuid if isinstance(volume_uuid, str) else str(volume_uuid)
        try:
            blocks = qmp.execute_qmp_command(domain_uuid, "query-block", raise_exception=False)
        except Exception as e:
            logger.warn("ZRM query-block failed for vm[uuid:%s]: %s" % (domain_uuid, e))
            return None, None
        if not blocks:
            return None, None
        if isinstance(blocks, dict):
            blocks = list(blocks.values())
        for b in (blocks or []):
            if not isinstance(b, dict) or not self._block_struct_contains_volume(b, vol_str):
                continue
            device = b.get("device") or ""
            if not (isinstance(device, _str_types) and device.strip()):
                device = None
            qdev = b.get("qdev") or b.get("Qdev") or ""
            if not isinstance(qdev, _str_types):
                qdev = str(qdev) if qdev else ""
            if (not device or not device.strip()) and qdev.strip():
                parts = qdev.strip().rstrip("/").split("/")
                for p in reversed(parts):
                    if p and p not in ("virtio-backend", "machine", "peripheral", "scsi-backend"):
                        device = p
                        break
            node_name = None
            inserted = b.get("inserted") or {}
            if isinstance(inserted, dict):
                node_name = inserted.get("node-name")
            if device or node_name:
                return device or node_name, node_name or device
        return None, None

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

    def _find_block_entry_for_volume(self, blocks_list, volume_uuid):
        """
        Find the query-block entry that contains the given volumeUuid from a
        pre-fetched blocks_list and return (device, node_name).

        The traversal logic mirrors _get_block_device_for_volume_uuid but
        does not issue a new QMP command. Returns (None, None) when not
        found or when blocks_list is None.
        """
        if not blocks_list or not volume_uuid:
            return None, None
        vol_str = volume_uuid if isinstance(volume_uuid, str) else str(volume_uuid)
        for b in blocks_list:
            if not self._block_struct_contains_volume(b, vol_str):
                continue
            device = b.get("device") or ""
            if not isinstance(device, _str_types) or not device.strip():
                device = None
            qdev = b.get("qdev") or b.get("Qdev") or ""
            if not isinstance(qdev, _str_types):
                qdev = str(qdev) if qdev else ""
            if (not device or not device.strip()) and qdev.strip():
                parts = qdev.strip().rstrip("/").split("/")
                for p in reversed(parts):
                    if p and p not in ("virtio-backend", "machine", "peripheral", "scsi-backend"):
                        device = p
                        break
            node_name = None
            inserted = b.get("inserted") or {}
            if isinstance(inserted, dict):
                node_name = inserted.get("node-name")
            if device or node_name:
                return device or node_name, node_name or device
        return None, None

    def _diagnose_block_topology(self, vm_uuid, volume_uuid, node_name_used):
        """
        Diagnose libvirt/QEMU block topology for a given volume and node name.

        Uses query-block plus x-debug-query-block-graph to determine whether
        node_name_used is a root block node; if not, walks the graph to find
        the root node name for drive-mirror. Returns (suggested_root_node_name
        or None, summary_string).
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

        # 2) x-debug-query-block-graph: check whether node_name_used is root and compute the chain root.
        suggested_root = None
        try:
            graph = qmp.execute_qmp_command(vm_uuid, "x-debug-query-block-graph", raise_exception=False)
        except Exception as e:
            summary_parts.append("x-debug-query-block-graph not available: %s" % e)
            return None, "; ".join(summary_parts)
        if not graph or not isinstance(graph, dict):
            summary_parts.append("x-debug-query-block-graph empty or not dict")
            return None, "; ".join(summary_parts)
        # QMP returns the graph object directly: { "nodes": [...], "edges": [...] }.
        nodes_list = graph.get("nodes")
        edges_list = graph.get("edges")
        if not nodes_list or not edges_list:
            summary_parts.append("block-graph: nodes or edges missing")
            return None, "; ".join(summary_parts)
        id_to_node = {}
        for n in (nodes_list or []):
            if isinstance(n, dict) and "id" in n:
                id_to_node[n["id"]] = n
        # Edges are (parent, child): a child may have multiple parents (e.g. quorum).
        child_to_parent_ids = {}
        for e in (edges_list or []):
            if isinstance(e, dict) and "child" in e and "parent" in e:
                child_to_parent_ids.setdefault(e["child"], []).append(e["parent"])

        node_id_used = None
        for n in (nodes_list or []):
            if not isinstance(n, dict):
                continue
            if n.get("name") == node_name_used and n.get("type") == "block-driver":
                node_id_used = n.get("id")
                break
        if node_id_used is None:
            summary_parts.append("block-graph: node '%s' not found (type=block-driver)" % (node_name_used or ""))
            return None, "; ".join(summary_parts)

        # Walk parents from the current node until its parent is a block-backend; that BDS is the root.
        current_id = node_id_used
        seen = set()
        while current_id is not None and current_id not in seen:
            seen.add(current_id)
            parent_ids = child_to_parent_ids.get(current_id) or []
            if not parent_ids:
                summary_parts.append("block-graph: node '%s' has no parent edge" % node_name_used)
                break
            # Try each parent; prefer block-backend, then block-driver.
            advanced = False
            for parent_id in parent_ids:
                parent_node = id_to_node.get(parent_id)
                if not parent_node:
                    continue
                ptype = parent_node.get("type") or ""
                if ptype == "block-backend":
                    current_node = id_to_node.get(current_id)
                    root_name = (current_node or {}).get("name") if isinstance(current_node, dict) else None
                    if current_id == node_id_used:
                        summary_parts.append("block-graph: node '%s' is ROOT (parent is block-backend)" % node_name_used)
                    else:
                        summary_parts.append("block-graph: node '%s' is NOT root; root of chain is '%s'" %
                                             (node_name_used, root_name))
                        suggested_root = root_name
                    current_id = None  # signal loop exit
                    advanced = True
                    break
                if ptype == "block-driver":
                    current_id = parent_id
                    advanced = True
                    break
            if not advanced:
                # None of the parents were block-backend or block-driver; follow the first one anyway.
                current_id = parent_ids[0]
        else:
            if current_id in seen and len(seen) > 1:
                summary_parts.append("block-graph: cycle or non-backend root for node '%s'" % node_name_used)

        return suggested_root, "; ".join(summary_parts)

    def _zrm_bitmap_name(self, volume_uuid):
        """Return the fixed per-volume bitmap name for ZRM, distinct from CDP's zsbm- prefix."""
        return ZRM_BITMAP_PREFIX + (volume_uuid or "")[:16]

    def _has_dirty_bitmap(self, domain_uuid, node_name, bitmap_name):
        """Return True if a dirty bitmap exists on the given node, otherwise False."""
        if not node_name or not bitmap_name:
            return False
        try:
            # Use a full arguments dict to avoid name collisions with qmp.execute_qmp_command's name parameter.
            qmp_cmd = {"execute": "block-dirty-bitmap-query", "arguments": {"node": node_name, "name": bitmap_name}}
            execute_qmp_command_raw(domain_uuid, json.dumps(qmp_cmd), raise_exception=True)
            return True
        except Exception:
            return False

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
        try:
            by_dev = qmp.query_block_jobs_by_device(vm_uuid)
        except Exception as e:
            logger.debug("ZRM query-block-jobs failed for vm %s: %s" % (vm_uuid, e))
            return {}
        if not by_dev:
            return {}
        return {k: v for k, v in by_dev.items() if k and (k.startswith("zrm-mirror-"))}

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
        (job.ready is True or status == "ready"). Returns None on success,
        or an error string on timeout or when jobs are missing.
        """
        if isinstance(volume_uuids, (str, bytes)):
            volume_uuids = [volume_uuids] if volume_uuids else []
        vols = [v.strip() for v in (volume_uuids or []) if (v or "").strip()]
        if not vols:
            return "no volumeUuids specified for initial full sync wait"
        job_ids = ["zrm-mirror-%s" % v[:8] for v in vols]
        # Enforce a deadline to prevent indefinite thread blocking.
        effective_timeout = timeout_seconds if (timeout_seconds and timeout_seconds > 0) else _DEFAULT_MAX_WAIT_TIMEOUT
        deadline = time.time() + effective_timeout
        last_log_ts = 0.0
        while True:
            jobs = self._get_zrm_block_jobs(vm_uuid)
            not_ready = []
            missing = []
            for job_id in job_ids:
                job = jobs.get(job_id)
                if not job:
                    missing.append(job_id)
                    continue
                status = (job.get("status") or "").lower()
                ready = job.get("ready") is True or status == "ready"
                if not ready:
                    not_ready.append(job_id)
            now = time.time()
            if not not_ready and not missing:
                logger.info("ZRM initial full sync wait: all jobs ready for vm=%s volumes=%s" %
                            (vm_uuid, ",".join([v[:8] for v in vols])))
                return None
            if now >= deadline:
                err = "initial full sync timeout for vm=%s, not_ready=%s, missing=%s" % (
                    vm_uuid, ",".join(not_ready), ",".join(missing))
                logger.warn("ZRM initial full sync wait: %s" % err)
                return err
            if now - last_log_ts >= 30.0:
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

    def _start_mirrors_for_zr(self, vm_uuid, volume_uuids, target_nbd_base_url, sync_mode_hint=None):
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
        base = (target_nbd_base_url or "").rstrip("/")
        if not base.startswith("nbd://"):
            return "targetNbdUrl must be nbd://host:port"
        # Reuse a single query-block result for all volumes to keep API latency low.
        blocks_cache = self._query_blocks_for_vm(vm_uuid)
        # Pre-query all ZR jobs on this VM for use by the per-volume state machine.
        zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
        first_error = None
        for vol_uuid in volume_uuids:
            vol_uuid = (vol_uuid or "").strip()
            if not vol_uuid:
                continue
            # ZR state machine: complete ready jobs, reuse running ones.
            job_id = "zrm-mirror-%s" % vol_uuid[:8]
            existing = zrm_jobs.get(job_id)
            if existing:
                status = (existing.get("status") or "").lower()
                ready = existing.get("ready") is True or status == "ready"
                paused = existing.get("paused") is True
                err_text = existing.get("error")
                reusable_running = ((status == "running") and (not paused) and (not err_text)) or (ready and (not err_text) and status != "concluded")
                if reusable_running:
                    logger.info("ZRM replication start: volume %s already has running mirror job %s, reuse" % (vol_uuid[:8], job_id))
                    continue
                else:
                    if status == "concluded":
                        qmp.execute_qmp_command(vm_uuid, "block-job-dismiss", raise_exception=False, id=job_id)
                    else:
                        qmp.block_job_cancel(vm_uuid, job_id)
                    logger.info("ZRM replication start: cleared stale mirror job %s for volume %s (status=%s paused=%s error=%s)" %
                                (job_id, vol_uuid[:8], status, paused, err_text if err_text else ""))
            nbd_url = "%s/vol-%s" % (base, vol_uuid)
            # Resolve device/node_name — _get_block_device_for_volume_uuid already
            # delegates to vm_plugin.get_mirror_device_for_volume_uuid internally.
            device, node_name = self._find_block_entry_for_volume(blocks_cache, vol_uuid) if blocks_cache else (None, None)
            if not device and not node_name:
                device, node_name = self._get_block_device_for_volume_uuid(vm_uuid, vol_uuid)
            if not device and not node_name:
                err = "no block device found for volume %s on vm %s (query-block)" % (vol_uuid, vm_uuid)
                logger.warn("ZRM replication start: %s" % err)
                if first_error is None:
                    first_error = err
                continue
            mirror_candidates = self._build_mirror_candidates(vm_uuid, vol_uuid, device, node_name, blocks_cache)
            bitmap_node = node_name or device
            logger.debug("ZRM replication volume=%s mirror_candidates=%s bitmap_node=%s" %
                         (vol_uuid[:8], mirror_candidates, bitmap_node))
            bitmap_name = self._zrm_bitmap_name(vol_uuid)
            has_bitmap = self._has_dirty_bitmap(vm_uuid, bitmap_node, bitmap_name)
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
                    err = "syncMode=INCREMENTAL but no dirty bitmap found for volume %s — bitmap must exist before incremental sync" % vol_uuid
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
            last_err = None
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
                suggested_root, topo_summary = self._diagnose_block_topology(vm_uuid, vol_uuid, primary_node or node_name)
                logger.warn("ZRM replication topology diagnosis volume=%s: %s" % (vol_uuid[:8], topo_summary))
                if suggested_root and suggested_root not in mirror_candidates:
                    try:
                        mirror_kw = dict(device=suggested_root, **base_mirror_kw)
                        qmp.execute_qmp_command(vm_uuid, "drive-mirror", raise_exception=True, **mirror_kw)
                        logger.info("ZRM replication start: drive-mirror ok with topology-suggested device=%s" % suggested_root)
                        last_err = None
                    except Exception as e:
                        logger.debug("ZRM drive-mirror device=%s (from topology) failed: %s" % (suggested_root, e))
            if last_err is not None and node_name:
                if self._try_blockdev_mirror_to_nbd(vm_uuid, node_name, nbd_url, job_id, sync_mode, bitmap_name):
                    last_err = None
            if last_err is not None:
                err = "drive-mirror failed for volume %s: %s" % (vol_uuid, last_err)
                logger.warn("ZRM replication start: %s" % err)
                if first_error is None:
                    first_error = err
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
            err = self._start_mirrors_for_zr(vm_uuid, volume_uuids, target_nbd_url, sync_mode_hint)
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
            zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
            for device in zrm_jobs:
                qmp.block_job_cancel(vm_uuid, device)
                logger.info("ZRM replication stop: cancelled job %s on vm %s" % (device, vm_uuid))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication stop failed")
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
            zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
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
                    # A concluded mirror job means the job has finished — possibly
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
            err = self._wait_initial_full_sync(vm_uuid, vol_uuids,
                                               int(timeout_seconds) if timeout_seconds else 0)
            if err:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error=err))
            return jsonobject.dumps(ZrmAgentRsp())
        except Exception as e:
            logger.exception("ZRM replication wait-initial failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))

    @kvmagent.replyerror
    def zrm_replication_stop(self, req):
        return self._replication_stop(req)

    @kvmagent.replyerror
    def zrm_replication_pause(self, req):
        return self._mock_ok(req)

    @kvmagent.replyerror
    def zrm_replication_resume(self, req):
        return self._mock_ok(req)

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
                if self._has_dirty_bitmap(vm_uuid, node_name, name):
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
        return self._mock_ok(req)

    @kvmagent.replyerror
    def zrm_recovery_prepare(self, req):
        return self._mock_ok(req)

    @kvmagent.replyerror
    def zrm_replication_throttle(self, req):
        return self._replication_throttle(req)

    def _replication_throttle(self, req):
        """
        Set mirror job speed for all zrm-mirror-* block jobs on the VM.

        When speed=0, poll until all mirrors reach ready state or timeout.
        When speed>0 (or speed=-1 for unlimited), set speed and return immediately.

        Request body: vmUuid, speed (bytes/s, 0=pause, -1=unlimited),
                      waitReadyTimeout (seconds, default 10).
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

            speed = getattr(cmd, "speed", None)
            if speed is None:
                return jsonobject.dumps(ZrmAgentRsp(success=False, error="speed required"))
            speed = int(speed)
            wait_timeout = int(getattr(cmd, "waitReadyTimeout", None) or 10)

            # QEMU block-job-set-speed: speed=0 means unlimited (no throttle)
            # We use speed=1 (1 byte/s ~ paused) to throttle, speed=0 to restore unlimited
            qemu_speed = 1 if speed == 0 else 0 if speed < 0 else speed

            all_jobs = self._get_zrm_block_jobs(vm_uuid)
            # Filter out concluded/completed jobs — QEMU rejects set-speed on them
            zrm_jobs = {d: j for d, j in all_jobs.items()
                        if (j.get("status") or "").lower() not in ("concluded", "null")}
            total_jobs = len(zrm_jobs)

            # Set speed on active mirror jobs only
            for device in zrm_jobs:
                try:
                    qmp.block_job_set_speed(vm_uuid, device, qemu_speed)
                except Exception as ex:
                    logger.warn("ZRM throttle: set-speed failed for %s on vm %s: %s" % (device, vm_uuid, ex))

            if total_jobs == 0:
                rsp = ZrmAgentRsp()
                rsp.allReady = True
                rsp.readyCount = 0
                rsp.runningCount = 0
                rsp.totalJobs = 0
                return jsonobject.dumps(rsp)

            # If throttling (speed==0), poll until all ready or timeout
            if speed == 0 and wait_timeout > 0:
                deadline = time.time() + wait_timeout
                while time.time() < deadline:
                    zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
                    ready_count = 0
                    running_count = 0
                    for device, job in zrm_jobs.items():
                        status = (job.get("status") or "").lower()
                        ready = job.get("ready") is True or status == "ready"
                        if ready:
                            ready_count += 1
                        elif status == "running":
                            running_count += 1
                    if ready_count >= len(zrm_jobs):
                        rsp = ZrmAgentRsp()
                        rsp.allReady = True
                        rsp.readyCount = ready_count
                        rsp.runningCount = running_count
                        rsp.totalJobs = len(zrm_jobs)
                        logger.info("ZRM throttle: vm=%s all %d mirrors ready" % (vm_uuid, ready_count))
                        return jsonobject.dumps(rsp)
                    time.sleep(0.5)

            # Final state snapshot
            zrm_jobs = self._get_zrm_block_jobs(vm_uuid)
            ready_count = 0
            running_count = 0
            for device, job in zrm_jobs.items():
                status = (job.get("status") or "").lower()
                ready = job.get("ready") is True or status == "ready"
                if ready:
                    ready_count += 1
                elif status == "running":
                    running_count += 1

            rsp = ZrmAgentRsp()
            rsp.allReady = ready_count >= len(zrm_jobs) and len(zrm_jobs) > 0
            rsp.readyCount = ready_count
            rsp.runningCount = running_count
            rsp.totalJobs = len(zrm_jobs)
            logger.info("ZRM throttle: vm=%s speed=%d ready=%d running=%d total=%d allReady=%s" %
                        (vm_uuid, speed, ready_count, running_count, len(zrm_jobs), rsp.allReady))
            return jsonobject.dumps(rsp)
        except Exception as e:
            logger.exception("ZRM replication throttle failed")
            return jsonobject.dumps(ZrmAgentRsp(success=False, error=str(e)))
