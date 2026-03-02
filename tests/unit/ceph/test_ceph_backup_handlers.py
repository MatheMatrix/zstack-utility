from __future__ import annotations

import importlib
import json
import sys
import pytest
from typing import cast
from unittest.mock import MagicMock, patch, mock_open


# ---------------------------------------------------------------------------
# Import the ceph backup storage module with lock passthrough
# ---------------------------------------------------------------------------
try:
    # Ensure lock decorators are passthroughs before importing
    import tests.conftest  # noqa: F401

    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))

    def _passthrough_lock(*_args, **_kwargs):
        if _args and callable(_args[0]) and len(_args) == 1 and not _kwargs:
            return _args[0]
        def _decorator(func):
            return func
        return _decorator

    setattr(lock_mod, "lock", _passthrough_lock)
    setattr(lock_mod, "file_lock", _passthrough_lock)

    module = importlib.import_module("cephbackupstorage.cephagent")
    module = importlib.reload(module)
except Exception as e:
    pytest.skip(f"Cannot import cephbackupstorage: {e}", allow_module_level=True)


def _make_req(body_dict=None):
    http = cast(object, importlib.import_module("zstacklib.utils.http"))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_agent():
    """Create CephAgent via __new__ to skip __init__ side effects."""
    agent = module.CephAgent.__new__(module.CephAgent)
    agent.cluster = MagicMock()
    agent.ioctx = {}
    agent.op_lock = __import__("threading").Lock()
    agent.upload_tasks = module.UploadTasks()
    return agent


def _mock_capacity(agent, total=10**12, avail=5 * 10**11):
    """Patch _get_capacity to return predictable values."""
    agent._get_capacity = MagicMock(return_value=(total, avail, []))
    ceph_mod = sys.modules["zstacklib.utils.ceph"]
    ceph_mod.get_ceph_manufacturer = MagicMock(return_value="generic")


