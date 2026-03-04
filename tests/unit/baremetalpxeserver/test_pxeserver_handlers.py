from __future__ import annotations

import importlib
import json
import sys
import os
import pytest
from typing import cast
from unittest.mock import MagicMock, patch, mock_open, call


# ---------------------------------------------------------------------------
# Import the baremetalpxeserver module with octal fix
# ---------------------------------------------------------------------------
try:
    import tests.conftest  # noqa: F401

    from tests.conftest import passthrough_lock
    lock_mod = cast(object, importlib.import_module("zstacklib.utils.lock"))

    setattr(lock_mod, "lock", passthrough_lock)
    setattr(lock_mod, "file_lock", passthrough_lock)

    module = importlib.import_module("baremetalpxeserver.pxeserveragent")
    module = importlib.reload(module)
except Exception as e:
    pytest.skip(f"Cannot import baremetalpxeserver: {e}", allow_module_level=True)


_orig_module_os = getattr(module, 'os', None)


@pytest.fixture(autouse=True)
def _restore_module_os():
    """Restore module.os after each test to prevent cross-test pollution."""
    yield
    if _orig_module_os is not None:
        module.os = _orig_module_os


def _make_req(body_dict=None):
    http = cast(object, importlib.import_module("zstacklib.utils.http"))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _load_rsp(result):
    return json.loads(result)


def _make_agent():
    """Create PxeServerAgent via __new__ to skip __init__ side effects."""
    agent = module.PxeServerAgent.__new__(module.PxeServerAgent)
    agent.uuid = "pxe-uuid-001"
    agent.storage_path = "/var/lib/zstack/baremetal/storage"
    agent.dhcp_interface = "eth0"
    agent.imagestore_client = MagicMock()
    return agent


def _mock_capacity(agent, total=10**12, avail=5 * 10**11):
    """Patch _get_capacity to return predictable values."""
    agent._get_capacity = MagicMock(return_value=(total, total - (total - avail)))


