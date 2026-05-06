# Copyright (c) 2025, ZStack, Inc.

import hashlib
import json
import os
import re


HOST_SOURCE_ROOT = '/var/lib/zstack/aios/virtiofs-sources'
VM_VIEW_ROOT = '/var/lib/zstack/aios/vm-views'
SOURCE_REGISTRY_FILE = os.path.join(HOST_SOURCE_ROOT, '.registry')


def get_attr(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    try:
        if hasattr(obj, 'hasattr') and obj.hasattr(name):
            return getattr(obj, name)
    except Exception:
        pass
    return getattr(obj, name, default)


def _safe_id(value, prefix):
    value = str(value or '').strip()
    value = re.sub(r'[^A-Za-z0-9_.-]', '_', value).strip('._-')
    if value:
        return value[:96]
    return prefix


def _path_id(path):
    digest = hashlib.sha1(os.path.realpath(path).encode('utf-8')).hexdigest()
    return 'source-%s' % digest[:16]


def ensure_under(path, root, field_name, allow_root=True):
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    if real_path == real_root:
        if allow_root:
            return real_path
        raise Exception('%s[%s] resolves to shared root[%s], not a concrete virtiofs source' % (
            field_name, path, real_root))
    if not real_path.startswith(real_root + os.sep):
        raise Exception('%s[%s] resolves to path[%s] outside allowed virtiofs source directory or VM view directory[%s]' % (
            field_name, path, real_path, root))
    return real_path


def ensure_under_any(path, roots, field_name, allow_root=True):
    root_error = None
    for root in roots:
        try:
            return ensure_under(path, root, field_name, allow_root)
        except Exception as exc:
            if 'not a concrete virtiofs source' in str(exc):
                root_error = exc
            pass
    if root_error:
        raise root_error
    raise Exception('%s[%s] is outside allowed virtiofs source directory or VM view directory[%s]' % (
        field_name, path, ','.join([os.path.realpath(root) for root in roots])))


class SourceCapability(object):
    def __init__(self, migratable=False, snapshotable=False, persistent=True, shared_across_hosts=False):
        self.migratable = migratable
        self.snapshotable = snapshotable
        self.persistent = persistent
        self.sharedAcrossHosts = shared_across_hosts

    def to_dict(self):
        return {
            'migratable': self.migratable,
            'snapshotable': self.snapshotable,
            'persistent': self.persistent,
            'sharedAcrossHosts': self.sharedAcrossHosts,
        }


class SourceSpec(object):
    def __init__(self, source_type='preparedPath', path=None, source_uuid=None):
        self.source_type = source_type or 'preparedPath'
        self.path = path
        self.source_uuid = source_uuid

    @staticmethod
    def from_raw(raw):
        if isinstance(raw, SourceSpec):
            return raw
        source_type = get_attr(raw, 'type', get_attr(raw, 'sourceType', 'preparedPath'))
        path = (get_attr(raw, 'path') or get_attr(raw, 'sourcePath') or
                get_attr(raw, 'preparedPath'))
        source_uuid = get_attr(raw, 'sourceUuid', get_attr(raw, 'uuid'))
        return SourceSpec(source_type, path, source_uuid)

    @staticmethod
    def from_command(cmd):
        source_spec = get_attr(cmd, 'sourceSpec')
        if source_spec:
            return SourceSpec.from_raw(source_spec)
        return SourceSpec(
            get_attr(cmd, 'sourceType', 'preparedPath'),
            get_attr(cmd, 'sourcePath'),
            get_attr(cmd, 'sourceUuid'),
        )


class HostSource(object):
    def __init__(self, source_uuid, source_type, path, capability):
        self.sourceUuid = source_uuid
        self.sourceType = source_type
        self.path = path
        self.capability = capability

    def to_registry_entry(self):
        return {
            'sourceUuid': self.sourceUuid,
            'sourceType': self.sourceType,
            'path': self.path,
            'capability': self.capability.to_dict(),
            'state': 'ready',
        }


class PreparedPathSourceProvider(object):
    source_types = ('preparedPath', 'local')
    allowed_roots = (HOST_SOURCE_ROOT, VM_VIEW_ROOT)

    def can_handle(self, spec):
        return spec.source_type in self.source_types

    def prepare(self, spec):
        if not spec.path:
            raise Exception('sourcePath is required')
        if not os.path.exists(spec.path):
            raise Exception('sourcePath[%s] does not exist' % spec.path)
        if not os.path.isdir(spec.path):
            raise Exception('sourcePath[%s] is not a directory' % spec.path)

        path = ensure_under_any(spec.path, self.allowed_roots, 'sourcePath', allow_root=False)
        source_uuid = _safe_id(spec.source_uuid, None) if spec.source_uuid else _path_id(path)
        capability = SourceCapability(
            migratable=False,
            snapshotable=False,
            persistent=True,
            shared_across_hosts=False,
        )
        return HostSource(source_uuid, spec.source_type, path, capability)


class SourceRegistry(object):
    def __init__(self, path=SOURCE_REGISTRY_FILE):
        self.path = path

    def load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, 'r') as fd:
                data = json.load(fd)
            return data if isinstance(data, dict) else {}
        except (IOError, ValueError):
            return {}

    def save_host_source(self, host_source):
        parent = os.path.dirname(self.path)
        try:
            if parent and not os.path.exists(parent):
                os.makedirs(parent)
            data = self.load()
            data[host_source.sourceUuid] = host_source.to_registry_entry()
            tmp_path = self.path + '.tmp'
            with open(tmp_path, 'w') as fd:
                json.dump(data, fd, indent=2)
            os.rename(tmp_path, self.path)
            return True
        except (IOError, OSError):
            return False


class SourceManager(object):
    def __init__(self, providers=None, registry=None):
        self.providers = providers or [PreparedPathSourceProvider()]
        self.registry = registry or SourceRegistry()

    def ensure_ready(self, raw_spec):
        spec = SourceSpec.from_raw(raw_spec)
        for provider in self.providers:
            if provider.can_handle(spec):
                host_source = provider.prepare(spec)
                self.registry.save_host_source(host_source)
                return host_source
        raise Exception('unsupported virtiofs source type[%s]' % spec.source_type)


def ensure_ready(raw_spec):
    return SourceManager().ensure_ready(raw_spec)
