# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock

from kvmagent.plugins import hygon_device_plugin


def _make_plugin():
    return hygon_device_plugin.HygonDevicePlugin.__new__(hygon_device_plugin.HygonDevicePlugin)


def _make_mdev(mdev_root, mdev_uuid, idx, address=None, use=None):
    vendor_dir = mdev_root / mdev_uuid / "vendor"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "idx").write_text(str(idx), encoding="utf-8")
    if address is not None:
        (vendor_dir / "address").write_text(address, encoding="utf-8")
    if use is not None:
        (vendor_dir / "use").write_text(str(use), encoding="utf-8")


@pytest.mark.kvmagent
class TestHygonMdevCollection:
    def test_start_registers_check_endpoint_when_tools_are_missing(self, monkeypatch):
        plugin = _make_plugin()
        http_server = MagicMock()
        monkeypatch.setattr(hygon_device_plugin.kvmagent, "get_http_server", lambda: http_server)
        monkeypatch.setattr(plugin, "_check_tools_availability", lambda: False)

        plugin.start()

        http_server.register_async_uri.assert_called_once_with(
            hygon_device_plugin.HygonDevicePlugin.CHECK_HYGON_TOOLS,
            plugin.check_hygon_tools,
        )

    def test_collect_mdev_bindings_by_vendor_address_without_use_filters_vm_range(self, tmp_path, monkeypatch):
        mdev_root = tmp_path / "mdev-devices"
        mdev_root.mkdir()
        monkeypatch.setattr(hygon_device_plugin.HygonDevicePlugin, "MDEV_DEVICES_PATH", str(mdev_root))

        _make_mdev(mdev_root, "host-mdev", 15, address="0000:06:00.1")
        _make_mdev(mdev_root, "vm-mdev-start", 16, address="0000:06:00.1")
        _make_mdev(mdev_root, "vm-mdev-end", 47, address="0000:23:00.2")
        _make_mdev(mdev_root, "out-of-range", 48, address="0000:23:00.2")
        _make_mdev(mdev_root, "mdev-unknown", 2, address="0000:99:00.1")
        _make_mdev(mdev_root, "mdev-no-address", 3)

        plugin = _make_plugin()
        bindings = plugin._collect_mdev_bindings({
            0: "0000:06:00.1",
            1: "0000:23:00.2",
        }, max_progress=16, max_qemu_num=32)

        assert sorted([b.mdevUuid for b in bindings]) == ["vm-mdev-end", "vm-mdev-start"]
        assert sorted([b.pciBdf for b in bindings]) == ["0000:06:00.1", "0000:23:00.2"]
        assert all(b.useFlag == hygon_device_plugin.HygonDevicePlugin.MDEV_USED_BY_VM for b in bindings)

    def test_collect_mdev_bindings_keeps_old_use_and_idx_mapping(self, tmp_path, monkeypatch):
        mdev_root = tmp_path / "mdev-devices"
        mdev_root.mkdir()
        monkeypatch.setattr(hygon_device_plugin.HygonDevicePlugin, "MDEV_DEVICES_PATH", str(mdev_root))

        _make_mdev(mdev_root, "vm-mdev", 20, use=1)
        _make_mdev(mdev_root, "host-mdev", 21, use=0)

        plugin = _make_plugin()
        bindings = plugin._collect_mdev_bindings({
            0: "0000:06:00.1",
            1: "0000:23:00.2",
        })

        assert len(bindings) == 1
        assert bindings[0].mdevUuid == "vm-mdev"
        assert bindings[0].pciBdf == "0000:23:00.2"
        assert bindings[0].vendorIdx == 20
        assert bindings[0].useFlag == 1
