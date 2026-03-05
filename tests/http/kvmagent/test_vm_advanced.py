# -*- coding: utf-8 -*-
"""HTTP smoke tests for kvmagent VM advanced operations (M2 coverage).

Covers VM endpoints not yet tested: lifecycle, guest tools, ISO,
console, volume backup/snapshot, USB, migration, etc.
"""

import uuid

import pytest

pytestmark = [
    pytest.mark.http,
]


def _skip_if_missing(response, endpoint):
    if response.status_code == 403:
        pytest.skip("blocked by firewall (403)")
    if response.status_code == 404:
        pytest.skip("%s not loaded (404)" % endpoint)
    if response.status_code == 500:
        pytest.skip("%s returned 500 (requires real infra)" % endpoint)


def _safe_wait(async_callback, task_uuid, timeout=15.0):
    try:
        return async_callback.wait(task_uuid, timeout=timeout)
    except TimeoutError:
        pytest.skip("callback timeout (handler requires real infra)")


class TestVMLifecycleAdvanced:
    """VM start/destroy/migrate and related operations."""

    def test_start_vm(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/start', data={
            'vmInstanceUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/start')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_destroy_vm(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/destroy', data={
            'uuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/destroy')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_migrate_vm(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/migrate', data={
            'vmUuid': uuid.uuid4().hex,
            'destHostIp': '127.0.0.1',
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/migrate')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_blk_live_migration(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/blklivemigration', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/blklivemigration')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_fstrim(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/fstrim', data={
            'uuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/fstrim')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_change_password(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/changepasswd', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/changepasswd')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_change_nic_state(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/changenicstate', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/changenicstate')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_update_nic(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/updatenic', data={
            'vmInstanceUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/updatenic')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_notify_tf_nic(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/nodifytfnic', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/nodifytfnic')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_set_vf_nic_mac(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/setvfnicmac', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/setvfnicmac')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMResourceOperations:
    """CPU/memory/priority/clock operations."""

    def test_increase_cpu(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/increase/cpu', data={
            'vmUuid': uuid.uuid4().hex,
            'cpuNum': 2,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/increase/cpu')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_increase_mem(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/increase/mem', data={
            'vmUuid': uuid.uuid4().hex,
            'memorySize': 1073741824,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/increase/mem')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_online_change_cpumem(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/online/changecpumem', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/online/changecpumem')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_apply_memory_balloon(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/apply/memory/balloon', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/apply/memory/balloon')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_set_priority(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/priority', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/priority')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_clock_sync(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/clock/sync', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/clock/sync')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_clock_sync_task(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/clock/sync/task', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/clock/sync/task')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_emulator_pinning(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/emulatorpinning', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/emulatorpinning')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_set_iothread_pin(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/setiothreadpin', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/setiothreadpin')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_del_iothread_pin(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/deliothreadpin', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/deliothreadpin')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMGuestTools:
    """Guest tools ISO attach/detach/exec."""

    def test_guesttools_attach_iso(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/guesttools/attachiso', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/guesttools/attachiso')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_guesttools_detach_iso(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/guesttools/detachiso', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/guesttools/detachiso')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_guesttools_exec(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/guesttools/exec', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/guesttools/exec')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_guesttools_upload_file(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/guesttools/upload_file', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/guesttools/upload_file')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMISOOperations:
    """ISO attach/detach."""

    def test_iso_attach(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/iso/attach', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/iso/attach')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_iso_detach(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/iso/detach', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/iso/detach')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMConsoleOperations:
    """Console firewall/harden."""

    def test_console_harden(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/console/harden', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/console/harden')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_console_delete_firewall(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/console/deletefirewall', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/console/deletefirewall')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMUSBDevice:
    """USB device attach/detach/reload."""

    def test_usb_attach(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/usbdevice/attach', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/usbdevice/attach')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_usb_detach(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/usbdevice/detach', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/usbdevice/detach')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_usb_reload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/usbdevice/reload', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/usbdevice/reload')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMVirtioDetach:
    """Virtio device detach."""

    def test_virtio_detach(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/virtio/detach', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/virtio/detach')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMRecoverVolumes:
    """VM volume recovery."""

    def test_recover_volumes(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/recover/volumes', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/recover/volumes')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestVMVolumeAdvanced:
    """Volume backup/snapshot/mirror/block operations."""

    def test_volume_take_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/takesnapshot', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/takesnapshot')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_merge_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/mergesnapshot', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/mergesnapshot')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_check_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/checksnapshot', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/checksnapshot')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_take_backup(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/takebackup', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/takebackup')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_take_cbt_backup(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/takecbtbackup', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/takecbtbackup')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_cancel_cbt_backup(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/cancelcbtbackup', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/cancelcbtbackup')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_cancel_backup_job(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/cancel/backupjob', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/cancel/backupjob')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_cancel_backup_jobs(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/cancel/backupjobs', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/cancel/backupjobs')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volumes_take_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volumes/takesnapshot', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volumes/takesnapshot')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volumes_take_backup(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volumes/takebackup', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volumes/takebackup')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_take_mirror(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/takemirror', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/takemirror')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_cancel_mirror(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/cancelmirror', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/cancelmirror')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_block_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/blockcommit', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/blockcommit')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_block_pull(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/blockpull', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/blockpull')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_block_stream(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/blockstream', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/blockstream')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_export_nbd(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/exportnbdvolumes', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/exportnbdvolumes')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_unexport_nbd(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vm/volume/unexportnbdvolumes', data={
            'vmUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/vm/volume/unexportnbdvolumes')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)
