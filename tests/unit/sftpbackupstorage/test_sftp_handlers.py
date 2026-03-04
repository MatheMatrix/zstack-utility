from __future__ import annotations

import importlib
import json
import os
import pytest
import sys
from typing import cast
from unittest.mock import MagicMock, patch, mock_open


try:
    from tests.conftest import _import_with_octal_fix

    _src_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "sftpbackupstorage", "sftpbackupstorage", "sftpbackupstorage.py",
    ))
    module = _import_with_octal_fix("sftpbackupstorage.sftpbackupstorage", _src_path)
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import sftpbackupstorage: {e}", allow_module_level=True)


def _make_req(body_dict=None):
    http = cast(object, importlib.import_module("zstacklib.utils.http"))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_agent():
    """Create SftpBackupStorageAgent via __new__ to skip __init__ side effects."""
    agent = module.SftpBackupStorageAgent.__new__(module.SftpBackupStorageAgent)
    agent.storage_path = "/test/storage"
    agent.uuid = "sftp-uuid-001"
    return agent


# ---------------------------------------------------------------------------
# echo
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpEcho:
    def test_echo_returns_empty_string(self):
        agent = _make_agent()
        result = agent.echo(_make_req())
        assert result == ""


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpPing:
    def test_ping_returns_uuid(self):
        agent = _make_agent()
        result = agent.ping(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["uuid"] == "sftp-uuid-001"

    def test_ping_returns_no_uuid_when_not_connected(self):
        agent = _make_agent()
        agent.uuid = None
        result = agent.ping(_make_req())
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert "uuid" not in rsp


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpConnect:
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=False)
    def test_connect_sets_storage_path_and_uuid(self, mock_isfile, mock_exists):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_total_disk_size = MagicMock(return_value=1000000000)
        linux_mod.get_used_disk_size = MagicMock(return_value=200000000)

        result = agent.connect(_make_req({
            "storagePath": "/data/sftp",
            "uuid": "sftp-uuid-002",
            "sendCommandUrl": "http://mn:8080",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["totalCapacity"] == 1000000000
        assert rsp["availableCapacity"] == 800000000
        assert agent.storage_path == "/data/sftp"
        assert agent.uuid == "sftp-uuid-002"

    @patch("os.path.isfile", return_value=True)
    def test_connect_raises_if_storage_path_is_file(self, mock_isfile):
        agent = _make_agent()
        result = agent.connect(_make_req({
            "storagePath": "/data/sftp",
            "uuid": "sftp-uuid-002",
            "sendCommandUrl": "http://mn:8080",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "is a file" in rsp["error"]


# ---------------------------------------------------------------------------
# get_image_size
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpGetImageSize:
    def test_get_image_size_returns_sizes(self):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.qcow2_size_and_actual_size = MagicMock(return_value=(1073741824, 536870912))

        result = agent.get_image_size(_make_req({"installPath": "/data/sftp/images/test.qcow2"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["size"] == 1073741824
        assert rsp["actualSize"] == 536870912


# ---------------------------------------------------------------------------
# get_local_file_size
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpGetLocalFileSize:
    def test_get_local_file_size_returns_size(self):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_local_file_size = MagicMock(return_value=2147483648)

        result = agent.get_local_file_size(_make_req({"path": "/data/sftp/images/test.raw"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["size"] == 2147483648


# ---------------------------------------------------------------------------
# delete_image
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpDeleteImage:
    @patch("shutil.rmtree")
    def test_delete_image_removes_directory(self, mock_rmtree):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_total_disk_size = MagicMock(return_value=1000000000)
        linux_mod.get_used_disk_size = MagicMock(return_value=100000000)

        result = agent.delete_image(_make_req({"installUrl": "/data/sftp/images/abc123/image.qcow2"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        mock_rmtree.assert_called_once_with("/data/sftp/images/abc123")


# ---------------------------------------------------------------------------
# get_sshkey
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpGetSshkey:
    @patch("os.path.exists", return_value=True)
    @patch("os.path.expanduser", return_value="/root/.ssh/id_rsa.sftp")
    def test_get_sshkey_returns_key(self, mock_expand, mock_exists):
        agent = _make_agent()
        with patch("builtins.open", mock_open(read_data="ssh-rsa AAAAB3... root@host")):
            result = agent.get_sshkey(_make_req({}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["sshKey"] == "ssh-rsa AAAAB3... root@host"

    @patch("os.path.exists", return_value=False)
    @patch("os.path.expanduser", return_value="/root/.ssh/id_rsa.sftp")
    def test_get_sshkey_returns_error_if_not_found(self, mock_expand, mock_exists):
        agent = _make_agent()
        result = agent.get_sshkey(_make_req({}))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "Cannot find private key" in rsp["error"]


# ---------------------------------------------------------------------------
# write_image_metadata
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpWriteImageMetadata:
    @patch("os.path.getsize", return_value=1024000)
    def test_write_image_metadata_success(self, mock_getsize):
        agent = _make_agent()
        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.md5sum = MagicMock(return_value="abc123md5")

        with patch("builtins.open", mock_open()):
            result = agent.write_image_metadata(_make_req({
                "metaData": {
                    "installPath": "/data/sftp/images/abc/image.qcow2",
                    "name": "test-image",
                }
            }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# check_image_metadata_file_exist
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpCheckImageMetadataFileExist:
    @patch("os.path.isfile", return_value=True)
    def test_metadata_file_exists(self, mock_isfile):
        agent = _make_agent()
        result = agent.check_image_metadata_file_exist(_make_req({
            "backupStoragePath": "/data/sftp/bs",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["exist"] is True

    @patch("os.path.isfile", return_value=False)
    def test_metadata_file_not_exists(self, mock_isfile):
        agent = _make_agent()
        result = agent.check_image_metadata_file_exist(_make_req({
            "backupStoragePath": "/data/sftp/bs",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["exist"] is False


# ---------------------------------------------------------------------------
# generate_image_metadata_file
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpGenerateImageMetadataFile:
    @patch("os.path.isfile", return_value=True)
    def test_generate_existing_file_returns_path(self, mock_isfile):
        agent = _make_agent()
        result = agent.generate_image_metadata_file(_make_req({
            "backupStoragePath": "/data/sftp/bs",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert "bs_sftp_info.json" in rsp["bsFileName"]


# ---------------------------------------------------------------------------
# dump_image_metadata_to_file — single item, dump_all=True
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpDumpImageMetadataToFile:
    def test_dump_single_image_metadata_write_mode(self):
        agent = _make_agent()
        with patch("builtins.open", mock_open()) as mock_file:
            result = agent.dump_image_metadata_to_file(_make_req({
                "backupStoragePath": "/data/sftp/bs",
                "imageMetaData": '{"uuid":"img-001","name":"test"}',
                "dumpAllMetaData": True,
            }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        # verify file was opened in write mode
        mock_file.assert_called_once_with("/data/sftp/bs/bs_sftp_info.json", "w")


# ---------------------------------------------------------------------------
# delete_image_metadata_from_file
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpDeleteImageMetadataFromFile:
    def test_delete_metadata_returns_ret_code(self):
        agent = _make_agent()
        # bash_ro is mocked — returns (0, "")
        bash_mod = sys.modules["zstacklib.utils.bash"]
        bash_mod.bash_ro = MagicMock(return_value=(0, ""))

        result = agent.delete_image_metadata_from_file(_make_req({
            "imageUuid": "img-001",
            "backupStoragePath": "/data/sftp/bs",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["ret"] == 0


# ---------------------------------------------------------------------------
# get_image_hash
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpGetImageHash:
    def test_get_image_hash_returns_hash(self):
        agent = _make_agent()
        secret_mod = sys.modules["zstacklib.utils.secret"]
        secret_mod.get_image_hash = MagicMock(return_value="sha256abcdef")

        result = agent.get_image_hash(_make_req({"path": "/data/sftp/images/test.qcow2"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["hash"] == "sha256abcdef"


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------
@pytest.mark.sftpbackupstorage
class TestSftpCancel:
    def test_cancel_delegates_to_plugin(self):
        agent = _make_agent()
        plugin_mod = sys.modules["zstacklib.utils.plugin"]
        mock_rsp = MagicMock()
        mock_rsp.__dict__ = {"success": True, "error": ""}
        plugin_mod.cancel_job = MagicMock(return_value=mock_rsp)

        result = agent.cancel(_make_req({"cancellationApiId": "api-123"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
