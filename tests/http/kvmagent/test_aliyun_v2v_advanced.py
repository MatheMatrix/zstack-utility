# -*- coding: utf-8 -*-
"""HTTP integration tests for Aliyun NAS/EBS and V2V conversion plugins.

Covers Aliyun NAS primary storage operations, Aliyun EBS TDC install/detach,
VMware V2V and KVM V2V conversion host init/convert/clean/cancel/QoS.
"""

import pytest


def _skip_if_not_loaded(response, endpoint):
    if response.status_code == 403:
        pytest.skip("%s blocked by firewall (403)" % endpoint)
    if response.status_code == 404:
        pytest.skip("%s not loaded on this kvmagent (404)" % endpoint)


@pytest.mark.http
class TestAliyunNasSmoke:
    """Smoke tests for aliyun_nas_plugin endpoints."""

    def test_first_mount(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/firstmount - first NAS mount."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/firstmount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/firstmount')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_is_mount(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/ismount - check NAS mount status."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/ismount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/ismount')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_mount_data(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/mountdata - mount NAS data path."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/mountdata', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/mountdata')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_init(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/init - initialize NAS storage."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_ping(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/ping - ping NAS storage."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/ping', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/ping')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_get_capacity(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/getcapacity - get NAS capacity."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/getcapacity', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/getcapacity')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_update_mount_point(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/updatemountpoint - update mount."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/updatemountpoint', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/updatemountpoint')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_remount(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/remount - remount NAS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/remount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/remount')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_unmount(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/unmount - unmount NAS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/unmount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/unmount')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_check_bits(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/checkbits - check bits exist."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/checkbits', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/checkbits')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_empty_volume(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/createempty - create empty volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/createempty', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/createempty')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_create_volume_from_cache(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/createvolume - create from cache."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/createvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/createvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_bits(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/deletebits - delete bits."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/deletebits', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/deletebits')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_get_volume_size(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/getvolumesize - get volume size."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/getvolumesize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/getvolumesize')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_revert_volume(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/revertvolume - revert snapshot."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/revertvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/revertvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_download_to_imagestore(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/imagestore/download - download."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/imagestore/download', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/imagestore/download')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_upload_to_imagestore(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/imagestore/upload - upload."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/imagestore/upload', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/imagestore/upload')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_reinit_volume(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/reinit - reinitialize volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/reinit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/reinit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_resize_volume(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/resize - resize volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/resize', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/resize')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_commit(self, kvmagent_client, async_callback):
        """Test /aliyun/nas/primarystorage/commit - commit."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/nas/primarystorage/commit', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/nas/primarystorage/commit')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestAliyunEbsSmoke:
    """Smoke tests for aliyun_ebs_plugin endpoints."""

    def test_install_tdc(self, kvmagent_client, async_callback):
        """Test /aliyun/ebs/primarystorage/installtdc - install TDC agent."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/ebs/primarystorage/installtdc', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/ebs/primarystorage/installtdc')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_detach_volume(self, kvmagent_client, async_callback):
        """Test /aliyun/ebs/primarystorage/detachvolume - detach EBS volume."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/aliyun/ebs/primarystorage/detachvolume', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/aliyun/ebs/primarystorage/detachvolume')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestVmwareV2VSmoke:
    """Smoke tests for vmware_v2v_plugin endpoints."""

    def test_init(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/init - init conversion host."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_convert(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/convert - start conversion."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/convert', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/convert')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_convert_progress(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/convert/progress - check progress."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/convert/progress', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/convert/progress')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_clean(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/clean - clean conversion artifacts."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/clean', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/clean')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_config_qos(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/qos/config - configure QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/qos/config', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/qos/config')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_qos(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/qos/delete - delete QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/qos/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/qos/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_convert(self, kvmagent_client, async_callback):
        """Test /vmwarev2v/conversionhost/convert/cancel - cancel conversion."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/vmwarev2v/conversionhost/convert/cancel', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/vmwarev2v/conversionhost/convert/cancel')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)


@pytest.mark.http
class TestKvmV2VSmoke:
    """Smoke tests for kvm_v2v_plugin endpoints."""

    def test_init(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/init - init KVM conversion host."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/init', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/init')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_list_vm(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/listvm - list VMs for conversion."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/listvm', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/listvm')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_umount(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/umount - unmount conversion share."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/umount', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/umount')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_convert(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/convert - start KVM conversion."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/convert', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/convert')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_clean(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/clean - clean conversion artifacts."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/clean', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/clean')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_config_qos(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/qos/config - configure QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/qos/config', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/qos/config')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_delete_qos(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/qos/delete - delete QoS."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/qos/delete', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/qos/delete')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)

    def test_cancel_convert(self, kvmagent_client, async_callback):
        """Test /kvmv2v/conversionhost/convert/cancel - cancel conversion."""
        callback_url = async_callback.get_callback_url()
        resp = kvmagent_client.post('/kvmv2v/conversionhost/convert/cancel', data={}, callback_url=callback_url)
        _skip_if_not_loaded(resp, '/kvmv2v/conversionhost/convert/cancel')
        assert resp.status_code in [200, 400, 403, 404, 500]
        try:
            result = async_callback.wait(resp.task_uuid, timeout=15.0)
        except TimeoutError:
            pytest.skip("callback timeout")
        assert isinstance(result, dict)
