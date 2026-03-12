from __future__ import absolute_import

import json
import logging
import os
import threading

from zstacklib.utils.vm_metadata_handler import VmMetadataHandler, VmMetadataScanEntry

logger = logging.getLogger(__name__)

# MN uses FILE_METADATA_SUFFIX = ".vmmeta"
# agent detects metadata files by this suffix; all paths are MN-issued
_METADATA_SUFFIX = '.vmmeta'


def _fsync_directory(file_path):
    """fsync the parent directory to ensure rename/unlink is durable."""
    dir_fd = os.open(os.path.dirname(file_path), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


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
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            metadata_tmp = metadataPath + ".tmp"
            with open(metadata_tmp, 'w') as f:
                f.write(metadata)
                f.flush()
                os.fsync(f.fileno())
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
                    try:
                        with open(tmp_path, 'r') as f:
                            content = f.read()
                        json.loads(content)
                        os.rename(tmp_path, metadataPath)
                        _fsync_directory(metadataPath)
                        logger.info("recovered tmp file to %s during get", metadataPath)
                    except (ValueError, TypeError):
                        logger.warn("tmp file %s contains incomplete JSON", tmp_path)
                        return {'metadata': None}
                    except Exception as e:
                        logger.warn("failed to recover tmp file %s: %s", tmp_path, e)
                        return {'metadata': None}
                else:
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
        if not os.path.isdir(metadataDir):
            return []

        entries = []
        for fname in os.listdir(metadataDir):
            if not fname.endswith(_METADATA_SUFFIX):
                continue
            vm_uuid = fname[:-len(_METADATA_SUFFIX)]
            if len(vm_uuid) != 32:
                continue

            fpath = os.path.join(metadataDir, fname)
            if not os.path.isfile(fpath):
                continue

            try:
                stat = os.stat(fpath)
                entry = VmMetadataScanEntry(
                    vmUuid=vm_uuid,
                    metadataPath=fpath,
                    sizeBytes=stat.st_size,
                    lastUpdateTime=int(stat.st_mtime),
                )

                summary_path = fpath + '.summary'
                try:
                    if os.path.isfile(summary_path):
                        with open(summary_path, 'r') as sf:
                            summary = json.loads(sf.read())
                        entry.vmName = summary.get('vmName', '')
                        entry.vmCategory = summary.get('vmCategory', 0)
                        entry.architecture = summary.get('architecture', '')
                        entry.schemaVersion = summary.get('schemaVersion', '')
                except Exception:
                    pass

                entries.append(entry)
            except Exception as e:
                logger.warn("failed to stat metadata file %s: %s", fpath, e)

        logger.debug("scan_vm_metadata on %s: found %d entries", metadataDir, len(entries))
        return entries

    def _do_cleanup(self, metadataPath):
        with self._get_path_lock(metadataPath):
            for path in [metadataPath, metadataPath + '.tmp',
                         metadataPath + '.summary', metadataPath + '.summary.tmp']:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.warn("failed to cleanup %s: %s", path, e)

            logger.debug("cleanup_vm_metadata: cleaned %s", metadataPath)

            # Remove the lock from the map while still holding it, to prevent
            # a race where another thread gets the old lock between our release
            # and the pop, then a third thread creates a new lock — causing two
            # threads to operate on the same path without mutual exclusion.
            with self._lock_map_lock:
                self._lock_map.pop(metadataPath, None)

        return {}


def _write_summary_best_effort(summary_path, vm_uuid, vm_name='', vm_category=0, architecture='', schema_version=''):
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
        with open(summary_tmp, 'w') as f:
            f.write(summary_json)
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
