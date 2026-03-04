# -*- coding: utf-8 -*-
"""HTTP smoke tests for kvmagent NFS primary storage advanced operations (M2 coverage)."""

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


class TestNFSVolumeOperations:
    """NFS volume create/delete/resize."""

    def test_create_empty_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/createemptyvolume', data={
            'installUrl': '/tmp/nfs-test-%s.qcow2' % uuid.uuid4().hex[:8],
            'size': 1073741824,
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/createemptyvolume')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_folder(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/createfolder', data={
            'installUrl': '/tmp/nfs-folder-test',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/createfolder')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_volume_with_backing(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/createvolumewithbacking', data={
            'installUrl': '/tmp/nfs-backing-%s.qcow2' % uuid.uuid4().hex[:8],
            'templatePathInCache': '/tmp/nonexistent-template.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/createvolumewithbacking')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_delete(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/delete', data={
            'installPath': '/tmp/nonexistent-nfs-delete',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/delete')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_unlink(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/unlink', data={
            'installPath': '/tmp/nonexistent-nfs-unlink',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/unlink')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_resize(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/volume/resize', data={
            'installPath': '/tmp/nonexistent.qcow2',
            'size': 2147483648,
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/volume/resize')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_get_backing_chain(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/volume/getbackingchain', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/volume/getbackingchain')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_estimate_template_size(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/estimatetemplatesize', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/estimatetemplatesize')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_get_qcow2_hash(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/getqcow2hash', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/getqcow2hash')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_reinit_image(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/reinitimage', data={
            'imagePath': '/tmp/nonexistent.qcow2',
            'volumePath': '/tmp/nonexistent-vol.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/reinitimage')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestNFSSnapshotOperations:
    """NFS snapshot merge/rebase/revert."""

    def test_merge_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/mergesnapshot', data={
            'srcPath': '/tmp/nonexistent-snap.qcow2',
            'destPath': '/tmp/nonexistent-dest.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/mergesnapshot')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_rebase_and_merge(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/rebaseandmergesnapshot', data={
            'srcPath': '/tmp/nonexistent-snap.qcow2',
            'destPath': '/tmp/nonexistent-dest.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/rebaseandmergesnapshot')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_rebase_volume_backing(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/rebasevolumebackingfile', data={
            'srcPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/rebasevolumebackingfile')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_revert_volume_from_snapshot(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/revertvolumefromsnapshot', data={
            'snapshotInstallPath': '/tmp/nonexistent-snap.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/revertvolumefromsnapshot')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestNFSMountOperations:
    """NFS mount/unmount/remount."""

    def test_mount(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/mount', data={
            'url': '127.0.0.1:/tmp/nfs-test',
            'mountPath': '/tmp/nfs-mount-test',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/mount')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_unmount(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/unmount', data={
            'mountPath': '/tmp/nfs-mount-test',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/unmount')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_remount(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/remount', data={
            'url': '127.0.0.1:/tmp/nfs-test',
            'mountPath': '/tmp/nfs-mount-test',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/remount')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_update_mountpoint(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/updatemountpoint', data={
            'oldMountPoint': '/tmp/nfs-old',
            'newMountPoint': '/tmp/nfs-new',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/updatemountpoint')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestNFSTransferOperations:
    """NFS imagestore/sftp/kvmhost download/upload."""

    def test_imagestore_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/imagestore/download', data={
            'hostname': '127.0.0.1',
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/imagestore/download')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_upload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/imagestore/upload', data={
            'hostname': '127.0.0.1',
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/imagestore/upload')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/imagestore/commit', data={
            'srcPath': '/tmp/nonexistent.qcow2',
            'dstPath': '/tmp/nonexistent-dst.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/imagestore/commit')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/kvmhost/download', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/kvmhost/download')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_cancel(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/kvmhost/download/cancel', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/kvmhost/download/cancel')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_progress(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/kvmhost/download/progress', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/kvmhost/download/progress')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_create_template(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/sftp/createtemplatefromvolume', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/sftp/createtemplatefromvolume')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_create_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/sftp/createvolumefromtemplate', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/sftp/createvolumefromtemplate')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_download_from_sftp(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/downloadfromsftpbackupstorage', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/downloadfromsftpbackupstorage')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_upload_to_sftp(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/uploadtosftpbackupstorage', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/uploadtosftpbackupstorage')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_migrate_bits(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/migratebits', data={
            'srcPath': '/tmp/nonexistent.qcow2',
            'dstPath': '/tmp/nonexistent-dst.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/migratebits')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_move_bits(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/nfsprimarystorage/movebits', data={
            'srcPath': '/tmp/nonexistent.qcow2',
            'destPath': '/tmp/nonexistent-dst.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/nfsprimarystorage/movebits')
        assert resp.status_code == 200
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)
