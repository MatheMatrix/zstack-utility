import pytest

try:
    from zstacklib.utils import lvm
except ImportError as exc:
    pytest.skip("Cannot import lvm utils: %s" % exc, allow_module_level=True)


class NoopFileLock(object):
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


def _write_config(path, device):
    path.write_text(
        'devices {\n'
        '    filter=["a|^%s$|", "r|.*|"]\n'
        '    global_filter=["a|^%s$|", "r|.*|"]\n'
        '}\n' % (device, device)
    )


def _rules(path, key):
    return lvm._get_lvm_filter_rules(path.read_text(), key)


def _devices(path, key):
    return set(filter(None, [
        lvm._exact_device_from_lvm_accept_rule(rule)
        for rule in _rules(path, key)
    ]))


@pytest.fixture
def lvm_configs(tmp_path, monkeypatch):
    monkeypatch.setattr(lvm.linux, "sync_file", lambda _path: None, raising=False)
    monkeypatch.setattr(lvm.lock, "FileLock", NoopFileLock)
    lvm_conf = tmp_path / "lvm.conf"
    lvmlocal_conf = tmp_path / "lvmlocal.conf"
    monkeypatch.setattr(lvm, "LVM_CONFIG_PATH", str(tmp_path))
    _write_config(lvm_conf, "/dev/sharedblock-a")
    _write_config(lvmlocal_conf, "/dev/sharedblock-b")
    return lvm_conf, lvmlocal_conf


def test_append_host_cache_lvm_filter_preserves_sharedblock_devices_and_deduplicates(lvm_configs):
    lvm_conf, lvmlocal_conf = lvm_configs

    lvm.append_lvm_filter_devices(["/dev/cache-a", "/dev/cache-a", "/dev/cache-b"])
    lvm.append_lvm_filter_devices(["/dev/cache-a"])

    for key in lvm.LVM_FILTER_KEYS:
        assert _devices(lvm_conf, key) == _devices(lvmlocal_conf, key)
        devices = _devices(lvm_conf, key)
        assert "/dev/sharedblock-a" in devices
        assert "/dev/sharedblock-b" in devices
        assert "/dev/cache-a" in devices
        assert "/dev/cache-b" in devices
        assert _rules(lvm_conf, key).count("a|^\\/dev\\/cache-a$|") == 1
        assert _rules(lvm_conf, key)[-1] == "r\\/.*\\/"


def test_remove_host_cache_lvm_filter_devices_keeps_sharedblock_devices(lvm_configs):
    lvm.append_lvm_filter_devices(["/dev/cache-a", "/dev/cache-b"])
    lvm.remove_lvm_filter_devices(["/dev/cache-a"])

    for path in lvm_configs:
        for key in lvm.LVM_FILTER_KEYS:
            devices = _devices(path, key)
            assert "/dev/sharedblock-a" in devices
            assert "/dev/sharedblock-b" in devices
            assert "/dev/cache-a" not in devices
            assert "/dev/cache-b" in devices
            assert _rules(path, key)[-1] == "r\\/.*\\/"
