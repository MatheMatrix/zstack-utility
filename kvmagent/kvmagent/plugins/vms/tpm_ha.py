"""
TPM HA State Sync — piggyback TPM state onto storage fencer heartbeat path.

Design:
    - Each storage fencer already writes heartbeat to shared/distributed storage
    - This module syncs swtpm state files alongside heartbeat data
    - TPM state follows the same network path as VM data (storage network)
    - No dependency on management network for HA protection

Coupling notes (TODO for future refactor):
    - Currently called directly from ha_plugin fencer loops
    - Ideally should be an event/hook system: fencer emits "heartbeat_written"
      event, tpm_ha subscribes. This avoids ha_plugin importing vms.tpm_ha.
    - The sync is best-effort: failure to sync TPM state must NOT block or
      fail the fencer heartbeat. VM availability > TPM state availability.

Storage backend support:
    - FileSystem (NFS/GlusterFS/CephFS): write state files to shared mount
    - Ceph RBD pool: write state as rados objects
    - SharedBlock (LVM/SAN): write state to a dedicated LV (TODO: phase 2)
    - iSCSI / CBD: not supported in this draft
"""

import os
import time
import json
import shutil
import tarfile
import tempfile
import threading

from zstacklib.utils import log
from zstacklib.utils import bash
from zstacklib.utils import linux

logger = log.get_logger(__name__)

SWTPM_STATE_DIR = "/var/lib/libvirt/swtpm"
TPM_SYNC_DIR_NAME = "zs-tpm-states"
TPM_SYNC_METADATA_FILE = "tpm-sync-meta.json"

# max allowed state size per VM (swtpm state is typically < 1MB)
MAX_TPM_STATE_SIZE = 16 * 1024 * 1024  # 16MB

# minimum interval between syncs for the same VM (seconds)
MIN_SYNC_INTERVAL = 30

# track last sync time per VM to avoid redundant writes
_last_sync_times = {}  # type: dict[str, float]
_sync_lock = threading.Lock()


def find_tpm_enabled_vms():
    # type: () -> list[str]
    """Find VM UUIDs that have swtpm state directories on this host."""
    if not os.path.isdir(SWTPM_STATE_DIR):
        return []

    vm_uuids = []
    for entry in os.listdir(SWTPM_STATE_DIR):
        entry_path = os.path.join(SWTPM_STATE_DIR, entry)
        if os.path.isdir(entry_path) and _is_uuid_format(entry):
            vm_uuids.append(entry)
    return vm_uuids


def _is_uuid_format(s):
    # type: (str) -> bool
    parts = s.split('-')
    if len(parts) != 5:
        return False
    expected_lens = [8, 4, 4, 4, 12]
    for part, expected_len in zip(parts, expected_lens):
        if len(part) != expected_len:
            return False
        try:
            int(part, 16)
        except ValueError:
            return False
    return True


def _should_sync(vm_uuid):
    # type: (str) -> bool
    """Check if enough time has passed since last sync for this VM."""
    now = time.time()
    last = _last_sync_times.get(vm_uuid, 0)
    return (now - last) >= MIN_SYNC_INTERVAL


def _mark_synced(vm_uuid):
    # type: (str) -> None
    with _sync_lock:
        _last_sync_times[vm_uuid] = time.time()


def _get_tpm_state_tarball(vm_uuid):
    # type: (str) -> str | None
    """Create a tarball of the VM's swtpm state dir, return path to temp file.

    Returns None if state dir doesn't exist or is empty.
    Caller is responsible for cleaning up the temp file.
    """
    state_dir = os.path.join(SWTPM_STATE_DIR, vm_uuid)
    if not os.path.isdir(state_dir):
        return None

    if not os.listdir(state_dir):
        return None

    tmp_dir = tempfile.mkdtemp(prefix="tpm_ha_sync_")
    tar_path = os.path.join(tmp_dir, "%s.tar.gz" % vm_uuid)

    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(state_dir, arcname=vm_uuid)

        file_size = os.path.getsize(tar_path)
        if file_size > MAX_TPM_STATE_SIZE:
            logger.warn("TPM state tarball for VM %s is %d bytes, exceeds limit" % (vm_uuid, file_size))
            shutil.rmtree(tmp_dir)
            return None

        return tar_path
    except Exception as e:
        logger.warn("failed to create TPM state tarball for VM %s: %s" % (vm_uuid, e))
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        return None


