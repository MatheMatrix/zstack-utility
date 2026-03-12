from __future__ import absolute_import

import json
import logging
import os

from zstacklib.utils.vm_metadata_handler import VmMetadataHandler, VmMetadataScanEntry

logger = logging.getLogger(__name__)

# MN uses FILE_METADATA_SUFFIX = ".vmmeta"
# agent detects metadata files by this suffix; all paths are MN-issued
_METADATA_SUFFIX = '.vmmeta'


class FileBasedMetadataHandler(VmMetadataHandler):
    def _do_write(self, metadataPath, metadata, vmUuid, vmName, vmCategory, architecture, schemaVersion):
        dir_path = os.path.dirname(metadataPath)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        metadata_tmp = metadataPath + ".tmp"
        with open(metadata_tmp, 'w') as f:
            f.write(metadata)
            f.flush()
            os.fsync(f.fileno())
        os.rename(metadata_tmp, metadataPath)

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
        if not os.path.isfile(metadataPath):
            tmp_path = metadataPath + ".tmp"
            if os.path.isfile(tmp_path):
                try:
                    with open(tmp_path, 'r') as f:
                        content = f.read()
                    json.loads(content)
                    os.rename(tmp_path, metadataPath)
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

    def _do_get_all(self, metadataPath):
        metadata_dir = os.path.dirname(metadataPath)
        if not os.path.isdir(metadata_dir):
            return {'entries': []}

        base_name = os.path.basename(metadataPath)
        filter_vm_uuid = None
        if base_name.endswith(_METADATA_SUFFIX):
            candidate = base_name[:-len(_METADATA_SUFFIX)]
            if len(candidate) == 32:
                filter_vm_uuid = candidate

        # collect vm_uuids from metadata files and tmp files
        meta_uuids = set()
        tmp_uuids = set()

        for fname in os.listdir(metadata_dir):
            if fname.endswith(_METADATA_SUFFIX) and not fname.endswith('.tmp') and not fname.endswith('.summary'):
                vm_uuid = fname[:-len(_METADATA_SUFFIX)]
                if len(vm_uuid) == 32:
                    if filter_vm_uuid and vm_uuid != filter_vm_uuid:
                        continue
                    meta_uuids.add(vm_uuid)
            elif fname.endswith(_METADATA_SUFFIX + '.tmp'):
                vm_uuid = fname[:-(len(_METADATA_SUFFIX) + 4)]  # strip '.vmmeta.tmp'
                if len(vm_uuid) == 32:
                    if filter_vm_uuid and vm_uuid != filter_vm_uuid:
                        continue
                    tmp_uuids.add(vm_uuid)

        # .tmp is always newer than the main file (write flow: write .tmp -> fsync -> rename)
        incomplete_uuids = set()
        for vm_uuid in list(tmp_uuids):
            tmp_path = os.path.join(metadata_dir, vm_uuid + _METADATA_SUFFIX + '.tmp')
            meta_path = os.path.join(metadata_dir, vm_uuid + _METADATA_SUFFIX)
            try:
                with open(tmp_path, 'r') as f:
                    content = f.read()
                json.loads(content)
                os.rename(tmp_path, meta_path)
                meta_uuids.add(vm_uuid)
                logger.info("recovered tmp file to %s (valid JSON, newer data)", meta_path)
            except (ValueError, TypeError):
                if vm_uuid in meta_uuids:
                    try:
                        os.remove(tmp_path)
                        logger.debug("removed broken tmp file %s (old metadata still usable)", tmp_path)
                    except OSError:
                        pass
                else:
                    incomplete_uuids.add(vm_uuid)
                    logger.warn("tmp file %s contains incomplete JSON, no fallback", tmp_path)
            except Exception as e:
                if vm_uuid not in meta_uuids:
                    incomplete_uuids.add(vm_uuid)
                logger.warn("failed to recover tmp file %s: %s", tmp_path, e)

        entries = []

        for vm_uuid in meta_uuids:
            meta_path = os.path.join(metadata_dir, vm_uuid + _METADATA_SUFFIX)
            if not os.path.isfile(meta_path):
                continue

            summary_path = meta_path + '.summary'
            entry = {"path": meta_path, "incomplete": False}

            if os.path.isfile(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        summary = json.loads(f.read())
                    entry["uuid"] = summary.get("vmUuid", vm_uuid)
                    entry["name"] = summary.get("vmName")
                    entry["vmCategory"] = summary.get("vmCategory")
                    entry["architecture"] = summary.get("architecture")
                    entry["schemaVersion"] = summary.get("schemaVersion")
                    entry["hasSummary"] = True
                    entry["metadata"] = None
                    entries.append(entry)
                    continue
                except Exception as e:
                    logger.warn("failed to read summary %s: %s", summary_path, e)

            try:
                with open(meta_path, 'r') as f:
                    content = f.read()
                if content:
                    entry["uuid"] = vm_uuid
                    entry["name"] = None
                    entry["vmCategory"] = None
                    entry["architecture"] = None
                    entry["hasSummary"] = False
                    entry["metadata"] = content
                    entries.append(entry)
            except Exception as e:
                logger.warn("failed to read metadata %s: %s", meta_path, e)

        for vm_uuid in incomplete_uuids:
            tmp_path = os.path.join(metadata_dir, vm_uuid + _METADATA_SUFFIX + '.tmp')
            entry = {
                "uuid": vm_uuid,
                "path": tmp_path,
                "name": None,
                "vmCategory": None,
                "architecture": None,
                "hasSummary": False,
                "metadata": None,
                "schemaVersion": None,
                "incomplete": True,
            }
            entries.append(entry)

        logger.debug("get_vm_instance_metadata from %s: found %d entries",
                     metadata_dir, len(entries))
        return {'entries': entries}

    def _do_scan(self, metadataDir):
        if not os.path.isdir(metadataDir):
            return []

        entries = []
        for fname in os.listdir(metadataDir):
            if not fname.endswith(_METADATA_SUFFIX):
                continue
            if fname.endswith('.tmp') or fname.endswith('.summary'):
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
        for path in [metadataPath, metadataPath + '.tmp',
                     metadataPath + '.summary', metadataPath + '.summary.tmp']:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warn("failed to cleanup %s: %s", path, e)

        logger.debug("cleanup_vm_metadata: cleaned %s", metadataPath)
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
    except Exception as e:
        logger.warn("failed to write summary for VM %s: %s", vm_uuid, e)
        try:
            os.remove(summary_tmp)
        except OSError:
            pass
