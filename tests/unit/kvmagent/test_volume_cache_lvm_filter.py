import pytest

try:
    ModuleNotFoundError
except NameError:
    ModuleNotFoundError = ImportError

try:
    from kvmagent.plugins import volume_cache_plugin as vcp
except (ImportError, ModuleNotFoundError) as exc:
    pytest.skip("Cannot import volume_cache_plugin: %s" % exc, allow_module_level=True)


def _write_config(path, device):
    path.write_text(
        'devices {\n'
        '    filter=["a|^%s$|", "r|.*|"]\n'
        '    global_filter=["a|^%s$|", "r|.*|"]\n'
        '}\n' % (device, device)
    )


def _rules(path, key):
    return vcp._extract_lvm_filter_rules(path.read_text(), key)


@pytest.fixture
def lvm_configs(tmp_path, monkeypatch):
    monkeypatch.setattr(vcp.lvm.linux, "sync_file", lambda _path: None, raising=False)
    lvm_conf = tmp_path / "lvm.conf"
    lvmlocal_conf = tmp_path / "lvmlocal.conf"
    _write_config(lvm_conf, "/dev/sharedblock-a")
    _write_config(lvmlocal_conf, "/dev/sharedblock-b")
    return lvm_conf, lvmlocal_conf


def test_append_host_cache_lvm_filter_preserves_sharedblock_devices(lvm_configs):
    lvm_conf, lvmlocal_conf = lvm_configs

    vcp.append_host_cache_lvm_filter_devices(
        ["/dev/cache-a"],
        config_files=(str(lvm_conf), str(lvmlocal_conf)),
    )

    for path in lvm_configs:
        for key in vcp.LVM_FILTER_KEYS:
            rules = _rules(path, key)
            assert "a|^/dev/sharedblock-a$|" in rules
            assert "a|^/dev/sharedblock-b$|" in rules
            assert "a|^/dev/cache-a$|" in rules
            assert rules[-1] == "r|.*|"


def test_append_host_cache_lvm_filter_deduplicates_repeated_devices(lvm_configs):
    lvm_conf, lvmlocal_conf = lvm_configs
    config_files = (str(lvm_conf), str(lvmlocal_conf))

    vcp.append_host_cache_lvm_filter_devices(["/dev/cache-a", "/dev/cache-a"], config_files=config_files)
    vcp.append_host_cache_lvm_filter_devices(["/dev/cache-a"], config_files=config_files)

    for path in lvm_configs:
        for key in vcp.LVM_FILTER_KEYS:
            rules = _rules(path, key)
            assert rules.count("a|^/dev/cache-a$|") == 1


def test_append_host_cache_lvm_filter_updates_lvm_and_lvmlocal_consistently(lvm_configs):
    lvm_conf, lvmlocal_conf = lvm_configs

    vcp.append_host_cache_lvm_filter_devices(
        ["/dev/cache-a", "/dev/cache-b"],
        config_files=(str(lvm_conf), str(lvmlocal_conf)),
    )

    for key in vcp.LVM_FILTER_KEYS:
        assert _rules(lvm_conf, key) == _rules(lvmlocal_conf, key)
        assert _rules(lvm_conf, key) == _rules(lvm_conf, "filter")
