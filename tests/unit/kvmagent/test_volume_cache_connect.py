# -*- coding: utf-8 -*-
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


_REPO_ROOT = Path(__file__).resolve().parents[3]
_KVMAGENT_ROOT = str(_REPO_ROOT / "kvmagent")
if _KVMAGENT_ROOT not in sys.path:
    sys.path.insert(0, _KVMAGENT_ROOT)


def _module(name):
    return types.ModuleType(name)


def _package(name, path):
    module = _module(name)
    module.__path__ = [str(path)]
    module.__package__ = name
    return module


def _install_import_fakes():
    kvmagent_module = _module("kvmagent.kvmagent")

    class AgentCommand(object):
        pass

    class AgentResponse(object):
        pass

    class KvmAgent(object):
        pass

    kvmagent_module.AgentCommand = AgentCommand
    kvmagent_module.AgentResponse = AgentResponse
    kvmagent_module.KvmAgent = KvmAgent
    kvmagent_module.replyerror = lambda func: func
    kvmagent_module.get_http_server = lambda: MagicMock()

    zstacklib = _package("zstacklib", _REPO_ROOT / "zstacklib" / "zstacklib")
    utils = _package("zstacklib.utils", _REPO_ROOT / "zstacklib" / "zstacklib" / "utils")
    zstacklib.utils = utils

    for name in ["linux", "lvm", "shell", "plugin"]:
        child = _module("zstacklib.utils.%s" % name)
        setattr(utils, name, child)

    class TaskDaemon(object):
        def __init__(self, *args, **kwargs):
            pass

    utils.plugin.TaskDaemon = TaskDaemon

    log = _module("zstacklib.utils.log")
    log.get_logger = lambda name: MagicMock()
    utils.log = log

    http = _module("zstacklib.utils.http")
    http.REQUEST_BODY = "body"
    http.REQUEST_HEADER = "header"
    utils.http = http

    rollback = _module("zstacklib.utils.rollback")
    rollback.rollback = lambda func: func
    rollback.rollbackable = lambda func: func

    jsonobject = _module("zstacklib.utils.jsonobject")

    class JsonObject(object):
        def to_dict(self):
            return dict(self.__dict__)

    jsonobject.JsonObject = JsonObject
    jsonobject.loads = lambda raw: JsonObject()
    jsonobject.dumps = lambda obj: "{}"
    utils.jsonobject = jsonobject

    qemu_img = _module("kvmagent.plugins.volume_cache.command_wrapper.qemu_img")
    qemu_img.BackingVolume = object
    qemu_img.BackingVolumeDeviceType = object
    qemu_img.QemuImgCommandWrapper = object
    qemu_img.supported_backing_volume_classes = []

    return {
        "kvmagent.kvmagent": kvmagent_module,
        "zstacklib": zstacklib,
        "zstacklib.utils": utils,
        "zstacklib.utils.linux": utils.linux,
        "zstacklib.utils.lvm": utils.lvm,
        "zstacklib.utils.shell": utils.shell,
        "zstacklib.utils.plugin": utils.plugin,
        "zstacklib.utils.log": log,
        "zstacklib.utils.http": http,
        "zstacklib.utils.rollback": rollback,
        "zstacklib.utils.jsonobject": jsonobject,
        "kvmagent.plugins.volume_cache.command_wrapper.qemu_img": qemu_img,
    }


with patch.dict(sys.modules, _install_import_fakes()):
    from kvmagent.plugins import volume_cache_plugin
    from kvmagent.plugins.volume_cache.command_wrapper.exceptions import PoolOperationError


class _FakeFileSystem(object):
    block_device = "/dev/vlvc/pool"


class TestVolumeCachePoolConnect(unittest.TestCase):
    def _loaded_pool(self, filesystem_healthy):
        pool = volume_cache_plugin.PoolProcessor("pool-uuid", "/cache/pool")
        check_filesystem = MagicMock(return_value=filesystem_healthy)
        patches = [
            patch.object(volume_cache_plugin.FileSystemCommandWrapper, "partprobe", MagicMock()),
            patch.object(pool, "_PoolProcessor__load_pvs", MagicMock(return_value=["/dev/sdb"])),
            patch.object(pool, "_PoolProcessor__load_vg", MagicMock(return_value=object())),
            patch.object(pool, "_PoolProcessor__load_lv", MagicMock(return_value=object())),
            patch.object(pool, "_PoolProcessor__load_filesystem", MagicMock(return_value=_FakeFileSystem())),
            patch.object(pool, "_PoolProcessor__load_mount_point", MagicMock(return_value=object())),
            patch.object(volume_cache_plugin.FileSystemCommandWrapper, "check_filesystem", check_filesystem),
        ]
        for patcher in patches:
            self.addCleanup(patcher.stop)
            patcher.start()
        return pool, check_filesystem

    def test_connect_pool_checks_filesystem_before_success(self):
        pool, check_filesystem = self._loaded_pool(True)

        pool.connect_pool()

        check_filesystem.assert_called_once_with("/cache/pool", "/cache/pool/.heartbeat")
        self.assertTrue(pool.is_initialized)

    def test_connect_pool_fails_when_filesystem_check_is_unhealthy(self):
        pool, check_filesystem = self._loaded_pool(False)

        with self.assertRaises(PoolOperationError) as error:
            pool.connect_pool()

        check_filesystem.assert_called_once_with("/cache/pool", "/cache/pool/.heartbeat")
        self.assertIn("Failed to connect pool pool-uuid on mount path /cache/pool", str(error.exception))


if __name__ == "__main__":
    unittest.main()
