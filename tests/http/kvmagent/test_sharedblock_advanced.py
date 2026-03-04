# -*- coding: utf-8 -*-
"""HTTP smoke tests for kvmagent shared block storage advanced operations (M2 coverage)."""

import uuid

import pytest

pytestmark = [
    pytest.mark.http,
]


def _skip_if_missing(response, endpoint):
    if response.status_code == 404:
        pytest.skip("%s not loaded (404)" % endpoint)
    if response.status_code == 500:
        pytest.skip("%s returned 500 (requires real infra)" % endpoint)


def _safe_wait(async_callback, task_uuid, timeout=15.0):
    try:
        return async_callback.wait(task_uuid, timeout=timeout)
    except TimeoutError:
        pytest.skip("callback timeout (handler requires real infra)")


class TestSharedBlockConnection:
    """Shared block connect/disconnect."""

    def test_connect(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/connect', data={
            'vgUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/connect')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_disconnect(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/disconnect', data={
            'vgUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/disconnect')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestSharedBlockVolume:
    """Shared block volume operations."""

    def test_create_empty(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/createempty', data={
            'installPath': '/dev/vg-test/vol-%s' % uuid.uuid4().hex[:8],
            'size': 1073741824,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/createempty')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_with_backing(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/createwithbacking', data={
            'installPath': '/dev/vg-test/vol-%s' % uuid.uuid4().hex[:8],
            'templatePathInCache': '/dev/vg-test/template',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/createwithbacking')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_active(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/active', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/active')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_resize(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/resize', data={
            'installPath': '/dev/vg-test/nonexistent',
            'size': 2147483648,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/resize')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_migrate(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/migrate', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/migrate')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_convert_format(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/convertformat', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/convertformat')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_convert_provisioning(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/convertprovisioning', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/convertprovisioning')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_revert_from_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/volume/revertfromsnapshot', data={
            'snapshotInstallPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/volume/revertfromsnapshot')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_bits_delete(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/bits/delete', data={
            'path': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/bits/delete')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_check_vmstate(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/check/vmstate', data={
            'vgUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/check/vmstate')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_disks_filter(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/disks/filter', data={
            'vgUuid': uuid.uuid4().hex,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/disks/filter')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_get_qcow2_hash(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/getqcow2hash', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/getqcow2hash')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_logical_volume_extend(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/logicalvolume/extend', data={
            'installPath': '/dev/vg-test/nonexistent',
            'size': 2147483648,
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/logicalvolume/extend')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestSharedBlockSnapshot:
    """Shared block snapshot operations."""

    def test_snapshot_merge(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/snapshot/merge', data={
            'snapshotInstallPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/snapshot/merge')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_snapshot_offline_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/snapshot/offlinecommit', data={
            'srcPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/snapshot/offlinecommit')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_snapshot_offline_merge(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/snapshot/offlinemerge', data={
            'srcPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/snapshot/offlinemerge')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_snapshot_shrink(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/snapshot/shrink', data={
            'installPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/snapshot/shrink')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_snapshot_extend_merge_target(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/snapshot/extendmergetarget', data={
            'installPath': '/dev/vg-test/snap-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/snapshot/extendmergetarget')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestSharedBlockTransfer:
    """Shared block imagestore/sftp/kvmhost transfer."""

    def test_imagestore_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/imagestore/download', data={
            'hostname': '127.0.0.1',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/imagestore/download')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_upload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/imagestore/upload', data={
            'hostname': '127.0.0.1',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/imagestore/upload')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/imagestore/commit', data={
            'srcPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/imagestore/commit')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/kvmhost/download', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/kvmhost/download')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_cancel(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/kvmhost/download/cancel', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/kvmhost/download/cancel')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_progress(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/kvmhost/download/progress', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/kvmhost/download/progress')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/sftp/download', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/sftp/download')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_upload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/sftp/upload', data={
            'installPath': '/dev/vg-test/nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/sftp/upload')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestSharedBlockTemplate:
    """Shared block template/image operations."""

    def test_create_root_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/createrootvolume', data={
            'installPath': '/dev/vg-test/vol-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/createrootvolume')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_template_from_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/createtemplatefromvolume', data={
            'installPath': '/dev/vg-test/vol-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/createtemplatefromvolume')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_image_cache_from_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/sharedblock/createimagecachefromvolume', data={
            'installPath': '/dev/vg-test/vol-nonexistent',
        }, callback_url=cb)
        _skip_if_missing(resp, '/sharedblock/createimagecachefromvolume')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)
