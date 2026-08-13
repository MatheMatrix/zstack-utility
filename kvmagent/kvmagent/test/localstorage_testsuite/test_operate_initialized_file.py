from kvmagent.test.utils import localstorage_utils,pytest_utils
from kvmagent.test.utils.stub import *
from kvmagent.plugins import localstorage
from zstacklib.test.utils import remote,misc
from zstacklib.utils import linux, jsonobject, bash
from unittest import TestCase
import os
import shutil
import tempfile
localstorage_utils.init_localstorage_plugin()

PKG_NAME = __name__

__ENV_SETUP__ = {
    'self': {}
}


## describe: case will manage by ztest
class TestLocalStoragePlugin(TestCase):

    @classmethod
    def setUpClass(cls):
        return

    def _register_local_storage_uri(self, path, handler):
        plugin = localstorage.LocalStoragePlugin()
        registered_handlers = {}

        class HttpServer(object):
            def register_async_uri(self, uri_path, uri_handler, *args, **kwargs):
                registered_handlers[uri_path] = uri_handler

        guarded_server = plugin._local_storage_guarded_http_server(HttpServer())
        guarded_server.register_async_uri(path, handler)
        return registered_handlers[path]

    @staticmethod
    def _succeed(req):
        rsp = localstorage.AgentResponse()
        rsp.success = True
        return jsonobject.dumps(rsp)

    def test_new_local_storage_write_uri_requires_initialized_file_when_registered(self):
        storage_path = tempfile.mkdtemp()
        try:
            handler = self._register_local_storage_uri('/localstorage/new/write', self._succeed)
            rsp = jsonobject.loads(handler(misc.make_a_request({
                'uuid': 'test-local-ps',
                'storagePath': storage_path,
            })))

            self.assertEqual(False, rsp.success, rsp.error)
            self.assertIn('/localstorage/new/write', rsp.error)
            self.assertIn('test-local-ps-initialized-file', rsp.error)
        finally:
            shutil.rmtree(storage_path)

    def test_new_local_storage_write_uri_allows_initialized_file_when_registered(self):
        storage_path = tempfile.mkdtemp()
        try:
            ps_uuid = 'test-local-ps'
            open(os.path.join(storage_path, '%s-initialized-file' % ps_uuid), 'w').close()

            handler = self._register_local_storage_uri('/localstorage/new/write', self._succeed)
            rsp = jsonobject.loads(handler(misc.make_a_request({
                'uuid': ps_uuid,
                'storagePath': storage_path,
            })))

            self.assertEqual(True, rsp.success, rsp.error)
        finally:
            shutil.rmtree(storage_path)

    def test_local_storage_read_uri_is_not_guarded_when_registered(self):
        handler = self._register_local_storage_uri(
            localstorage.LocalStoragePlugin.GET_VOLUME_SIZE,
            self._succeed
        )
        rsp = jsonobject.loads(handler(misc.make_a_request({})))

        self.assertEqual(True, rsp.success, rsp.error)

    def test_guarded_write_uri_requires_storage_identity(self):
        plugin = localstorage.LocalStoragePlugin()
        handler = plugin._with_initialized_file_guard('/localstorage/new/write', self._succeed)
        rsp = jsonobject.loads(handler(misc.make_a_request({})))

        self.assertEqual(False, rsp.success, rsp.error)
        self.assertIn('requires primaryStorageUuid/uuid and storagePath', rsp.error)

    def test_localstorage_init_does_not_create_initialized_file(self):
        storage_path = tempfile.mkdtemp()
        try:
            initialized_file = os.path.join(storage_path, 'test-local-ps-initialized-file')
            rsp = localstorage_utils.localstorage_init(storage_path, initialized_file)

            self.assertGreater(rsp.totalCapacity, 0, rsp.error)
            self.assertFalse(os.path.exists(initialized_file), '[check] init created initialized file unexpectedly')
        finally:
            shutil.rmtree(storage_path)

    @pytest_utils.ztest_decorater
    def test_create_initialized_file(self):
        rsp = localstorage_utils.localstorage_init(
            "/local_ps"
        )
        self.assertGreater(rsp.totalCapacity, 0, rsp.error)
        self.assertGreater(rsp.availableCapacity, 0, rsp.error)

        rsp = localstorage_utils.create_initialized_file(
            filePath = "/local_ps/test",
            storagePath = "/local_ps"
        )

        self.assertEqual(True, os.path.exists("/local_ps/test"), "[check] cannot create  initialized file in host")

        rsp = localstorage_utils.check_initialized_file(
            filePath="/local_ps/test",
            storagePath="/local_ps"
        )

        self.assertGreater(rsp.totalCapacity, 0, rsp.error)
        self.assertGreater(rsp.availableCapacity, 0, rsp.error)
        bash.bash_ro("rm -rf /local_ps")

    @pytest_utils.ztest_decorater
    def test_create_empty_volume_requires_initialized_file(self):
        storage_path = "/local_ps"
        ps_uuid = "test-local-ps"
        marker_path = "%s/%s-initialized-file" % (storage_path, ps_uuid)
        missing_target = "%s/missing-marker.qcow2" % storage_path
        success_target = "%s/marker-present.qcow2" % storage_path

        try:
            rsp = localstorage_utils.localstorage_init(storage_path)
            self.assertGreater(rsp.totalCapacity, 0, rsp.error)
            self.assertGreater(rsp.availableCapacity, 0, rsp.error)

            rsp = localstorage_utils.create_empty_volume(
                installUrl=missing_target,
                size=1048576,
                storagePath=storage_path,
                uuid=ps_uuid,
                primaryStorageUuid=ps_uuid
            )
            self.assertEqual(False, rsp.success, rsp.error)
            self.assertIn(marker_path, rsp.error)
            self.assertFalse(os.path.exists(missing_target), "[check] volume was created without initialized file")

            bash.bash_ro("touch %s" % marker_path)
            rsp = localstorage_utils.create_empty_volume(
                installUrl=success_target,
                size=1048576,
                storagePath=storage_path,
                uuid=ps_uuid,
                primaryStorageUuid=ps_uuid
            )
            self.assertNotEqual(False, rsp.success, rsp.error)
            self.assertTrue(os.path.exists(success_target), "[check] cannot find volume after initialized file exists")
        finally:
            bash.bash_ro("rm -rf %s" % storage_path)

    @pytest_utils.ztest_decorater
    def test_create_root_volume_checks_initialized_file_before_template(self):
        storage_path = "/local_ps"
        ps_uuid = "test-local-ps"
        marker_path = "%s/%s-initialized-file" % (storage_path, ps_uuid)
        target = "%s/root/test.qcow2" % storage_path

        try:
            rsp = localstorage_utils.localstorage_init(storage_path)
            self.assertGreater(rsp.totalCapacity, 0, rsp.error)
            self.assertGreater(rsp.availableCapacity, 0, rsp.error)

            rsp = localstorage_utils.create_root_volume_from_template(
                templatePathInCache="/not-exist/template.qcow2",
                installUrl=target,
                storagePath=storage_path,
                uuid=ps_uuid,
                primaryStorageUuid=ps_uuid
            )
            self.assertEqual(False, rsp.success, rsp.error)
            self.assertIn(marker_path, rsp.error)
            self.assertFalse(os.path.exists(target), "[check] root volume was created without initialized file")
        finally:
            bash.bash_ro("rm -rf %s" % storage_path)
