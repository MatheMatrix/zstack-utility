"""
Unit tests for vm_plugin block-cache API handlers and helpers.

Covers:
- attach_volume_cache handler
- detach_volume_cache handler
- DetachBlockCacheTaskDaemon
- add_caching_store helper function
"""
import json

try:
    import mock
except ImportError:
    from unittest import mock

from unittest import TestCase

from lxml import etree

from zstacklib.utils import jsonobject, http, plugin

from kvmagent import kvmagent
from kvmagent.plugins.vm_plugin import (
    AttachBlockCacheRsp,
    DetachBlockCacheRsp,
    DetachBlockCacheTaskDaemon,
    Vm,
    VmPlugin,
    add_caching_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(payload):
    return {http.REQUEST_BODY: json.dumps(payload)}


def _make_mock_vm(uuid="vm-1", state=Vm.VM_STATE_RUNNING):
    vm = mock.MagicMock(spec=Vm)
    vm.uuid = uuid
    vm.state = state
    vm._get_target_disk.return_value = (mock.MagicMock(), "vda")
    return vm


def _attach_payload(instance_uuid="vm-1", volume_install_path="/vol/path",
                    cache_install_path="/cache/path"):
    return {
        "instanceUuid": instance_uuid,
        "volume": {
            "installPath": volume_install_path,
            "cache": {
                "installPath": cache_install_path,
            },
        },
    }


def _detach_payload(instance_uuid="vm-1", volume_install_path="/vol/path",
                    cache_install_path="/cache/path", timeout=None, delete=False):
    cache_obj = {"installPath": cache_install_path}
    if timeout is not None:
        cache_obj["timeout"] = timeout
    if delete:
        cache_obj["delete"] = True
    return {
        "instanceUuid": instance_uuid,
        "volume": {
            "installPath": volume_install_path,
            "cache": cache_obj,
        },
    }


# ---------------------------------------------------------------------------
# attach_volume_cache
# ---------------------------------------------------------------------------

class TestAttachVolumeCache(TestCase):

    @mock.patch('kvmagent.plugins.vm_plugin.CacheVirshWrapper')
    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_attach_success(self, mock_get_vm, mock_virsh):
        vm = _make_mock_vm(state=Vm.VM_STATE_RUNNING)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        req = _make_request(_attach_payload())
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertTrue(rsp.success)
        mock_virsh.block_cache_attach.assert_called_once_with(
            domain="vm-1",
            path="/vol/path",
            cache="/cache/path",
        )

    @mock.patch('kvmagent.plugins.vm_plugin.CacheVirshWrapper')
    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_attach_paused_vm(self, mock_get_vm, mock_virsh):
        vm = _make_mock_vm(state=Vm.VM_STATE_PAUSED)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        req = _make_request(_attach_payload())
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertTrue(rsp.success)
        mock_virsh.block_cache_attach.assert_called_once()

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_attach_vm_not_running(self, mock_get_vm):
        vm = _make_mock_vm(state=Vm.VM_STATE_SHUTDOWN)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        req = _make_request(_attach_payload())
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)
        self.assertIn("running or paused", rsp.error)

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_attach_missing_cache_install_path(self, mock_get_vm):
        vm = _make_mock_vm(state=Vm.VM_STATE_RUNNING)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        payload = {
            "instanceUuid": "vm-1",
            "volume": {
                "installPath": "/vol/path",
                # no cache field
            },
        }
        req = _make_request(payload)
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)
        self.assertIn("installPath", rsp.error)

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_attach_empty_cache_install_path(self, mock_get_vm):
        vm = _make_mock_vm(state=Vm.VM_STATE_RUNNING)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        payload = {
            "instanceUuid": "vm-1",
            "volume": {
                "installPath": "/vol/path",
                "cache": {"installPath": ""},
            },
        }
        req = _make_request(payload)
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid',
                side_effect=kvmagent.KvmError('unable to find vm'))
    def test_attach_vm_not_found(self, mock_get_vm):
        vm_plugin = VmPlugin()

        req = _make_request(_attach_payload(instance_uuid="nonexistent"))
        result_json = vm_plugin.attach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)
        self.assertIn("unable to find vm", rsp.error)


# ---------------------------------------------------------------------------
# detach_volume_cache
# ---------------------------------------------------------------------------