def _restore_tpm_state_from_tarball(tar_path, vm_uuid):
    # type: (str, str) -> bool
    """Restore a VM's swtpm state from a tarball."""
    target_dir = os.path.join(SWTPM_STATE_DIR, vm_uuid)

    try:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        extract_dir = tempfile.mkdtemp(prefix="tpm_ha_restore_")
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                for member in tar.getmembers():
                    normalized = os.path.normpath(member.name)
                    if os.path.isabs(member.name) or normalized.startswith('..'):
                        raise ValueError("unsafe tar entry: %s" % member.name)
                    if member.issym() or member.islnk():
                        raise ValueError("symlinks not allowed: %s" % member.name)
                tar.extractall(extract_dir)

            extracted = os.path.join(extract_dir, vm_uuid)
            if os.path.isdir(extracted):
                shutil.move(extracted, target_dir)
            else:
                logger.warn("tarball for VM %s doesn't contain expected directory" % vm_uuid)
                return False
        finally:
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)

        logger.info("restored TPM state for VM %s from storage" % vm_uuid)
        return True
    except Exception as e:
        logger.warn("failed to restore TPM state for VM %s: %s" % (vm_uuid, e))
        return False


# ============================================================
#  FileSystem backend (NFS / GlusterFS / CephFS shared mount)
# ============================================================

def sync_tpm_states_to_filesystem(mount_path, host_uuid):
    # type: (str, str) -> None
    """Sync all local TPM states to shared filesystem.

    Called from FileSystemHeartbeatController's heartbeat loop.
    Best-effort: exceptions are caught and logged, never propagated.
    """
    try:
        _do_sync_tpm_to_filesystem(mount_path, host_uuid)
    except Exception as e:
        logger.warn("TPM state filesystem sync failed: %s" % e)


