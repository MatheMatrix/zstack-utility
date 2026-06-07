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