class TestDetachVolumeCache(TestCase):

    @mock.patch('kvmagent.plugins.vm_plugin.DetachBlockCacheTaskDaemon')
    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_detach_success(self, mock_get_vm, mock_daemon_cls):
        vm = _make_mock_vm(state=Vm.VM_STATE_RUNNING)
        mock_get_vm.return_value = vm
        daemon_instance = mock.MagicMock()
        mock_daemon_cls.return_value = daemon_instance
        daemon_instance.__enter__ = mock.MagicMock(return_value=daemon_instance)
        daemon_instance.__exit__ = mock.MagicMock(return_value=False)
        vm_plugin = VmPlugin()

        req = _make_request(_detach_payload())
        result_json = vm_plugin.detach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertTrue(rsp.success)
        daemon_instance.detach.assert_called_once()

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_detach_vm_not_running(self, mock_get_vm):
        vm = _make_mock_vm(state=Vm.VM_STATE_SHUTDOWN)
        mock_get_vm.return_value = vm
        vm_plugin = VmPlugin()

        req = _make_request(_detach_payload())
        result_json = vm_plugin.detach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)
        self.assertIn("running or paused", rsp.error)

    @mock.patch('kvmagent.plugins.vm_plugin.DetachBlockCacheTaskDaemon')
    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid')
    def test_detach_paused_vm(self, mock_get_vm, mock_daemon_cls):
        vm = _make_mock_vm(state=Vm.VM_STATE_PAUSED)
        mock_get_vm.return_value = vm
        daemon_instance = mock.MagicMock()
        mock_daemon_cls.return_value = daemon_instance
        daemon_instance.__enter__ = mock.MagicMock(return_value=daemon_instance)
        daemon_instance.__exit__ = mock.MagicMock(return_value=False)
        vm_plugin = VmPlugin()

        req = _make_request(_detach_payload())
        result_json = vm_plugin.detach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertTrue(rsp.success)

    @mock.patch('kvmagent.plugins.vm_plugin.get_vm_by_uuid',
                side_effect=kvmagent.KvmError('unable to find vm'))
    def test_detach_vm_not_found(self, mock_get_vm):
        vm_plugin = VmPlugin()

        req = _make_request(_detach_payload(instance_uuid="nonexistent"))
        result_json = vm_plugin.detach_volume_cache(req)
        rsp = jsonobject.loads(result_json)

        self.assertFalse(rsp.success)
        self.assertIn("unable to find vm", rsp.error)


# ---------------------------------------------------------------------------
# DetachBlockCacheTaskDaemon
# ---------------------------------------------------------------------------

class TestDetachBlockCacheTaskDaemon(TestCase):

    def _make_daemon(self, vm_uuid="vm-1", volume_install_path="/vol/path",
                     cache_install_path="/cache/path", timeout=None, delete=False):
        volume = mock.MagicMock()
        volume.installPath = volume_install_path
        cache = mock.MagicMock()
        cache.installPath = cache_install_path
        cache.timeout = timeout
        cache.delete = delete
        volume.cache = cache
        with mock.patch.object(plugin.TaskDaemon, '__init__', return_value=None):
            daemon = DetachBlockCacheTaskDaemon(mock.MagicMock(), vm_uuid, volume)
        return daemon

    def test_initial_state(self):
        daemon = self._make_daemon()
        self.assertEqual(daemon.progress, 0)
        self.assertIsNone(daemon.error)

    def test_get_percent(self):
        daemon = self._make_daemon()
        self.assertEqual(daemon._get_percent(), 0)
        daemon.progress = 42
        self.assertEqual(daemon._get_percent(), 42)

    def test_on_progress_updates(self):
        daemon = self._make_daemon()
        daemon._on_progress(50.0, None)
        self.assertEqual(daemon.progress, 50)
        self.assertIsNone(daemon.error)

    def test_on_progress_clamp_high(self):
        daemon = self._make_daemon()
        daemon._on_progress(120.0, None)
        self.assertEqual(daemon.progress, 99)

    def test_on_progress_clamp_low(self):
        daemon = self._make_daemon()
        daemon._on_progress(-10.0, None)
        self.assertEqual(daemon.progress, 0)

    def test_on_progress_records_error(self):
        daemon = self._make_daemon()
        daemon._on_progress(30.0, "I/O error")
        self.assertEqual(daemon.progress, 30)
        self.assertEqual(daemon.error, "I/O error")

    def test_on_progress_none_preserves_progress(self):
        daemon = self._make_daemon()
        daemon.progress = 42
        daemon._on_progress(None, None)
        self.assertEqual(daemon.progress, 42)

    def test_get_detail(self):
        daemon = self._make_daemon(vm_uuid="vm-abc", volume_install_path="/vol/abc")
        detail = daemon._get_detail()
        self.assertEqual(detail.vmUuid, "vm-abc")
        self.assertEqual(detail.volumeInstallPath, "/vol/abc")

    @mock.patch('kvmagent.plugins.vm_plugin.CacheVirshWrapper')
    def test_detach_calls_virsh_wrapper(self, mock_virsh):
        daemon = self._make_daemon(timeout=60, delete=True)
        daemon.detach()

        mock_virsh.block_cache_detach.assert_called_once()
        _, kwargs = mock_virsh.block_cache_detach.call_args
        self.assertEqual(kwargs['domain'], "vm-1")
        self.assertEqual(kwargs['path'], "/vol/path")
        self.assertEqual(kwargs['timeout'], 60)
        self.assertTrue(kwargs['delete'])
        self.assertEqual(daemon.progress, 100)

    @mock.patch('kvmagent.plugins.vm_plugin.CacheVirshWrapper')
    def test_detach_no_timeout_no_delete(self, mock_virsh):
        daemon = self._make_daemon(timeout=None, delete=False)
        daemon.detach()

        _, kwargs = mock_virsh.block_cache_detach.call_args
        self.assertIsNone(kwargs['timeout'])
        self.assertFalse(kwargs['delete'])

    @mock.patch('kvmagent.plugins.vm_plugin.CacheVirshWrapper')
    def test_detach_raises_on_error(self, mock_virsh):
        daemon = self._make_daemon()

        def fake_detach(**kwargs):
            on_progress = kwargs.get('on_progress')
            if on_progress:
                on_progress(50.0, "detach I/O error")

        mock_virsh.block_cache_detach.side_effect = fake_detach
        with self.assertRaises(Exception) as ctx:
            daemon.detach()
        self.assertIn("detach I/O error", str(ctx.exception))

    def test_cancel_does_not_raise(self):
        daemon = self._make_daemon()
        daemon._cancel()  # should just log a warning, not raise