def _do_sync_tpm_to_filesystem(mount_path, host_uuid):
    # type: (str, str) -> None
    tpm_sync_dir = os.path.join(mount_path, TPM_SYNC_DIR_NAME)
    if not os.path.exists(tpm_sync_dir):
        try:
            os.makedirs(tpm_sync_dir, 0o755)
        except OSError:
            if not os.path.exists(tpm_sync_dir):
                raise

    tpm_vms = find_tpm_enabled_vms()
    if not tpm_vms:
        return

    for vm_uuid in tpm_vms:
        if not _should_sync(vm_uuid):
            continue

        state_dir = os.path.join(SWTPM_STATE_DIR, vm_uuid)
        target_dir = os.path.join(tpm_sync_dir, vm_uuid)

        try:
            # use atomic replace: write to temp dir, then rename
            tmp_target = target_dir + ".tmp.%s" % host_uuid
            if os.path.exists(tmp_target):
                shutil.rmtree(tmp_target)

            shutil.copytree(state_dir, tmp_target)

            # write metadata
            meta = {
                "host_uuid": host_uuid,
                "vm_uuid": vm_uuid,
                "sync_time": time.time(),
                "sync_time_readable": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            meta_path = os.path.join(tmp_target, TPM_SYNC_METADATA_FILE)
            with open(meta_path, 'w') as f:
                json.dump(meta, f)

            # atomic replace
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            os.rename(tmp_target, target_dir)

            _mark_synced(vm_uuid)
            logger.debug("synced TPM state for VM %s to filesystem" % vm_uuid)
        except Exception as e:
            logger.warn("failed to sync TPM state for VM %s to filesystem: %s" % (vm_uuid, e))
            if os.path.exists(tmp_target):
                try:
                    shutil.rmtree(tmp_target)
                except Exception:
                    pass


def restore_tpm_state_from_filesystem(mount_path, vm_uuid):
    # type: (str, str) -> bool
    """Restore a VM's TPM state from shared filesystem before VM starts.

    Returns True if state was restored, False if no state found or error.
    """
    tpm_sync_dir = os.path.join(mount_path, TPM_SYNC_DIR_NAME)
    source_dir = os.path.join(tpm_sync_dir, vm_uuid)

    if not os.path.isdir(source_dir):
        logger.debug("no TPM state backup found for VM %s on filesystem" % vm_uuid)
        return False

    target_dir = os.path.join(SWTPM_STATE_DIR, vm_uuid)

    try:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        shutil.copytree(source_dir, target_dir)

        # remove sync metadata from local copy
        meta_path = os.path.join(target_dir, TPM_SYNC_METADATA_FILE)
        if os.path.exists(meta_path):
            os.remove(meta_path)

        logger.info("restored TPM state for VM %s from filesystem" % vm_uuid)
        return True
    except Exception as e:
        logger.warn("failed to restore TPM state for VM %s: %s" % (vm_uuid, e))
        return False


# ============================================================
#  Ceph backend (rados objects in the heartbeat pool)
# ============================================================

def sync_tpm_states_to_ceph(ioctx, host_uuid, pool_name, write_timeout=5):
    # type: (object, str, str, int) -> None
    """Sync all local TPM states to Ceph pool as rados objects.

    Called from CephHeartbeatController's heartbeat loop.
    Best-effort: exceptions are caught and logged, never propagated.

    Object naming: tpm-state-{vm_uuid}
    """
    try:
        _do_sync_tpm_to_ceph(ioctx, host_uuid, pool_name, write_timeout)
    except Exception as e:
        logger.warn("TPM state ceph sync failed: %s" % e)


def _do_sync_tpm_to_ceph(ioctx, host_uuid, pool_name, write_timeout):
    # type: (object, str, str, int) -> None
    tpm_vms = find_tpm_enabled_vms()
    if not tpm_vms:
        return

    for vm_uuid in tpm_vms:
        if not _should_sync(vm_uuid):
            continue

        tar_path = _get_tpm_state_tarball(vm_uuid)
        if not tar_path:
            continue

        try:
            with open(tar_path, 'rb') as f:
                data = f.read()

            object_name = "tpm-state-%s" % vm_uuid

            # write tarball as rados object
            completion = ioctx.aio_write_full(object_name, data)
            waited = 0
            while not completion.is_complete():
                time.sleep(1)
                waited += 1
                if waited >= write_timeout:
                    logger.warn("TPM state ceph write for VM %s timed out" % vm_uuid)
                    break

            if completion.is_complete():
                # write metadata object
                meta = {
                    "host_uuid": host_uuid,
                    "vm_uuid": vm_uuid,
                    "pool_name": pool_name,
                    "data_size": len(data),
                    "sync_time": time.time(),
                    "sync_time_readable": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                meta_obj_name = "tpm-state-%s-meta" % vm_uuid
                ioctx.write_full(meta_obj_name, json.dumps(meta).encode('utf-8'))

                _mark_synced(vm_uuid)
                logger.debug("synced TPM state for VM %s to ceph pool %s (%d bytes)"
                             % (vm_uuid, pool_name, len(data)))

            del completion
        except Exception as e:
            logger.warn("failed to sync TPM state for VM %s to ceph: %s" % (vm_uuid, e))
        finally:
            tmp_dir = os.path.dirname(tar_path)
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)


def restore_tpm_state_from_ceph(ioctx, vm_uuid, read_timeout=10):
    # type: (object, str, int) -> bool
    """Restore a VM's TPM state from Ceph pool before VM starts.

    Returns True if state was restored, False if no state found or error.
    """
    import rados as _rados

    object_name = "tpm-state-%s" % vm_uuid

    try:
        stat = ioctx.stat(object_name)
        obj_size = stat[0]
    except _rados.ObjectNotFound:
        logger.debug("no TPM state backup found for VM %s in ceph" % vm_uuid)
        return False
    except Exception as e:
        logger.warn("failed to stat TPM state object for VM %s: %s" % (vm_uuid, e))
        return False

    try:
        data = ioctx.read(object_name, obj_size)

        tmp_dir = tempfile.mkdtemp(prefix="tpm_ha_ceph_restore_")
        tar_path = os.path.join(tmp_dir, "%s.tar.gz" % vm_uuid)

        try:
            with open(tar_path, 'wb') as f:
                f.write(data)

            return _restore_tpm_state_from_tarball(tar_path, vm_uuid)
        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)

    except Exception as e:
        logger.warn("failed to restore TPM state for VM %s from ceph: %s" % (vm_uuid, e))
        return False


def cleanup_tpm_state_on_storage(mount_path=None, ioctx=None, vm_uuid=None):
    # type: (str | None, object | None, str) -> None
    """Remove TPM state backup from storage when VM is deleted.

    Call from VM destroy/delete flow.
    """
    if mount_path:
        target = os.path.join(mount_path, TPM_SYNC_DIR_NAME, vm_uuid)
        if os.path.exists(target):
            try:
                shutil.rmtree(target)
                logger.info("cleaned up TPM state for VM %s on filesystem" % vm_uuid)
            except Exception as e:
                logger.warn("failed to cleanup TPM state for VM %s: %s" % (vm_uuid, e))

    if ioctx:
        for obj_name in ["tpm-state-%s" % vm_uuid, "tpm-state-%s-meta" % vm_uuid]:
            try:
                ioctx.remove_object(obj_name)
                logger.info("cleaned up TPM state object %s" % obj_name)
            except Exception:
                pass
