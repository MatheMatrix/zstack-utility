"""Tests for storage.iscsi module."""

import pytest

from zstacklib.storage.iscsi.models import (
    IscsiPortal,
    ChapCredentials,
    IscsiLun,
    IscsiTarget,
    IscsiSession,
    DiscoveryResult,
    LoginResult,
)


class TestIscsiPortal:
    def test_portal_creation(self):
        portal = IscsiPortal(ip="192.168.1.100", port=3260)
        assert portal.ip == "192.168.1.100"
        assert portal.port == 3260

    def test_portal_default_port(self):
        portal = IscsiPortal(ip="192.168.1.100")
        assert portal.port == 3260

    def test_portal_str(self):
        portal = IscsiPortal(ip="10.0.0.1", port=3261)
        assert str(portal) == "10.0.0.1:3261"

    def test_from_string_with_port(self):
        portal = IscsiPortal.from_string("192.168.1.1:3260")
        assert portal.ip == "192.168.1.1"
        assert portal.port == 3260

    def test_from_string_without_port(self):
        portal = IscsiPortal.from_string("192.168.1.1")
        assert portal.ip == "192.168.1.1"
        assert portal.port == 3260

    def test_from_string_with_tpgt(self):
        portal = IscsiPortal.from_string("192.168.1.1:3260,1")
        assert portal.ip == "192.168.1.1"
        assert portal.port == 3260

    def test_from_string_with_whitespace(self):
        portal = IscsiPortal.from_string("  192.168.1.1:3260  ")
        assert portal.ip == "192.168.1.1"
        assert portal.port == 3260


class TestChapCredentials:
    def test_chap_creation(self):
        creds = ChapCredentials(username="admin", password="secret123")
        assert creds.username == "admin"
        assert creds.password == "secret123"


class TestIscsiLun:
    def test_lun_creation(self):
        lun = IscsiLun(
            lun_id=0,
            path="/dev/disk/by-path/ip-192.168.1.1:3260-iscsi-iqn.2020-01.com.example:target-lun-0",
            size=10737418240,
            wwid="360000000000000000001",
        )
        assert lun.lun_id == 0
        assert lun.size == 10737418240
        assert lun.wwid == "360000000000000000001"

    def test_lun_defaults(self):
        lun = IscsiLun(lun_id=1)
        assert lun.path == ""
        assert lun.size == 0
        assert lun.type == "disk"
        assert lun.wwid is None


class TestIscsiTarget:
    def test_target_creation(self):
        portal = IscsiPortal(ip="192.168.1.1", port=3260)
        target = IscsiTarget(
            iqn="iqn.2020-01.com.example:storage.target1",
            portal=portal,
        )
        assert target.iqn == "iqn.2020-01.com.example:storage.target1"
        assert target.portal.ip == "192.168.1.1"

    def test_target_portal_str(self):
        portal = IscsiPortal(ip="10.0.0.1", port=3260)
        target = IscsiTarget(iqn="iqn.test", portal=portal)
        assert target.portal_str == "10.0.0.1:3260"

    def test_target_with_luns(self):
        portal = IscsiPortal(ip="192.168.1.1")
        lun0 = IscsiLun(lun_id=0, size=1000000000)
        lun1 = IscsiLun(lun_id=1, size=2000000000)
        target = IscsiTarget(
            iqn="iqn.test",
            portal=portal,
            luns=[lun0, lun1],
        )
        assert len(target.luns) == 2
        assert target.luns[0].lun_id == 0
        assert target.luns[1].lun_id == 1


class TestIscsiSession:
    def test_session_creation(self):
        portal = IscsiPortal(ip="192.168.1.1")
        session = IscsiSession(
            session_id="1",
            target_iqn="iqn.2020-01.com.example:target",
            portal=portal,
        )
        assert session.session_id == "1"
        assert session.target_iqn == "iqn.2020-01.com.example:target"
        assert session.state == "LOGGED_IN"

    def test_from_session_line_basic(self):
        line = "tcp: [1] 192.168.1.1:3260,1 iqn.2020-01.com.example:target (non-flash)"
        session = IscsiSession.from_session_line(line)
        assert session is not None
        assert session.session_id == "1"
        assert session.target_iqn == "iqn.2020-01.com.example:target"
        assert session.portal.ip == "192.168.1.1"
        assert session.portal.port == 3260

    def test_from_session_line_minimal(self):
        line = "tcp: [2] 10.0.0.1:3260,1 iqn.test:storage"
        session = IscsiSession.from_session_line(line)
        assert session is not None
        assert session.session_id == "2"
        assert session.portal.ip == "10.0.0.1"

    def test_from_session_line_invalid(self):
        line = "invalid line"
        session = IscsiSession.from_session_line(line)
        assert session is None

    def test_from_session_line_empty(self):
        session = IscsiSession.from_session_line("")
        assert session is None


class TestDiscoveryResult:
    def test_discovery_success(self):
        portal = IscsiPortal(ip="192.168.1.1")
        target = IscsiTarget(iqn="iqn.test", portal=portal)
        result = DiscoveryResult(
            portal=portal,
            targets=[target],
            success=True,
        )
        assert result.success is True
        assert len(result.targets) == 1

    def test_discovery_failure(self):
        portal = IscsiPortal(ip="192.168.1.1")
        result = DiscoveryResult(
            portal=portal,
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


class TestLoginResult:
    def test_login_success(self):
        portal = IscsiPortal(ip="192.168.1.1")
        target = IscsiTarget(iqn="iqn.test", portal=portal)
        session = IscsiSession(session_id="1", target_iqn="iqn.test", portal=portal)
        result = LoginResult(
            target=target,
            session=session,
            success=True,
            disks=["/dev/sdb", "/dev/sdc"],
        )
        assert result.success is True
        assert len(result.disks) == 2

    def test_login_failure(self):
        portal = IscsiPortal(ip="192.168.1.1")
        target = IscsiTarget(iqn="iqn.test", portal=portal)
        result = LoginResult(
            target=target,
            success=False,
            error="Authentication failed",
        )
        assert result.success is False
        assert result.session is None
