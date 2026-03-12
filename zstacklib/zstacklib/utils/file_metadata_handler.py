from __future__ import absolute_import

import json
import logging
import os

from zstacklib.utils.vm_metadata_handler import VmMetadataHandler, VmMetadataScanEntry

logger = logging.getLogger(__name__)


class FileBasedMetadataHandler(VmMetadataHandler):
    def _do_write(self, metadataPath, metadata, vmInstanceUuid, vmInstanceName, architecture, schemaVersion):
        dir_path = os.path.dirname(metadataPath)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        metadata_tmp = metadataPath + ".tmp"
        with open(metadata_tmp, 'w') as f:
            f.write(metadata)
            f.flush()
            os.fsync(f.fileno())
        os.rename(metadata_tmp, metadataPath)

        if vmInstanceUuid:
            _write_summary_best_effort(
                dir_path, vmInstanceUuid,
                vm_name=vmInstanceName,
                architecture=architecture,
                schema_version=schemaVersion,
            )

        logger.debug("successfully wrote vm metadata to %s", metadataPath)
        return {}

    def _do_get(self, metadataPath):
        if not os.path.isfile(metadataPath):
            # try .tmp recovery: if .json doesn't exist, check .json.tmp
            tmp_path = metadataPath + ".tmp"
            if os.path.isfile(tmp_path):
                try:
                    with open(tmp_path, 'r') as f:
                        content = f.read()
                    json.loads(content)  # validate JSON completeness
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

        filter_vm_uuid = os.path.basename(metadataPath).replace('.json', '') if metadataPath.endswith('.json') else None
        if filter_vm_uuid and len(filter_vm_uuid) != 32:
            filter_vm_uuid = None

        # collect vm_uuids that have a .json file
        json_uuids = set()
        # collect vm_uuids that have a .json.tmp file
        tmp_uuids = set()

        for fname in os.listdir(metadata_dir):
            if fname.endswith('.json') and not fname.endswith('.tmp') and not fname.endswith('.summary'):
                vm_uuid = fname[:-5]  # strip '.json'
                if len(vm_uuid) == 32:
                    if filter_vm_uuid and vm_uuid != filter_vm_uuid:
                        continue
                    json_uuids.add(vm_uuid)
            elif fname.endswith('.json.tmp'):
                vm_uuid = fname[:-9]  # strip '.json.tmp'
                if len(vm_uuid) == 32:
                    if filter_vm_uuid and vm_uuid != filter_vm_uuid:
                        continue
                    tmp_uuids.add(vm_uuid)

        # .tmp is always newer than .json (write flow: write .tmp -> fsync -> rename)
        # try to recover every .tmp, regardless of whether .json exists
        incomplete_uuids = set()
        for vm_uuid in list(tmp_uuids):
            tmp_path = os.path.join(metadata_dir, "%s.json.tmp" % vm_uuid)
            json_path = os.path.join(metadata_dir, "%s.json" % vm_uuid)
            try:
                with open(tmp_path, 'r') as f:
                    content = f.read()
                json.loads(content)  # validate JSON completeness
                # JSON is valid -- complete the interrupted atomic write
                os.rename(tmp_path, json_path)
                json_uuids.add(vm_uuid)
                logger.info("recovered tmp file to %s (valid JSON, newer data)", json_path)
            except (ValueError, TypeError):
                # invalid JSON -- .tmp is a half-write
                if vm_uuid in json_uuids:
                    # old .json still usable, just remove the broken .tmp
                    try:
                        os.remove(tmp_path)
                        logger.debug("removed broken tmp file %s (old json still usable)", tmp_path)
                    except OSError:
                        pass
                else:
                    # no .json at all -- truly incomplete
                    incomplete_uuids.add(vm_uuid)
                    logger.warn("tmp file %s contains incomplete JSON, no .json fallback", tmp_path)
            except Exception as e:
                if vm_uuid not in json_uuids:
                    incomplete_uuids.add(vm_uuid)
                logger.warn("failed to recover tmp file %s: %s", tmp_path, e)

        entries = []

        # process normal .json entries
        for vm_uuid in json_uuids:
            json_path = os.path.join(metadata_dir, "%s.json" % vm_uuid)
            if not os.path.isfile(json_path):
                continue

            summary_path = os.path.join(metadata_dir, "%s.json.summary" % vm_uuid)
            entry = {"path": json_path, "incomplete": False}

            # prefer reading .summary
            if os.path.isfile(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        summary = json.loads(f.read())
                    entry["uuid"] = summary.get("vmUuid", vm_uuid)
                    entry["name"] = summary.get("vmName")
                    entry["architecture"] = summary.get("architecture")
                    entry["schemaVersion"] = summary.get("schemaVersion")
                    entry["hasSummary"] = True
                    entry["metadata"] = None
                    entries.append(entry)
                    continue
                except Exception as e:
                    logger.warn("failed to read summary %s: %s", summary_path, e)

            # no .summary or read failed -> read full .json
            try:
                with open(json_path, 'r') as f:
                    content = f.read()
                if content:
                    entry["uuid"] = vm_uuid
                    entry["name"] = None
                    entry["architecture"] = None
                    entry["hasSummary"] = False
                    entry["metadata"] = content
                    entries.append(entry)
            except Exception as e:
                logger.warn("failed to read metadata %s: %s", json_path, e)

        # process incomplete tmp-only entries
        for vm_uuid in incomplete_uuids:
            tmp_path = os.path.join(metadata_dir, "%s.json.tmp" % vm_uuid)
            entry = {
                "uuid": vm_uuid,
                "path": tmp_path,
                "name": None,
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
            if not fname.endswith('.json') or fname.endswith('.tmp'):
                continue
            vm_uuid = fname[:-5]  # strip '.json'
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

                # read .json.summary for lightweight fields
                summary_path = os.path.join(metadataDir, "%s.json.summary" % vm_uuid)
                try:
                    if os.path.isfile(summary_path):
                        with open(summary_path, 'r') as sf:
                            summary = json.loads(sf.read())
                        entry.vmName = summary.get('vmName', '')
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
        # delete .json
        try:
            if os.path.exists(metadataPath):
                os.remove(metadataPath)
        except Exception as e:
            logger.warn("failed to cleanup metadata file %s: %s", metadataPath, e)

        # delete .json.summary
        summary_path = metadataPath + ".summary"
        try:
            if os.path.exists(summary_path):
                os.remove(summary_path)
        except Exception as e:
            logger.warn("failed to cleanup summary file %s: %s", summary_path, e)

        logger.debug("cleanup_vm_metadata: cleaned %s", metadataPath)
        return {}


def _write_summary_best_effort(meta_dir, vm_uuid, vm_name='', architecture='', schema_version=''):
    """Write a lightweight ``.json.summary`` file next to the main ``.json``.

    Failures are logged but never propagated (best-effort).
    """
    summary_target = os.path.join(meta_dir, "%s.json.summary" % vm_uuid)
    summary_tmp = os.path.join(meta_dir, "%s.json.summary.tmp" % vm_uuid)
    summary_json = json.dumps({
        "vmUuid": vm_uuid,
        "vmName": vm_name,
        "architecture": architecture,
        "schemaVersion": schema_version,
    }, ensure_ascii=False, separators=(',', ':'))
    try:
        with open(summary_tmp, 'w') as f:
            f.write(summary_json)
            f.flush()
            os.fsync(f.fileno())
        os.rename(summary_tmp, summary_target)
    except Exception as e:
        logger.warn("failed to write summary for VM %s: %s", vm_uuid, e)
        try:
            os.remove(summary_tmp)
        except OSError:
            pass
