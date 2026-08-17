# -*- coding: utf-8 -*-
from kvmagent.plugins import storage_device


def test_format_iscsi_portal_brackets_ipv6():
    assert storage_device._format_iscsi_portal("192.168.10.10", "3260") == "192.168.10.10:3260"
    assert storage_device._format_iscsi_portal("fd11:5:5:29::4", "3260") == "[fd11:5:5:29::4]:3260"
    assert storage_device._format_iscsi_portal("[fd11:5:5:29::4]", "3260") == "[fd11:5:5:29::4]:3260"


def test_format_iscsi_portal_patterns_keep_legacy_ipv6_match():
    assert storage_device._format_iscsi_portal_patterns("192.168.10.10", "3260") == ["192.168.10.10:3260"]
    assert storage_device._format_iscsi_portal_patterns("fd11:5:5:29::4", "3260") == [
        "[fd11:5:5:29::4]:3260",
        "fd11:5:5:29::4:3260",
    ]


def test_clean_iscsi_cache_configuration_uses_literal_ipv6_portal_path(monkeypatch, tmp_path):
    portal_dir = tmp_path / "iqn.2018-06.org.disk1" / "[fd11:5:5:29::4]:3260"
    portal_dir.mkdir(parents=True)
    removed = []

    monkeypatch.setattr(storage_device.linux, "rm_dir_force", lambda path: removed.append(path))

    storage_device.StorageDevicePlugin.clean_iscsi_cache_configuration(
        str(tmp_path), "fd11:5:5:29::4", "3260")

    assert removed == [str(portal_dir)]
