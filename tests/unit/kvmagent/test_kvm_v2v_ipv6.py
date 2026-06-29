from kvmagent.plugins import kvm_v2v_plugin


def test_build_nfs_mount_source_keeps_ipv4_and_hostname():
    assert kvm_v2v_plugin.build_nfs_mount_source(
        "192.168.10.10",
        "/v2v/v2v-cache",
    ) == "192.168.10.10:/v2v/v2v-cache"
    assert kvm_v2v_plugin.build_nfs_mount_source(
        "v2v-convert.example.com",
        "/v2v/v2v-cache",
    ) == "v2v-convert.example.com:/v2v/v2v-cache"


def test_build_nfs_mount_source_brackets_ipv6_once():
    assert kvm_v2v_plugin.build_nfs_mount_source(
        "fd00:5:5:28::e:e554",
        "/v2v/v2v-cache",
    ) == "[fd00:5:5:28::e:e554]:/v2v/v2v-cache"
    assert kvm_v2v_plugin.build_nfs_mount_source(
        "[fd00:5:5:28::e:e554]",
        "/v2v/v2v-cache",
    ) == "[fd00:5:5:28::e:e554]:/v2v/v2v-cache"


def test_should_apply_ipv4_qos_only_accepts_ipv4():
    assert kvm_v2v_plugin.should_apply_ipv4_qos("192.168.10.10")
    assert not kvm_v2v_plugin.should_apply_ipv4_qos("fd00:5:5:28::e:e554")
    assert not kvm_v2v_plugin.should_apply_ipv4_qos("")


def test_normalize_host_for_lookup_removes_ipv6_brackets_only():
    assert kvm_v2v_plugin.normalize_host_for_lookup("192.168.10.10") == "192.168.10.10"
    assert kvm_v2v_plugin.normalize_host_for_lookup("fd00:5:5:28::e:e554") == "fd00:5:5:28::e:e554"
    assert kvm_v2v_plugin.normalize_host_for_lookup("[fd00:5:5:28::e:e554]") == "fd00:5:5:28::e:e554"
