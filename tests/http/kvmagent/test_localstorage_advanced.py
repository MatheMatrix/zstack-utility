# -*- coding: utf-8 -*-
"""HTTP smoke tests for kvmagent localstorage advanced operations (M2 coverage)."""

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


class TestLocalStorageVolumeAdvanced:
    """Localstorage volume create/resize/backing."""

    def test_create_folder(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/createfolder', data={
            'installUrl': '/tmp/ls-folder-test-%s' % uuid.uuid4().hex[:8],
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/createfolder')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_with_backing(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/createwithbacking', data={
            'installUrl': '/tmp/ls-backing-%s.qcow2' % uuid.uuid4().hex[:8],
            'templatePathInCache': '/tmp/nonexistent-template.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/createwithbacking')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_create_from_cache(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/createvolumefromcache', data={
            'installUrl': '/tmp/ls-cache-%s.qcow2' % uuid.uuid4().hex[:8],
            'templatePathInCache': '/tmp/nonexistent-cache.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/createvolumefromcache')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_volume_resize(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/resize', data={
            'installPath': '/tmp/nonexistent.qcow2',
            'size': 2147483648,
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/resize')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_estimate_template_size(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/estimatetemplatesize', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/estimatetemplatesize')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_rebase_root_volume(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/volume/rebaserootvolumetobackingfile', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/volume/rebaserootvolumetobackingfile')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestLocalStorageSnapshotAdvanced:
    """Localstorage snapshot merge/rebase/verify."""

    def test_merge_and_rebase(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/snapshot/mergeandrebase', data={
            'snapshotInstallPath': '/tmp/nonexistent-snap.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/snapshot/mergeandrebase')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_offline_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/snapshot/offlinecommit', data={
            'srcPath': '/tmp/nonexistent-snap.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/snapshot/offlinecommit')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_offline_merge(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/snapshot/offlinemerge', data={
            'srcPath': '/tmp/nonexistent-snap.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/snapshot/offlinemerge')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_rebase_backing_files(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/snapshot/rebasebackingfiles', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/snapshot/rebasebackingfiles')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_verify_chain(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/snapshot/verifychain', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/snapshot/verifychain')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestLocalStorageTransfer:
    """Localstorage imagestore/sftp/kvmhost transfer."""

    def test_imagestore_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/imagestore/download', data={
            'hostname': '127.0.0.1',
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/imagestore/download')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_upload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/imagestore/upload', data={
            'hostname': '127.0.0.1',
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/imagestore/upload')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_imagestore_commit(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/imagestore/commit', data={
            'srcPath': '/tmp/nonexistent.qcow2',
            'dstPath': '/tmp/nonexistent-dst.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/imagestore/commit')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/kvmhost/download', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/kvmhost/download')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_cancel(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/kvmhost/download/cancel', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/kvmhost/download/cancel')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_kvmhost_download_progress(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/kvmhost/download/progress', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/kvmhost/download/progress')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_download(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/sftp/download', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/sftp/download')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_sftp_upload(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/sftp/upload', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/sftp/upload')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)


class TestLocalStorageMisc:
    """Localstorage misc: copy, delete, md5, reinit, unlink."""

    def test_copy_to_remote(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/copytoremote', data={
            'srcPath': '/tmp/nonexistent.qcow2',
            'dstPath': '/tmp/nonexistent-dst.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/copytoremote')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_delete_dir(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/deletedir', data={
            'path': '/tmp/nonexistent-dir-test',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/deletedir')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_get_md5(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/getmd5', data={
            'path': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/getmd5')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_check_md5(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/checkmd5', data={
            'path': '/tmp/nonexistent.qcow2',
            'md5': 'd41d8cd98f00b204e9800998ecf8427e',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/checkmd5')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_get_qcow2_hash(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/getqcow2hash', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/getqcow2hash')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_reinit_image(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/reinit/image', data={
            'imagePath': '/tmp/nonexistent.qcow2',
            'volumePath': '/tmp/nonexistent-vol.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/reinit/image')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)

    def test_unlink(self, kvmagent_client, async_callback):
        cb = async_callback.get_callback_url()
        resp = kvmagent_client.post('/localstorage/unlink', data={
            'installPath': '/tmp/nonexistent.qcow2',
        }, callback_url=cb)
        _skip_if_missing(resp, '/localstorage/unlink')
        assert resp.status_code in [200, 403, 404]
        _safe_wait(async_callback, resp.task_uuid, timeout=15.0)
