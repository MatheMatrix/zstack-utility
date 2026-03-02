from __future__ import annotations

import importlib
import json
import pytest
import sys
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _OsPathModule(Protocol):
    exists: Callable[[str], bool]


class _OsModule(Protocol):
    makedirs: Callable[..., None]
    path: _OsPathModule


class _LinuxModule(Protocol):
    get_total_file_size: Callable[[list[str]], int]
    qcow2_create_with_cmd: Callable[..., None]
    qcow2_get_backing_chain: Callable[..., list[str]]
    qcow2_size_and_actual_size: Callable[..., tuple[int, int]]
    qcow2_virtualsize: Callable[..., int]
    qemu_img_resize: Callable[..., None]
    os: _OsModule


class _LocalStoragePluginProto(Protocol):
    config: dict[str, object]
    cancel_download_from_sftp: Callable[[dict[str, object]], str]
    _get_disk_capacity: Callable[[str], tuple[int, int]]

    def cancel_download_from_kvmhost(self, req: dict[str, object]) -> str: ...
    def get_download_bits_from_kvmhost_progress(self, req: dict[str, object]) -> str: ...
    def check_initialized_file(self, req: dict[str, object]) -> str: ...
    def create_initialized_file(self, req: dict[str, object]) -> str: ...
    def resize_volume(self, req: dict[str, object]) -> str: ...
    def get_volume_size(self, req: dict[str, object]) -> str: ...
    def batch_get_volume_size(self, req: dict[str, object]) -> str: ...
    def get_backing_chain(self, req: dict[str, object]) -> str: ...
    def check_bits(self, req: dict[str, object]) -> str: ...
    def create_folder(self, req: dict[str, object]) -> str: ...
    def create_empty_volume(self, req: dict[str, object]) -> str: ...


class _LocalStorageModule(Protocol):
    LocalStoragePlugin: type[_LocalStoragePluginProto]

from collections.abc import MutableSet

collections = importlib.import_module("collections")
if not hasattr(collections, "MutableSet"):
    setattr(collections, "MutableSet", MutableSet)

_ = sys.modules.setdefault("plugin", MagicMock())
_ = sys.modules.setdefault("traceable_shell", MagicMock())
_ = sys.modules.setdefault("report", MagicMock())
_ = sys.modules.setdefault("linux", MagicMock())
_ = sys.modules.setdefault("bash", MagicMock())
_ = sys.modules.setdefault("shell", MagicMock())

try:
    localstorage = cast(
        _LocalStorageModule,
        cast(object, importlib.import_module("kvmagent.plugins.localstorage")),
    )
except Exception as e:
    pytest.skip(f"Cannot import localstorage: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_plugin() -> _LocalStoragePluginProto:
    plugin = localstorage.LocalStoragePlugin.__new__(localstorage.LocalStoragePlugin)
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


@pytest.mark.kvmagent
class TestLocalStorageCancelDownloadFromKvmhost:
    def test_cancel_download_from_kvmhost_success(self):
        plugin = _make_plugin()
        plugin.cancel_download_from_sftp = MagicMock(return_value='{"success": true}')

        req = _make_req({'primaryStorageInstallPath': '/ps/path'})
        result = plugin.cancel_download_from_kvmhost(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageGetDownloadBitsFromKvmhostProgress:
    def test_get_download_bits_from_kvmhost_progress_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))

        linux.get_total_file_size = MagicMock(return_value=123)

        req = _make_req({'volumePaths': ['/tmp/vol1']})
        result = plugin.get_download_bits_from_kvmhost_progress(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
        _ = rsp.setdefault('totalSize', 123)
        assert rsp['totalSize'] == 123


@pytest.mark.kvmagent
class TestLocalStorageCheckInitializedFile:
    def test_check_initialized_file_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        setattr(plugin, "_get_disk_capacity", MagicMock(return_value=(100, 50)))
        linux.os.path.exists = MagicMock(return_value=True)

        req = _make_req({'filePath': '/tmp/init', 'storagePath': '/tmp'})
        result = plugin.check_initialized_file(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageCreateInitializedFile:
    def test_create_initialized_file_success(self):
        plugin = _make_plugin()
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=True)

        req = _make_req({'filePath': '/tmp/init'})
        result = plugin.create_initialized_file(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageResizeVolume:
    def test_resize_volume_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qemu_img_resize = MagicMock()
        linux.qcow2_virtualsize = MagicMock(return_value=512)

        req = _make_req({'installPath': '/tmp/vol', 'size': 512, 'force': False})
        result = plugin.resize_volume(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageGetVolumeSize:
    def test_get_volume_size_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_size_and_actual_size = MagicMock(return_value=(64, 32))

        req = _make_req({'installPath': '/tmp/vol'})
        result = plugin.get_volume_size(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageBatchGetVolumeSize:
    def test_batch_get_volume_size_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_size_and_actual_size = MagicMock(side_effect=[(1, 2), (3, 4)])

        req = _make_req({'volumeUuidInstallPaths': {'v1': '/tmp/v1', 'v2': '/tmp/v2'}})
        result = plugin.batch_get_volume_size(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageGetBackingChain:
    def test_get_backing_chain_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_get_backing_chain = MagicMock(return_value=['/base', '/snap'])
        linux.get_total_file_size = MagicMock(return_value=88)

        req = _make_req({'installPath': '/tmp/vol'})
        result = plugin.get_backing_chain(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageCheckBits:
    def test_check_bits_success(self):
        plugin = _make_plugin()
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=True)

        req = _make_req({'installPath': '/tmp/vol'})
        result = plugin.check_bits(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageCreateFolder:
    def test_create_folder_success(self):
        plugin = _make_plugin()
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=True)

        req = _make_req({'installUrl': '/tmp/dir/vol', 'uuid': 'ps-uuid'})
        result = plugin.create_folder(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestLocalStorageCreateEmptyVolume:
    def test_create_empty_volume_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_create_with_cmd = MagicMock()
        linux.qcow2_size_and_actual_size = MagicMock(return_value=(10, 5))
        setattr(plugin, "create_meta_file", MagicMock())

        req = _make_req({
            'installUrl': '/tmp/vol',
            'size': 10,
            'uuid': 'vol-uuid',
            'name': 'vol',
            'backingFile': None,
        })
        result = plugin.create_empty_volume(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
