import json
import logging
import os
import re
import threading

from zstacklib.utils.vm_metadata_handler import VmMetadataHandler, VmMetadataScanEntry

logger = logging.getLogger(__name__)

# MN uses FILE_METADATA_SUFFIX = ".vmmeta"
# agent detects metadata files by this suffix; all paths are MN-issued
_METADATA_SUFFIX = '.vmmeta'
_UUID_HEX_RE = re.compile(r'^[0-9a-f]{32}$')


def _fsync_directory(file_path):
    """fsync the parent directory to ensure rename/unlink is durable."""
    dir_fd = os.open(os.path.dirname(file_path), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _ensure_bytes(data):
    """Encode unicode to UTF-8 bytes; pass through if already bytes."""
    if isinstance(data, bytes):
        return data
    return data.encode('utf-8')


class FileBasedMetadataHandler(VmMetadataHandler):
    def __init__(self):
        super(FileBasedMetadataHandler, self).__init__()
        self._lock_map = {}
        self._lock_map_lock = threading.Lock()

    def _get_path_lock(self, metadataPath):
        with self._lock_map_lock:
            if metadataPath not in self._lock_map:
                self._lock_map[metadataPath] = threading.Lock()
            return self._lock_map[metadataPath]

    def _do_write(self, metadataPath, metadata, vmUuid, vmName, vmCategory, architecture, schemaVersion):
        with self._get_path_lock(metadataPath):
            dir_path = os.path.dirname(metadataPath)
            created_dir = False
            if not os.path.isdir(dir_path):
                try:
                    os.makedirs(dir_path)
                    created_dir = True
                except OSError:
                    if not os.path.isdir(dir_path):
                        raise
            if created_dir:
                _fsync_directory(dir_path)

            metadata_tmp = metadataPath + ".tmp"
            fd = os.open(metadata_tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(_ensure_bytes(metadata))
                    f.flush()
                    os.fsync(f.fileno())
            except:
                # fd is consumed by os.fdopen even on failure
                raise
            os.rename(metadata_tmp, metadataPath)
            _fsync_directory(metadataPath)

            if vmUuid:
                summary_path = metadataPath + ".summary"
                _write_summary_best_effort(
                    summary_path, vmUuid,
                    vm_name=vmName,
                    vm_category=vmCategory,
                    architecture=architecture,
                    schema_version=schemaVersion,
                )

            logger.debug("successfully wrote vm metadata to %s", metadataPath)
            return {}

    def _do_get(self, metadataPath):
        with self._get_path_lock(metadataPath):
            if not os.path.isfile(metadataPath):
                tmp_path = metadataPath + ".tmp"
                if os.path.isfile(tmp_path):
                    # .tmp without a corresponding final file means the previous write
                    # may have crashed before rename().  Do NOT promote it — the data
                    # could be truncated.  Return None so the caller triggers a re-write.
                    logger.warn("found orphan tmp file %s without final metadata; "
                                "not promoting (may be incomplete)", tmp_path)
                return {'metadata': None}

            try:
                with open(metadataPath, 'r') as f:
                    content = f.read()
                logger.debug("read vm metadata from %s (%d bytes)", metadataPath, len(content))
                return {'metadata': content}
            except Exception as e:
                logger.warn("failed to read metadata file %s: %s", metadataPath, e)
                return {'metadata': None}

    def _do_scan(self, metadataDir):
        if not metadataDir or not os.path.isabs(metadataDir):
            logger.warn("scan: metadataDir must be an absolute path: %s", metadataDir)
            return []
        if not os.path.isdir(metadataDir):
            return []

        entries = []
        for fname in os.listdir(metadataDir):
            is_tmp = fname.endswith(_METADATA_SUFFIX + '.tmp')
            if not (fname.endswith(_METADATA_SUFFIX) or is_tmp):
                continue
            vm_uuid = fname[:-len(_METADATA_SUFFIX + '.tmp')] if is_tmp else fname[:-len(_METADATA_SUFFIX)]
            if not _UUID_HEX_RE.match(vm_uuid):
                continue

            fpath = os.path.join(metadataDir, fname)
            metadata_path = fpath[:-4] if is_tmp else fpath
            if is_tmp and os.path.isfile(metadata_path):
                continue
            if not os.path.isfile(fpath):
                continue

            try:
                stat = os.stat(fpath)
                entry = VmMetadataScanEntry(
                    vmUuid=vm_uuid,
                    metadataPath=metadata_path,
                    sizeBytes=stat.st_size,
                    lastUpdateTime=int(stat.st_mtime * 1000),
                    incomplete=is_tmp,
                )

                summary_path = metadata_path + '.summary'
                try:
                    if os.path.isfile(summary_path):
                        with open(summary_path, 'r') as sf:
                            summary = json.loads(sf.read())
                        entry.vmName = summary.get('vmName', '')
                        entry.vmCategory = summary.get('vmCategory', '')
                        entry.architecture = summary.get('architecture', '')
                        entry.schemaVersion = summary.get('schemaVersion', '')
                except Exception as e:
                    logger.warn("failed to load metadata summary %s: %s", summary_path, e)

                entries.append(entry)
            except Exception as e:
                logger.warn("failed to stat metadata file %s: %s", fpath, e)

        logger.debug("scan_vm_metadata on %s: found %d entries", metadataDir, len(entries))
        return entries

    def _do_cleanup(self, metadataPath):
        with self._get_path_lock(metadataPath):
            removed_any = False
            for path in [metadataPath, metadataPath + '.tmp',
                         metadataPath + '.summary', metadataPath + '.summary.tmp']:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        removed_any = True
                except Exception as e:
                    if path == metadataPath:
                        raise Exception("failed to cleanup metadata file %s: %s" % (path, e))
                    logger.warn("failed to cleanup %s: %s", path, e)

            if removed_any:
                _fsync_directory(metadataPath)

            logger.debug("cleanup_vm_metadata: cleaned %s", metadataPath)

        return {}


def _write_summary_best_effort(summary_path, vm_uuid, vm_name='', vm_category='', architecture='', schema_version=''):
    """Write a lightweight summary file next to the metadata file.

    Failures are logged but never propagated (best-effort).
    """
    summary_tmp = summary_path + '.tmp'
    summary_json = json.dumps({
        "vmUuid": vm_uuid,
        "vmName": vm_name,
        "vmCategory": vm_category,
        "architecture": architecture,
        "schemaVersion": schema_version,
    }, ensure_ascii=False, separators=(',', ':'))
    try:
        fd = os.open(summary_tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(_ensure_bytes(summary_json))
            f.flush()
            os.fsync(f.fileno())
        os.rename(summary_tmp, summary_path)
        _fsync_directory(summary_path)
    except Exception as e:
        logger.warn("failed to write summary for VM %s: %s", vm_uuid, e)
        try:
            os.remove(summary_tmp)
        except OSError:
            pass
