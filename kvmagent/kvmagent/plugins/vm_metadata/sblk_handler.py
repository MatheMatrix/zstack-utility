from __future__ import absolute_import

import logging

from kvmagent.plugins import vm_metadata

from .handler import VmMetadataHandler

logger = logging.getLogger(__name__)


class SblkMetadataHandler(VmMetadataHandler):
    def __init__(self, lvm_module, bash_module):
        """
        :param lvm_module:  the ``zstacklib.utils.lvm`` module (or compatible).
        :param bash_module: the ``zstacklib.utils.bash`` module (or compatible).
        """
        self._lvm = lvm_module
        self._bash = bash_module

    def _ensure_metadata_lv(self, metadata_path):
        """Create the metadata LV if it does not exist yet.

        The LV is created at INITIAL_LV_SIZE (4 MB) and initialised with
        an empty header + Slot A (payload = ``b'{}'``).
        """
        if self._lvm.lv_exists(metadata_path):
            return

        self._lvm.create_lv_from_absolute_path(
            metadata_path,
            vm_metadata.INITIAL_LV_SIZE,
            tag=vm_metadata.LV_METADATA_TAG,
            lock=False,
            exact_size=True,
        )
        vm_metadata.initialize_metadata_lv(
            metadata_path, vm_metadata.INITIAL_LV_SIZE)
        logger.info("created and initialized metadata LV %s", metadata_path)

    def _lv_list_func(self, vg):
        """Return list of ``(lv_name, lv_path, lv_size)`` tuples for *vg*.

        Decorated with ``@bash.in_bash`` at call-site via the injected bash
        module; here we define the plain function and the constructor caller
        wraps it.
        """
        r, o = self._bash.bash_ro(
            "lvs --nolocking -t %s --noheadings -o lv_name,lv_path,lv_size"
            " --units b --nosuffix --separator '|'" % vg
        )
        result = []
        for line in o.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 3:
                continue
            lv_name = parts[0].strip()
            lv_path = parts[1].strip()
            lv_size = int(parts[2].strip())
            result.append((lv_name, lv_path, lv_size))
        return result

    def _do_write(self, cmd):
        metadata_path = cmd.metadataPath
        self._ensure_metadata_lv(metadata_path)

        lvm = self._lvm

        def _get_lv_size():
            return int(lvm.get_lv_size(metadata_path))

        def _extend_lv(new_size):
            lvm.extend_lv(metadata_path, new_size)

        with lvm.OperateLv(metadata_path, shared=False):
            vm_metadata.write_metadata(
                lv_path=metadata_path,
                payload=cmd.metadata,
                lv_size_getter=_get_lv_size,
                lv_extend_func=_extend_lv,
                vm_uuid=cmd.vmInstanceUuid if cmd.vmInstanceUuid else '',
                vm_name=cmd.vmInstanceName if cmd.vmInstanceName else '',
            )

        logger.debug("successfully wrote vm metadata to %s", metadata_path)
        return {}

    def _do_read(self, cmd):
        metadata_path = cmd.metadataPath
        lvm = self._lvm

        if not lvm.lv_exists(metadata_path):
            return {'metadata': None}

        with lvm.OperateLv(metadata_path, shared=True):
            lv_size = int(lvm.get_lv_size(metadata_path))
            result = vm_metadata.read_metadata(metadata_path, lv_size)

        if result.is_usable():
            payload = result.payload.decode('utf-8') \
                if isinstance(result.payload, bytes) else result.payload
        else:
            raise Exception(
                "read vm metadata from %s failed: status=%s, message=%s"
                % (metadata_path, result.status, result.error))

        logger.debug("successfully read vm metadata from %s (status=%s)",
                     metadata_path, result.status)
        return {'metadata': payload}

    def _do_get_all(self, cmd):
        vg_uuid = cmd.vgUuid
        lvm = self._lvm
        bash = self._bash

        @bash.in_bash
        def _lv_list(vg):
            return self._lv_list_func(vg)

        metadata_lvs = vm_metadata.scan_metadata_lvs(vg_uuid, _lv_list)

        payloads = []
        incomplete_entries = []
        for item in metadata_lvs:
            lv_path = item['lv_path']
            lv_size = item['lv_size']
            vm_uuid = item.get('vm_uuid', '')
            try:
                with lvm.OperateLv(lv_path, shared=True):
                    read_result = vm_metadata.read_metadata(lv_path, lv_size)
                if read_result.is_usable():
                    payload = read_result.payload.decode('utf-8') \
                        if isinstance(read_result.payload, bytes) else read_result.payload
                    if payload:
                        payloads.append(payload)
                else:
                    incomplete_entries.append({
                        'vmUuid': vm_uuid,
                        'lvPath': lv_path,
                        'readStatus': read_result.status,
                        'error': read_result.error or '',
                    })
                    logger.warn("metadata LV %s is not usable: status=%s, error=%s",
                                lv_path, read_result.status, read_result.error)
            except Exception as e:
                logger.warn("failed to read metadata from %s: %s", lv_path, e)
                incomplete_entries.append({
                    'vmUuid': vm_uuid,
                    'lvPath': lv_path,
                    'readStatus': 'READ_ERROR',
                    'error': str(e),
                })

        logger.debug("get_vm_instance_metadata on vg %s: found %d usable, %d incomplete",
                     vg_uuid, len(payloads), len(incomplete_entries))
        return {
            'entries': payloads,
            'incompleteEntries': incomplete_entries,
        }

    def _do_scan(self, cmd):
        vg_uuid = cmd.vgUuid
        lvm = self._lvm
        bash = self._bash
        filter_vm_uuids = set(cmd.vmUuids) if cmd.vmUuids else None

        @bash.in_bash
        def _lv_list(vg):
            return self._lv_list_func(vg)

        metadata_lvs = vm_metadata.scan_metadata_lvs(vg_uuid, _lv_list)

        entries = []
        for item in metadata_lvs:
            vm_uuid = item['vm_uuid']
            if filter_vm_uuids and vm_uuid not in filter_vm_uuids:
                continue

            lv_path = item['lv_path']
            lv_size = item['lv_size']

            entry = {
                'vmUuid': vm_uuid,
                'metadataPath': lv_path,
                'sizeBytes': lv_size,
            }

            try:
                with lvm.OperateLv(lv_path, shared=True):
                    status = vm_metadata.get_metadata_status(lv_path, lv_size)
                if status.get('valid'):
                    entry['schemaVersion'] = status.get('schema_version', 0)
                    entry['lastUpdateTime'] = status.get('last_update_time', 0)
            except Exception as e:
                logger.warn("failed to read metadata status for %s: %s", lv_path, e)

            entries.append(entry)

        logger.debug("scan_vm_metadata on vg %s: found %d metadata LVs, returned %d entries",
                     vg_uuid, len(metadata_lvs), len(entries))
        return {'metadataEntries': entries}

    def _do_cleanup(self, cmd):
        metadata_path = cmd.metadataPath
        lvm = self._lvm

        try:
            if lvm.lv_exists(metadata_path):
                vm_metadata.delete_metadata_lv(metadata_path, lvm.delete_lv)
            else:
                logger.debug("metadata LV %s does not exist, skip cleanup", metadata_path)
        except Exception as e:
            raise Exception("failed to cleanup metadata LV %s: %s" % (metadata_path, e))

        logger.debug("cleanup_vm_metadata: cleaned %s", metadata_path)
        return {}
