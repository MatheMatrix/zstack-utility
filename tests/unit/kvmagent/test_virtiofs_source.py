# -*- coding: utf-8 -*-

import json
import os

import pytest

from kvmagent.plugins import virtiofs_source


class Obj(object):
    pass


class Statvfs(object):
    def __init__(self, available_bytes):
        self.f_frsize = 1
        self.f_bavail = available_bytes


def _provider_with_roots(*roots):
    provider = virtiofs_source.PreparedPathSourceProvider()
    provider.allowed_roots = roots
    return provider


def test_source_spec_from_command_uses_structured_spec():
    cmd = Obj()
    cmd.sourcePath = '/ignored'
    cmd.sourceSpec = {
        'type': 'local',
        'path': '/var/lib/zstack/aios/virtiofs-sources/source-a',
        'uuid': 'source-a',
    }

    spec = virtiofs_source.SourceSpec.from_command(cmd)

    assert spec.source_type == 'local'
    assert spec.path == '/var/lib/zstack/aios/virtiofs-sources/source-a'
    assert spec.source_uuid == 'source-a'


def test_source_spec_from_command_keeps_legacy_flat_fields():
    cmd = Obj()
    cmd.sourceType = 'preparedPath'
    cmd.sourcePath = '/var/lib/zstack/aios/virtiofs-sources/source-a'
    cmd.sourceUuid = 'source-a'

    spec = virtiofs_source.SourceSpec.from_command(cmd)

    assert spec.source_type == 'preparedPath'
    assert spec.path == '/var/lib/zstack/aios/virtiofs-sources/source-a'
    assert spec.source_uuid == 'source-a'


def test_prepare_path_source_records_ready_source(tmp_path):
    source_dir = tmp_path / 'virtiofs-sources' / 'source-a'
    source_dir.mkdir(parents=True)
    registry_file = tmp_path / 'registry.json'
    manager = virtiofs_source.SourceManager(
        providers=[_provider_with_roots(str(tmp_path / 'virtiofs-sources'))],
        registry=virtiofs_source.SourceRegistry(str(registry_file)),
    )

    host_source = manager.ensure_ready({
        'type': 'preparedPath',
        'sourcePath': str(source_dir),
        'sourceUuid': 'source-a',
    })

    assert host_source.sourceUuid == 'source-a'
    assert host_source.sourceType == 'preparedPath'
    assert host_source.path == os.path.realpath(str(source_dir))
    with open(str(registry_file), 'r') as fd:
        registry = json.load(fd)
    assert registry['source-a']['state'] == 'ready'
    assert registry['source-a']['capability']['persistent'] is True


def test_prepare_path_source_accepts_command_source_root(tmp_path):
    source_dir = tmp_path / 'large-disk' / 'model-centers' / 'mc' / 'root' / 'models' / 'qwen'
    source_dir.mkdir(parents=True)
    registry_file = tmp_path / 'registry.json'
    manager = virtiofs_source.SourceManager(
        registry=virtiofs_source.SourceRegistry(str(registry_file)),
    )

    host_source = manager.ensure_ready({
        'type': 'preparedPath',
        'sourcePath': str(source_dir),
        'sourceRootPath': str(tmp_path / 'large-disk'),
        'sourceUuid': 'source-a',
    })

    assert host_source.path == os.path.realpath(str(source_dir))


def test_prepare_path_source_rejects_insufficient_capacity(tmp_path, monkeypatch):
    source_dir = tmp_path / 'large-disk' / 'source-a'
    source_dir.mkdir(parents=True)
    monkeypatch.setattr(virtiofs_source.os, 'statvfs', lambda path: Statvfs(512))
    manager = virtiofs_source.SourceManager(
        registry=virtiofs_source.SourceRegistry(str(tmp_path / 'registry.json')),
    )

    with pytest.raises(Exception) as exc_info:
        manager.ensure_ready({
            'type': 'preparedPath',
            'sourcePath': str(source_dir),
            'sourceRootPath': str(tmp_path / 'large-disk'),
            'requiredCapacityBytes': 1024,
        })

    assert 'available capacity[512 bytes] is less than required capacity[1024 bytes]' in str(exc_info.value)


def test_prepare_path_source_accepts_vm_view_root(tmp_path):
    view_dir = tmp_path / 'vm-views' / 'vm-a'
    view_dir.mkdir(parents=True)
    manager = virtiofs_source.SourceManager(
        providers=[_provider_with_roots(str(tmp_path / 'virtiofs-sources'), str(tmp_path / 'vm-views'))],
        registry=virtiofs_source.SourceRegistry(str(tmp_path / 'registry.json')),
    )

    host_source = manager.ensure_ready({
        'type': 'preparedPath',
        'sourcePath': str(view_dir),
    })

    assert host_source.path == os.path.realpath(str(view_dir))


def test_prepare_path_source_rejects_shared_root_itself(tmp_path):
    source_root = tmp_path / 'virtiofs-sources'
    source_root.mkdir()
    manager = virtiofs_source.SourceManager(
        providers=[_provider_with_roots(str(source_root))],
        registry=virtiofs_source.SourceRegistry(str(tmp_path / 'registry.json')),
    )

    with pytest.raises(Exception) as exc_info:
        manager.ensure_ready({
            'type': 'preparedPath',
            'sourcePath': str(source_root),
        })

    assert 'not a concrete virtiofs source' in str(exc_info.value)


def test_prepare_path_source_rejects_outside_roots(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    manager = virtiofs_source.SourceManager(
        providers=[_provider_with_roots(str(tmp_path / 'virtiofs-sources'))],
        registry=virtiofs_source.SourceRegistry(str(tmp_path / 'registry.json')),
    )

    with pytest.raises(Exception) as exc_info:
        manager.ensure_ready({
            'type': 'preparedPath',
            'sourcePath': str(outside),
        })

    assert 'outside allowed virtiofs source directory' in str(exc_info.value)


def test_prepare_path_source_rejects_unsupported_source_type(tmp_path):
    manager = virtiofs_source.SourceManager(
        providers=[_provider_with_roots(str(tmp_path / 'virtiofs-sources'))],
        registry=virtiofs_source.SourceRegistry(str(tmp_path / 'registry.json')),
    )

    with pytest.raises(Exception) as exc_info:
        manager.ensure_ready({
            'type': 'juicefs',
            'sourcePath': '/var/lib/zstack/aios/virtiofs-sources/source-a',
        })

    assert 'unsupported virtiofs source type[juicefs]' in str(exc_info.value)


def test_registry_load_ignores_invalid_json(tmp_path):
    registry_file = tmp_path / 'registry.json'
    registry_file.write_text('{broken')

    assert virtiofs_source.SourceRegistry(str(registry_file)).load() == {}