# ---------------------------------------------------------------------------
# add_caching_store
# ---------------------------------------------------------------------------

class TestAddCachingStore(TestCase):

    def _make_disk_element(self):
        return etree.Element("disk", attrib={"type": "file", "device": "disk"})

    def _make_volume(self, install_path="/vol/path", device_type="file",
                     cache_install_path="/cache/path"):
        vol = mock.MagicMock()
        vol.installPath = install_path
        vol.deviceType = device_type
        cache = mock.MagicMock()
        cache.installPath = cache_install_path
        # Simulate JsonObject.hasattr behavior
        cache.hasattr = mock.MagicMock(return_value=True)
        vol.cache = cache
        return vol

    def test_adds_caching_store_element(self):
        disk = self._make_disk_element()
        volume = self._make_volume(cache_install_path="/lcache/lcache0")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNotNone(cs)
        self.assertEqual(cs.get("type"), "file")

        fmt = cs.find("format")
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt.get("type"), "qcow2")

        source = cs.find("source")
        self.assertIsNotNone(source)
        self.assertEqual(source.get("file"), "/lcache/lcache0")

    def test_no_cache_does_nothing(self):
        disk = self._make_disk_element()
        volume = mock.MagicMock()
        volume.cache = None
        volume.deviceType = "file"

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)

    def test_empty_install_path_does_nothing(self):
        disk = self._make_disk_element()
        volume = self._make_volume(cache_install_path="")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)

    def test_none_install_path_does_nothing(self):
        disk = self._make_disk_element()
        volume = self._make_volume(cache_install_path=None)

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)

    def test_unsupported_device_type_skips(self):
        """Device type 'quorum' is not in supported_backing_volume_classes."""
        disk = self._make_disk_element()
        volume = self._make_volume(device_type="quorum",
                                   cache_install_path="/cache/path")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)

    def test_unrecognised_device_type_skips(self):
        """A completely unknown device type should be skipped."""
        disk = self._make_disk_element()
        volume = self._make_volume(device_type="unknown_type_xyz",
                                   cache_install_path="/cache/path")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)

    def test_supported_device_type_file(self):
        disk = self._make_disk_element()
        volume = self._make_volume(device_type="file",
                                   cache_install_path="/cache/path")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNotNone(cs)

    def test_no_device_type_still_adds(self):
        """When deviceType is None, validation is skipped and element is added."""
        disk = self._make_disk_element()
        volume = self._make_volume(device_type=None,
                                   cache_install_path="/cache/path")

        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNotNone(cs)

    def test_volume_without_cache_attr(self):
        """When volume has no cache attribute at all (getattr returns None)."""
        disk = self._make_disk_element()
        volume = mock.MagicMock(spec=[])  # empty spec, no attributes
        volume.cache = None  # explicit None

        # getattr(volume, 'cache', None) should return None
        add_caching_store(disk, volume)

        cs = disk.find("cachingStore")
        self.assertIsNone(cs)
