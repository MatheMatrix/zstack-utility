from kvmagent.test.utils import localstorage_utils,pytest_utils
from kvmagent.test.utils.stub import *
from zstacklib.test.utils import remote,misc
from zstacklib.utils import linux, jsonobject, bash
from unittest import TestCase
import os
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