# ---------------------------------------------------------------------------
# echo
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeEcho:
    def test_echo_returns_empty_string(self):
        agent = _make_agent()
        result = agent.echo(_make_req())
        assert result == ""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeInit:
    @patch("builtins.open", mock_open())
    def test_init_success(self):
        agent = _make_agent()
        _mock_capacity(agent)

        # Mock static helpers
        agent._get_ip_address = MagicMock(return_value="192.168.1.10")
        agent._get_mac_address = MagicMock(return_value="aa:bb:cc:dd:ee:ff")
        agent._is_belong_to_same_subnet = MagicMock(return_value=True)
        agent._start_pxe_server = MagicMock()
        agent._stop_pxe_server = MagicMock()

        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_netmask_of_nic = MagicMock(return_value="255.255.255.0")

        module.bash_r = MagicMock(return_value=0)
        mock_os = MagicMock(wraps=os)
        mock_os.path.exists = MagicMock(return_value=True)
        mock_os.path.islink = MagicMock(return_value=True)
        mock_os.remove = MagicMock()
        mock_os.symlink = MagicMock()
        mock_os.makedirs = MagicMock()
        module.os = mock_os

        result = agent.init(_make_req({
            "uuid": "pxe-001",
            "storagePath": "/var/lib/zstack/baremetal/storage",
            "dhcpInterface": "eth0",
            "dhcpRangeBegin": "192.168.1.100",
            "dhcpRangeEnd": "192.168.1.200",
            "dhcpRangeNetmask": "255.255.255.0",
            "managementIp": "10.0.0.1",
            "managementPort": 8080,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        agent._stop_pxe_server.assert_called_once()
        agent._start_pxe_server.assert_called_once()

    def test_init_fails_when_dhcp_range_not_in_subnet(self):
        agent = _make_agent()
        _mock_capacity(agent)

        agent._get_ip_address = MagicMock(return_value="192.168.1.10")
        # First call (begin) returns False = not in subnet
        agent._is_belong_to_same_subnet = MagicMock(return_value=False)

        linux_mod = sys.modules["zstacklib.utils.linux"]
        linux_mod.get_netmask_of_nic = MagicMock(return_value="255.255.255.0")

        result = agent.init(_make_req({
            "uuid": "pxe-001",
            "storagePath": "/var/lib/zstack/baremetal/storage",
            "dhcpInterface": "eth0",
            "dhcpRangeBegin": "10.0.0.100",
            "dhcpRangeEnd": "10.0.0.200",
            "dhcpRangeNetmask": "255.255.255.0",
            "managementIp": "10.0.0.1",
            "managementPort": 8080,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "cannot connect to dhcp interface" in rsp["error"]


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxePing:
    def test_ping_no_rogue_dhcp_returns_uuid(self):
        agent = _make_agent()
        agent._get_mac_address = MagicMock(return_value="aa:bb:cc:dd:ee:ff")
        agent._start_pxe_server = MagicMock()

        # nmap returns non-zero = no rogue DHCP found
        module.bash_ro = MagicMock(return_value=(1, ""))

        result = agent.ping(_make_req({
            "dhcpInterface": "eth0",
            "enabled": True,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["uuid"] == "pxe-uuid-001"
        agent._start_pxe_server.assert_called_once()

    def test_ping_detects_rogue_dhcp(self):
        agent = _make_agent()
        agent._get_mac_address = MagicMock(return_value="aa:bb:cc:dd:ee:ff")

        # nmap returns 0 = rogue DHCP found
        module.bash_ro = MagicMock(return_value=(0, "Server Identifier: 10.0.0.99"))

        result = agent.ping(_make_req({
            "dhcpInterface": "eth0",
            "enabled": False,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "rogue dhcp server" in rsp["error"]

    def test_ping_disabled_does_not_start_server(self):
        agent = _make_agent()
        agent._get_mac_address = MagicMock(return_value="aa:bb:cc:dd:ee:ff")
        agent._start_pxe_server = MagicMock()

        module.bash_ro = MagicMock(return_value=(1, ""))

        result = agent.ping(_make_req({
            "dhcpInterface": "eth0",
            "enabled": False,
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        agent._start_pxe_server.assert_not_called()


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeConnect:
    def test_connect_returns_capacity(self):
        agent = _make_agent()
        _mock_capacity(agent)

        module.os = MagicMock(wraps=os)
        module.os.path.isfile = MagicMock(return_value=False)
        module.os.path.exists = MagicMock(return_value=True)

        result = agent.connect(_make_req({
            "uuid": "pxe-002",
            "storagePath": "/var/lib/zstack/baremetal/storage",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["totalCapacity"] == 10**12
        assert rsp["availableCapacity"] == 5 * 10**11
        assert agent.uuid == "pxe-002"

    def test_connect_raises_if_path_is_file(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.isfile = MagicMock(return_value=True)

        result = agent.connect(_make_req({
            "uuid": "pxe-002",
            "storagePath": "/some/file.img",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "is a file" in rsp["error"]


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeStart:
    def test_start_calls_start_pxe_server(self):
        agent = _make_agent()
        agent._start_pxe_server = MagicMock()

        result = agent.start(_make_req({"uuid": "pxe-001"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        agent._start_pxe_server.assert_called_once()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeStop:
    def test_stop_calls_stop_pxe_server(self):
        agent = _make_agent()
        agent._stop_pxe_server = MagicMock()

        result = agent.stop(_make_req({"uuid": "pxe-001"}))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        agent._stop_pxe_server.assert_called_once()


# ---------------------------------------------------------------------------
# create_bm_configs
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeCreateBmConfigs:
    def test_create_bm_configs_kickstart(self):
        agent = _make_agent()
        agent._get_ip_address = MagicMock(return_value="192.168.1.10")
        agent._create_pxelinux_cfg = MagicMock()
        agent._create_preconfiguration_file = MagicMock()

        content = "kickstart content"
        md5sum = __import__("hashlib").md5(content.encode()).hexdigest()

        # Mock hashlib.md5 on the module to handle Py3 str input
        real_hashlib = __import__("hashlib")
        mock_md5_obj = MagicMock()
        mock_md5_obj.hexdigest.return_value = md5sum
        mock_hashlib = MagicMock(wraps=real_hashlib)
        mock_hashlib.md5 = MagicMock(return_value=mock_md5_obj)
        module.hashlib = mock_hashlib

        result = agent.create_bm_configs(_make_req({
            "uuid": "pxe-001",
            "dhcpInterface": "eth0",
            "pxeNicMac": "aa:bb:cc:dd:ee:ff",
            "bmUuid": "bm-001",
            "preconfigurationContent": content,
            "preconfigurationMd5sum": md5sum,
            "preconfigurationType": "kickstart",
            "imageUuid": "img-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        agent._create_pxelinux_cfg.assert_called_once()
        agent._create_preconfiguration_file.assert_called_once()

    def test_create_bm_configs_fails_on_md5_mismatch(self):
        agent = _make_agent()

        # Mock hashlib.md5 on the module to handle Py3 str input
        real_hashlib = __import__("hashlib")
        mock_md5_obj = MagicMock()
        mock_md5_obj.hexdigest.return_value = "correct-md5-hash"
        mock_hashlib = MagicMock(wraps=real_hashlib)
        mock_hashlib.md5 = MagicMock(return_value=mock_md5_obj)
        module.hashlib = mock_hashlib

        result = agent.create_bm_configs(_make_req({
            "uuid": "pxe-001",
            "dhcpInterface": "eth0",
            "pxeNicMac": "aa:bb:cc:dd:ee:ff",
            "bmUuid": "bm-001",
            "preconfigurationContent": "some content",
            "preconfigurationMd5sum": "wrong-md5",
            "preconfigurationType": "kickstart",
            "imageUuid": "img-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "preconfiguration content not complete" in rsp["error"]


# ---------------------------------------------------------------------------
# delete_bm_configs — wildcard
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDeleteBmConfigs:
    def test_delete_all_configs_wildcard(self):
        agent = _make_agent()

        module.bash_r = MagicMock(return_value=0)
        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)

        result = agent.delete_bm_configs(_make_req({
            "pxeNicMac": "*",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        # Should call bash_r for rm -f on multiple paths
        assert module.bash_r.call_count >= 4

    def test_delete_specific_config_by_mac(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.path.isdir = MagicMock(return_value=False)
        module.os.path.isfile = MagicMock(return_value=True)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join

        result = agent.delete_bm_configs(_make_req({
            "pxeNicMac": "aa:bb:cc:dd:ee:ff",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        # Should call os.remove for pxe cfg, grub cfg, symlink, ks cfg, pre/post scripts
        assert module.os.remove.call_count >= 3


# ---------------------------------------------------------------------------
# create_bm_nginx_proxy
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeCreateBmNginxProxy:
    @patch("builtins.open", mock_open())
    def test_create_nginx_proxy_writes_upstream(self):
        agent = _make_agent()
        module.bash_roe = MagicMock(return_value=(0, "", ""))

        result = agent.create_bm_nginx_proxy(_make_req({
            "bmUuid": "bm-001",
            "upstream": "location / { proxy_pass http://10.0.0.1:4200; }",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# delete_bm_nginx_proxy
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDeleteBmNginxProxy:
    def test_delete_nginx_proxy_removes_file(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join
        module.bash_roe = MagicMock(return_value=(0, "", ""))

        result = agent.delete_bm_nginx_proxy(_make_req({
            "bmUuid": "bm-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        module.os.remove.assert_called_once()

    def test_delete_nginx_proxy_file_not_exists(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=False)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join
        module.bash_roe = MagicMock(return_value=(0, "", ""))

        result = agent.delete_bm_nginx_proxy(_make_req({
            "bmUuid": "bm-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        module.os.remove.assert_not_called()


# ---------------------------------------------------------------------------
# create_bm_novnc_proxy
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeCreateBmNovncProxy:
    @patch("builtins.open", mock_open())
    def test_create_novnc_proxy_writes_token_file(self):
        agent = _make_agent()

        result = agent.create_bm_novnc_proxy(_make_req({
            "bmUuid": "bm-001",
            "upstream": "bm-001: 10.0.0.5:5900",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# delete_bm_novnc_proxy
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDeleteBmNovncProxy:
    def test_delete_novnc_proxy_removes_token_file(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join

        result = agent.delete_bm_novnc_proxy(_make_req({
            "bmUuid": "bm-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        module.os.remove.assert_called_once()


# ---------------------------------------------------------------------------
# create_bm_dhcp_config
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeCreateBmDhcpConfig:
    @patch("builtins.open", mock_open())
    def test_create_dhcp_config_writes_host_file(self):
        agent = _make_agent()

        result = agent.create_bm_dhcp_config(_make_req({
            "chassisUuid": "chassis-001",
            "pxeNicMac": "aa:bb:cc:dd:ee:ff",
            "pxeNicIp": "192.168.1.50",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# delete_bm_dhcp_config
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDeleteBmDhcpConfig:
    def test_delete_dhcp_config_removes_host_file(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join

        result = agent.delete_bm_dhcp_config(_make_req({
            "chassisUuid": "chassis-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        module.os.remove.assert_called_once()

    def test_delete_dhcp_config_file_not_exists(self):
        agent = _make_agent()

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=False)
        module.os.remove = MagicMock()
        module.os.path.join = os.path.join

        result = agent.delete_bm_dhcp_config(_make_req({
            "chassisUuid": "chassis-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        module.os.remove.assert_not_called()


# ---------------------------------------------------------------------------
# download_imagestore
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDownloadImagestore:
    def test_download_imagestore_success(self):
        agent = _make_agent()
        _mock_capacity(agent)

        # imagestore_client.download_image_from_imagestore returns success
        mock_dl_rsp = MagicMock()
        mock_dl_rsp.success = True
        agent.imagestore_client.download_image_from_imagestore = MagicMock(return_value=mock_dl_rsp)

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.path.join = os.path.join
        module.os.makedirs = MagicMock()
        module.bash_r = MagicMock(return_value=0)

        result = agent.download_imagestore(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["totalCapacity"] == 10**12

    def test_download_imagestore_fails_on_download_error(self):
        agent = _make_agent()

        mock_dl_rsp = MagicMock()
        mock_dl_rsp.success = False
        agent.imagestore_client.download_image_from_imagestore = MagicMock(return_value=mock_dl_rsp)

        result = agent.download_imagestore(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "failed to download image" in rsp["error"]

    def test_download_imagestore_fails_on_mount_error(self):
        agent = _make_agent()
        _mock_capacity(agent)

        mock_dl_rsp = MagicMock()
        mock_dl_rsp.success = True
        agent.imagestore_client.download_image_from_imagestore = MagicMock(return_value=mock_dl_rsp)

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=False)
        module.os.path.join = os.path.join
        module.os.makedirs = MagicMock()
        # mount fails
        module.bash_r = MagicMock(return_value=1)

        result = agent.download_imagestore(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "failed to mount image" in rsp["error"]


# ---------------------------------------------------------------------------
# download_cephb
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDownloadCephb:
    def test_download_cephb_returns_success_stub(self):
        agent = _make_agent()

        result = agent.download_cephb(_make_req({
            "imageUuid": "img-001",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True


# ---------------------------------------------------------------------------
# delete_bm_image_cache
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeDeleteBmImageCache:
    def test_delete_image_cache_success(self):
        agent = _make_agent()
        _mock_capacity(agent)

        module.os = MagicMock(wraps=os)
        module.os.path.exists = MagicMock(return_value=True)
        module.os.path.join = os.path.join
        module.os.remove = MagicMock()
        module.shutil = MagicMock()
        module.bash_r = MagicMock(return_value=0)

        result = agent.delete_bm_image_cache(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True
        assert rsp["totalCapacity"] == 10**12


# ---------------------------------------------------------------------------
# mount_bm_image_cache
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeMountBmImageCache:
    def test_mount_image_cache_success(self):
        agent = _make_agent()

        module.bash_r = MagicMock(return_value=0)

        result = agent.mount_bm_image_cache(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is True

    def test_mount_image_cache_fails(self):
        agent = _make_agent()

        module.bash_r = MagicMock(return_value=1)

        result = agent.mount_bm_image_cache(_make_req({
            "imageUuid": "img-001",
            "cacheInstallPath": "/var/lib/zstack/baremetal/cache/img-001.iso",
        }))
        rsp = _load_rsp(result)
        assert rsp["success"] is False
        assert "failed to mount" in rsp["error"]


# ---------------------------------------------------------------------------
# _start_pxe_server / _stop_pxe_server (internal helpers)
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeStartStopHelpers:
    def test_start_pxe_server_success(self):
        agent = _make_agent()
        module.bash_roe = MagicMock(return_value=(0, "", ""))

        # Should not raise
        agent._start_pxe_server()
        # bash_roe called 4 times: dnsmasq, vsftpd, websockify, nginx
        assert module.bash_roe.call_count == 4

    def test_start_pxe_server_dnsmasq_failure(self):
        agent = _make_agent()
        module.bash_roe = MagicMock(return_value=(1, "", "dnsmasq error"))

        with pytest.raises(module.PxeServerError, match="failed to start dnsmasq"):
            agent._start_pxe_server()

    def test_stop_pxe_server(self):
        agent = _make_agent()
        module.bash_r = MagicMock(return_value=0)

        # Should not raise
        agent._stop_pxe_server()
        # bash_r called 4 times: vsftpd, websockify, dnsmasq, nginx
        assert module.bash_r.call_count == 4


# ---------------------------------------------------------------------------
# AgentResponse / PingResponse / InitResponse classes
# ---------------------------------------------------------------------------
@pytest.mark.baremetalpxeserver
class TestPxeResponseClasses:
    def test_agent_response_defaults(self):
        rsp = module.AgentResponse()
        assert rsp.success is True
        assert rsp.error == ""
        assert rsp.totalCapacity is None

    def test_agent_response_with_error(self):
        rsp = module.AgentResponse(success=False, error="test error")
        assert rsp.success is False
        assert rsp.error == "test error"

    def test_ping_response_inherits(self):
        rsp = module.PingResponse()
        assert rsp.success is True
        assert rsp.uuid is None

    def test_init_response_inherits(self):
        rsp = module.InitResponse()
        assert rsp.success is True
        assert rsp.dhcpRangeBegin is None
        assert rsp.dhcpRangeEnd is None
        assert rsp.dhcpRangeNetmask is None