# ---------------------------------------------------------------------------
# echo
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupEcho:
    def test_echo_returns_empty_string(self):
        agent = _make_agent()
        result = agent.echo(_make_req())
        assert result == ""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupInit:
    def test_init_creates_missing_pools(self):
        agent = _make_agent()
        _mock_capacity(agent)
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.call = MagicMock(return_value="existing-pool")
        ceph_mod = sys.modules["zstacklib.utils.ceph"]
        ceph_mod.get_fsid = MagicMock(return_value="fsid-001")
        ceph_mod.is_xsky = MagicMock(return_value=False)
        ceph_mod.is_sandstone = MagicMock(return_value=False)

        result = agent.init(_make_req({
            "pools": [
                {"name": "existing-pool", "predefined": False},
                {"name": "new-pool", "predefined": False},
            ]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["fsid"] == "fsid-001"
        # existing-pool should NOT trigger create, new-pool should
        create_calls = [c for c in shell_mod.call.call_args_list
                        if "osd pool create" in str(c)]
        assert len(create_calls) == 1
        assert "new-pool" in str(create_calls[0])

    def test_init_raises_if_predefined_pool_missing(self):
        agent = _make_agent()
        _mock_capacity(agent)
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.call = MagicMock(return_value="other-pool")

        result = agent.init(_make_req({
            "pools": [{"name": "missing-pool", "predefined": True}]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "cannot find pool" in rsp["error"]


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupConnect:
    def test_connect_reconnects_and_returns_capacity(self):
        agent = _make_agent()
        _mock_capacity(agent)
        agent.reconnect_cluster = MagicMock()

        result = agent.connect(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["totalCapacity"] == 10**12
        assert rsp["availableCapacity"] == 5 * 10**11
        agent.reconnect_cluster.assert_called_once()


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupPing:
    def test_ping_success_when_mon_addr_found(self):
        agent = _make_agent()
        module.bash_o = MagicMock(return_value=json.dumps({
            "mons": [{"addr": "10.0.0.1:6789/0"}]
        }))

        mock_shell_cmd = MagicMock()
        mock_shell_cmd.return_code = 0
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd = MagicMock(return_value=mock_shell_cmd)
        shell_mod.run = MagicMock()

        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.write_uuids = MagicMock()

        result = agent.ping(_make_req({
            "monAddr": "10.0.0.1",
            "monUuid": "mon-uuid-001",
            "testImagePath": "pool1/test-obj",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True

    def test_ping_fails_when_mon_addr_changed(self):
        agent = _make_agent()
        module.bash_o = MagicMock(return_value=json.dumps({
            "mons": [{"addr": "10.0.0.2:6789/0"}]
        }))

        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.write_uuids = MagicMock()

        result = agent.ping(_make_req({
            "monAddr": "10.0.0.1",
            "monUuid": "mon-uuid-001",
            "testImagePath": "pool1/test-obj",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert rsp["failure"] == "MonAddrChanged"

    def test_ping_fails_when_rados_write_fails(self):
        agent = _make_agent()
        module.bash_o = MagicMock(return_value=json.dumps({
            "mons": [{"addr": "10.0.0.1:6789/0"}]
        }))

        mock_shell_cmd = MagicMock()
        mock_shell_cmd.return_code = 1
        mock_shell_cmd.stderr = "write error"
        mock_shell_cmd.stdout = ""
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.ShellCmd = MagicMock(return_value=mock_shell_cmd)

        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.write_uuids = MagicMock()

        result = agent.ping(_make_req({
            "monAddr": "10.0.0.1",
            "monUuid": "mon-uuid-001",
            "testImagePath": "pool1/test-obj",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert rsp["failure"] == "UnableToCreateFile"


# ---------------------------------------------------------------------------
# get_image_size
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupGetImageSize:
    def test_get_image_size_returns_size(self):
        agent = _make_agent()
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.call = MagicMock(return_value='{"size": 1073741824}')

        result = agent.get_image_size(_make_req({
            "installPath": "ceph://pool1/image-001"
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["size"] == 1073741824


# ---------------------------------------------------------------------------
# get_local_file_size
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupGetLocalFileSize:
    def test_get_local_file_size_returns_size(self):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_local_file_size = MagicMock(return_value=2147483648)

        result = agent.get_local_file_size(_make_req({"path": "/tmp/test.img"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["size"] == 2147483648


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupDelete:
    def test_delete_removes_image(self):
        agent = _make_agent()
        _mock_capacity(agent)
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.wait_callback_success = MagicMock()
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.check_run = MagicMock()

        mock_ioctx = MagicMock()
        agent.get_ioctx = MagicMock(return_value=mock_ioctx)

        result = agent.delete(_make_req({
            "installPath": "ceph://pool1/image-001"
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        linux_mod.wait_callback_success.assert_called_once()
        mock_ioctx.remove_object.assert_called_once_with("image-001-export")


# ---------------------------------------------------------------------------
# get_facts
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupGetFacts:
    def test_get_facts_returns_fsid_and_mon_addr(self):
        agent = _make_agent()
        bash_mod = sys.modules["zstacklib.utils.bash"]
        bash_mod.bash_o = MagicMock(return_value='{"mons":[]}')
        ceph_mod = sys.modules["zstacklib.utils.ceph"]
        ceph_mod.get_fsid = MagicMock(return_value="fsid-002")
        ceph_mod.get_mon_addr = MagicMock(return_value="10.0.0.1:6789")

        result = agent.get_facts(_make_req({"monUuid": "mon-001"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["fsid"] == "fsid-002"


# ---------------------------------------------------------------------------
# check_pool
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupCheckPool:
    def test_check_pool_passes_when_pools_exist(self):
        agent = _make_agent()
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.call = MagicMock(return_value="pool1\npool2\n")

        result = agent.check_pool(_make_req({
            "pools": [{"name": "pool1"}, {"name": "pool2"}]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True

    def test_check_pool_fails_when_pool_missing(self):
        agent = _make_agent()
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.call = MagicMock(return_value="pool1\n")

        result = agent.check_pool(_make_req({
            "pools": [{"name": "pool1"}, {"name": "missing-pool"}]
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "cannot find pool" in rsp["error"]


# ---------------------------------------------------------------------------
# add_export_token
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupAddExportToken:
    def test_add_export_token_writes_to_rados(self):
        agent = _make_agent()
        _mock_capacity(agent)
        mock_ioctx = MagicMock()
        agent.get_ioctx = MagicMock(return_value=mock_ioctx)

        result = agent.add_export_token(_make_req({
            "installPath": "ceph://pool1/image-001",
            "token": "secret-token-123",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_ioctx.write_full.assert_called_once_with("image-001-export", "secret-token-123")


# ---------------------------------------------------------------------------
# remove_export_token
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupRemoveExportToken:
    def test_remove_export_token_removes_from_rados(self):
        agent = _make_agent()
        _mock_capacity(agent)
        mock_ioctx = MagicMock()
        agent.get_ioctx = MagicMock(return_value=mock_ioctx)

        result = agent.remove_export_token(_make_req({
            "installPath": "ceph://pool1/image-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_ioctx.remove_object.assert_called_once_with("image-001-export")

    def test_remove_export_token_ignores_not_found(self):
        agent = _make_agent()
        _mock_capacity(agent)
        mock_ioctx = MagicMock()
        rados_mod = sys.modules["rados"]
        mock_ioctx.remove_object.side_effect = rados_mod.ObjectNotFound
        agent.get_ioctx = MagicMock(return_value=mock_ioctx)

        result = agent.remove_export_token(_make_req({
            "installPath": "ceph://pool1/image-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# check_image_metadata_file_exist
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupCheckImageMetadataFileExist:
    def test_metadata_file_exists(self):
        agent = _make_agent()
        module.bash_ro = MagicMock(return_value=(0, "stat info"))

        result = agent.check_image_metadata_file_exist(_make_req({
            "poolName": "bak-t-uuid001"
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["exist"] is True
        assert rsp["backupStorageMetaFileName"] == "bs_ceph_info.json"

    def test_metadata_file_not_exists(self):
        agent = _make_agent()
        module.bash_ro = MagicMock(return_value=(2, "not found"))

        result = agent.check_image_metadata_file_exist(_make_req({
            "poolName": "bak-t-uuid002"
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["exist"] is False


# ---------------------------------------------------------------------------
# dump_image_metadata_to_file
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupDumpImageMetadataToFile:
    def test_dump_single_metadata_write_mode(self):
        agent = _make_agent()
        bash_mod = sys.modules["zstacklib.utils.bash"]
        bash_mod.bash_r = MagicMock(return_value=0)
        bash_mod.bash_ro = MagicMock(return_value=(0, ""))
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.rm_file_force = MagicMock()

        # Mock put_metadata_file to avoid real rados
        agent.put_metadata_file = MagicMock()

        with patch("builtins.open", mock_open()) as mock_file:
            result = agent.dump_image_metadata_to_file(_make_req({
                "poolName": "bak-t-uuid001",
                "imageMetaData": '{"uuid":"img-001","name":"test"}',
                "dumpAllMetaData": True,
            }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_file.assert_called_with("/tmp/bs_ceph_info.json", "w")


# ---------------------------------------------------------------------------
# delete_image_metadata_from_file
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupDeleteImageMetadataFromFile:
    def test_delete_metadata_returns_ret_code(self):
        agent = _make_agent()
        module.bash_ro = MagicMock(return_value=(0, ""))
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.rm_file_force = MagicMock()

        # Mock get/put metadata
        agent.get_metadata_file = MagicMock()
        agent.put_metadata_file = MagicMock()

        result = agent.delete_image_metadata_from_file(_make_req({
            "imageUuid": "img-001",
            "poolName": "bak-t-uuid001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["ret"] == 0


# ---------------------------------------------------------------------------
# migrate_image
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupMigrateImage:
    def test_migrate_success(self):
        agent = _make_agent()
        _mock_capacity(agent)
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.run = MagicMock(return_value=0)
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.build_sshpass_cmd = MagicMock(return_value=("sshpass_cmd", "/tmp/file"))
        linux_mod.rm_file_force = MagicMock()
        linux_mod.sshpass_call = MagicMock(return_value="md5hash")
        agent._read_file_content = MagicMock(return_value="md5hash")

        result = agent.migrate_image(_make_req({
            "imageUuid": "img-001",
            "imageSize": 1073741824,
            "srcInstallPath": "ceph://pool1/src-img",
            "dstInstallPath": "ceph://pool2/dst-img",
            "dstMonHostname": "10.0.0.2",
            "dstMonSshUsername": "root",
            "dstMonSshPassword": "password",
            "dstMonSshPort": 22,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True

    def test_migrate_failure(self):
        agent = _make_agent()
        _mock_capacity(agent)
        shell_mod = sys.modules["zstacklib.utils.shell"]
        shell_mod.run = MagicMock(return_value=1)
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.build_sshpass_cmd = MagicMock(return_value=("sshpass_cmd", "/tmp/file"))
        linux_mod.rm_file_force = MagicMock()

        result = agent.migrate_image(_make_req({
            "imageUuid": "img-001",
            "imageSize": 1073741824,
            "srcInstallPath": "ceph://pool1/src-img",
            "dstInstallPath": "ceph://pool2/dst-img",
            "dstMonHostname": "10.0.0.2",
            "dstMonSshUsername": "root",
            "dstMonSshPassword": "password",
            "dstMonSshPort": 22,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "Failed to migrate" in rsp["error"]


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupCancel:
    def test_cancel_delegates_to_plugin(self):
        agent = _make_agent()
        plugin_mod = sys.modules["zstacklib.utils.plugin"]
        mock_rsp = MagicMock()
        mock_rsp.__dict__ = {"success": True, "error": ""}
        plugin_mod.cancel_job = MagicMock(return_value=mock_rsp)

        result = agent.cancel(_make_req({"cancellationApiId": "api-123"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# get_upload_param (static method)
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupGetUploadParam:
    def test_valid_headers_parsed(self):
        headers = {
            "X-IMAGE-UUID": "img-uuid-001",
            "X-IMAGE-SIZE": "1073741824",
            "X-SLICE-OFFSET": "0",
            "X-SLICE-SIZE": "4194304",
            "X-SLICE-INDEX": "0",
            "X-SLICE-HASH": "abc123",
            "X-HASH-ALGORITHM": "md5",
        }
        param = module.CephAgent.get_upload_param(headers)
        assert param.image_uuid == "img-uuid-001"
        assert param.image_size == 1073741824
        assert param.slice_offset == 0
        assert param.slice_size == 4194304
        assert param.slice_hash == "abc123"

    def test_invalid_offset_raises(self):
        headers = {
            "X-IMAGE-UUID": "img-uuid-001",
            "X-IMAGE-SIZE": "1024",
            "X-SLICE-OFFSET": "2048",  # >= image_size
        }
        with pytest.raises(Exception, match="invalid slice offset"):
            module.CephAgent.get_upload_param(headers)

    def test_negative_size_raises(self):
        headers = {
            "X-IMAGE-UUID": "img-uuid-001",
            "X-IMAGE-SIZE": "-1",
        }
        with pytest.raises(Exception, match="invalid header"):
            module.CephAgent.get_upload_param(headers)


# ---------------------------------------------------------------------------
# get_upload_progress
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupGetUploadProgress:
    def test_upload_progress_for_running_task(self):
        agent = _make_agent()
        # Create a mock task
        task = MagicMock()
        task.completed = False
        task.installPath = "ceph://pool1/image-001"
        task.expectedSize = 1073741824
        task.checked_download_size.return_value = 536870912
        task.lastOpTime = 1000
        task.image_format = "raw"
        task.lastError = None
        task.slice_uploaded = MagicMock()
        task.slice_uploaded.__len__ = MagicMock(return_value=536870912)
        agent.upload_tasks.get_task = MagicMock(return_value=task)

        result = agent.get_upload_progress(_make_req({"imageUuid": "img-uuid-001"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["completed"] is False
        assert rsp["installPath"] == "ceph://pool1/image-001"

    def test_upload_progress_task_not_found(self):
        agent = _make_agent()
        agent.upload_tasks.get_task = MagicMock(return_value=None)

        result = agent.get_upload_progress(_make_req({"imageUuid": "nonexistent"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "not found" in rsp["error"]


# ---------------------------------------------------------------------------
# _normalize_install_path / _parse_install_path
# ---------------------------------------------------------------------------
@pytest.mark.ceph
class TestCephBackupHelpers:
    def test_normalize_install_path(self):
        agent = _make_agent()
        assert agent._normalize_install_path("ceph://pool1/image-001") == "pool1/image-001"

    def test_parse_install_path(self):
        agent = _make_agent()
        pool, image = agent._parse_install_path("ceph://pool1/image-001")
        assert pool == "pool1"
        assert image == "image-001"
