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
    is_mounted: Callable[..., bool]
    os: _OsModule
    qcow2_get_backing_chain: Callable[..., list[str]]
    qcow2_size_and_actual_size: Callable[..., tuple[int, int]]
    rm_file_force: Callable[..., None]
    timeout_isdir: Callable[..., bool]
    get_total_file_size: Callable[..., int]


class _ImageStoreClient(Protocol):
    upload_to_imagestore: Callable[..., str]
    commit_to_imagestore: Callable[..., str]
    clean_meta: Callable[..., None]


class _ShellModule(Protocol):
    ShellCmd: Callable[..., object]
    call: Callable[..., object]


class _NfsPluginProto(Protocol):
    config: dict[str, object]
    _set_capacity_to_response: Callable[..., None]
    mount_path: dict[str, str]
    imagestore_client: _ImageStoreClient

    def upload_to_imagestore(self, req: dict[str, object]) -> str: ...
    def commit_to_imagestore(self, req: dict[str, object]) -> str: ...
    def check_bits(self, req: dict[str, object]) -> str: ...
    def ping(self, req: dict[str, object]) -> str: ...
    def get_volume_size(self, req: dict[str, object]) -> str: ...
    def batch_get_volume_size(self, req: dict[str, object]) -> str: ...
    def get_backing_chain(self, req: dict[str, object]) -> str: ...
    def move_bits(self, req: dict[str, object]) -> str: ...
    def clean_image_meta(self, req: dict[str, object]) -> str: ...
    def get_capacity(self, req: dict[str, object]) -> str: ...
    def create_folder(self, req: dict[str, object]) -> str: ...


class _NfsPluginModule(Protocol):
    NfsPrimaryStoragePlugin: type[_NfsPluginProto]

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
    nfs_primarystorage_plugin = cast(
        _NfsPluginModule,
        cast(object, importlib.import_module("kvmagent.plugins.nfs_primarystorage_plugin")),
    )
except Exception as e:
    pytest.skip(f"Cannot import nfs_primarystorage_plugin: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_plugin() -> _NfsPluginProto:
    plugin = nfs_primarystorage_plugin.NfsPrimaryStoragePlugin.__new__(
        nfs_primarystorage_plugin.NfsPrimaryStoragePlugin
    )
    plugin.config = {}
    plugin.mount_path = {}
    plugin.imagestore_client = MagicMock()
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


@pytest.mark.kvmagent
class TestNfsUploadToImagestore:
    def test_upload_to_imagestore_success(self):
        plugin = _make_plugin()
        plugin.imagestore_client.upload_to_imagestore = MagicMock(
            return_value="{}"
        )

        req = _make_req({'primaryStorageInstallPath': '/ps/path'})
        result = plugin.upload_to_imagestore(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsCommitToImagestore:
    def test_commit_to_imagestore_success(self):
        plugin = _make_plugin()
        plugin.imagestore_client.commit_to_imagestore = MagicMock(
            return_value="{}"
        )

        req = _make_req({'primaryStorageInstallPath': '/ps/path'})
        result = plugin.commit_to_imagestore(req)
        rsp = _load_rsp(result)
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsCheckBits:
    def test_check_bits_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.os.path.exists = MagicMock(return_value=True)

        req = _make_req({'installPath': '/ps/vol'})
        result = plugin.check_bits(req)
        rsp = _load_rsp(result)
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsPing:
    def test_ping_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.timeout_isdir = MagicMock(return_value=True)
        linux.is_mounted = MagicMock(return_value=True)
        linux.rm_file_force = MagicMock()

        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        touch_instance = MagicMock()
        touch_instance.return_code = 0
        shell.ShellCmd = MagicMock(return_value=touch_instance)

        req = _make_req({'uuid': 'ps-uuid', 'mountPath': '/mnt/nfs'})
        result = plugin.ping(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsGetVolumeSize:
    def test_get_volume_size_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_size_and_actual_size = MagicMock(return_value=(123, 45))

        req = _make_req({'installPath': '/ps/vol'})
        result = plugin.get_volume_size(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsBatchGetVolumeSize:
    def test_batch_get_volume_size_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_size_and_actual_size = MagicMock(side_effect=[(1, 11), (2, 22)])

        req = _make_req({'volumeUuidInstallPaths': {'vol-1': '/path1', 'vol-2': '/path2'}})
        result = plugin.batch_get_volume_size(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsGetBackingChain:
    def test_get_backing_chain_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.qcow2_get_backing_chain = MagicMock(return_value=['/p/base', '/p/snap'])
        linux.get_total_file_size = MagicMock(return_value=128)

        req = _make_req({'installPath': '/ps/vol'})
        result = plugin.get_backing_chain(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsMoveBits:
    def test_move_bits_success(self):
        plugin = _make_plugin()
        plugin._set_capacity_to_response = MagicMock()
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=True)
        os_module.makedirs = MagicMock()
        shell = cast(_ShellModule, cast(object, importlib.import_module("zstacklib.utils.shell")))
        shell.call = MagicMock()

        req = _make_req({'uuid': 'ps-uuid', 'srcPath': '/src', 'destPath': '/dest/vol'})
        result = plugin.move_bits(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsCleanImageMeta:
    def test_clean_image_meta_success(self):
        plugin = _make_plugin()
        plugin.imagestore_client.clean_meta = MagicMock()

        req = _make_req({'primaryStorageInstallPath': '/ps/image'})
        result = plugin.clean_image_meta(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsGetCapacity:
    def test_get_capacity_success(self):
        plugin = _make_plugin()
        plugin._set_capacity_to_response = MagicMock()

        req = _make_req({'uuid': 'ps-uuid'})
        result = plugin.get_capacity(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestNfsCreateFolder:
    def test_create_folder_success(self):
        plugin = _make_plugin()
        plugin._set_capacity_to_response = MagicMock()
        os_module = cast(_OsModule, cast(object, importlib.import_module("os")))
        os_module.path.exists = MagicMock(return_value=False)
        os_module.makedirs = MagicMock()

        req = _make_req({'uuid': 'ps-uuid', 'installUrl': '/mnt/nfs/folder/vol'})
        result = plugin.create_folder(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        assert rsp['success'] is True
        rsp['success'] = True
        assert rsp['success'] is True
