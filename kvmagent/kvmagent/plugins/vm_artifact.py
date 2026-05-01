import os
import re
import shutil
import tempfile

try:
    from shlex import quote as shell_quote
except ImportError:
    from pipes import quote as shell_quote

import libvirt

from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import log

logger = log.get_logger(__name__)

MODEL_CENTER_ROOT = '/var/lib/zstack/aios/model-centers'
VM_VIEW_ROOT = '/var/lib/zstack/aios/vm-views'

DEFAULT_VIRTIOFS_CACHE = 'none'
DEFAULT_VIRTIOFS_QUEUE = 1024
DEFAULT_VIRTIOFS_BINARY = '/usr/libexec/virtiofsd'

ADDON_VM_ARTIFACT_VIEWS = 'vmArtifactViews'


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


def get_addon(addons, name, default=None):
    if addons is None:
        return default
    if isinstance(addons, dict):
        return addons.get(name, default)
    try:
        if addons.hasattr(name):
            return getattr(addons, name)
    except Exception:
        pass
    return default


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def safe_uuid(value, field_name):
    if not value or not re.match(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', value):
        raise Exception('invalid %s: %s' % (field_name, value))
    return value


def sanitize_tag(value):
    tag = re.sub(r'[^A-Za-z0-9_.-]', '_', str(value or 'artifact'))
    tag = tag.strip('._-')
    return tag[:96] if tag else 'artifact'


def ensure_under(path, root, field_name):
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    if real_path != real_root and not real_path.startswith(real_root + os.sep):
        raise Exception('%s[%s] is outside allowed root[%s]' % (field_name, path, root))
    return real_path


def safe_join(root, *paths):
    for p in paths:
        if p is None:
            continue
        if os.path.isabs(str(p)):
            raise Exception('absolute path component is not allowed: %s' % p)

    joined = os.path.join(root, *[str(p) for p in paths if p is not None and str(p) != ''])
    return ensure_under(joined, root, 'path')


def validate_relative_path(path, field_name):
    if path is None or str(path).strip() == '':
        raise Exception('%s cannot be empty' % field_name)
    path = str(path).strip().lstrip('/')
    if os.path.isabs(path) or path == '..' or path.startswith('../') or '/../' in path or path.endswith('/..'):
        raise Exception('%s[%s] escapes its root' % (field_name, path))
    return path


def vm_view_root(vm_uuid):
    return safe_join(VM_VIEW_ROOT, safe_uuid(vm_uuid, 'vmInstanceUuid'))


def model_center_mount_point(model_center_uuid):
    return safe_join(MODEL_CENTER_ROOT, safe_uuid(model_center_uuid, 'modelCenterUuid'))


def artifact_source_path(artifact):
    source_path = get_attr(artifact, 'sourcePath')
    if source_path:
        return ensure_under(source_path, MODEL_CENTER_ROOT, 'sourcePath')

    model_center_uuid = get_attr(artifact, 'modelCenterUuid')
    install_path = validate_relative_path(get_attr(artifact, 'installPath'), 'installPath')
    return safe_join(model_center_mount_point(model_center_uuid), install_path)


def artifact_relative_path(artifact):
    relative_path = get_attr(artifact, 'relativePath')
    if relative_path:
        return validate_relative_path(relative_path, 'relativePath')

    artifact_uuid = get_attr(artifact, 'artifactUuid') or get_attr(artifact, 'uuid') or get_attr(artifact, 'name')
    return sanitize_tag(artifact_uuid)


def make_view_bind_specs(vm_uuid, artifacts):
    root = vm_view_root(vm_uuid)
    specs = []
    for artifact in as_list(artifacts):
        source = artifact_source_path(artifact)
        relative = artifact_relative_path(artifact)
        target = safe_join(root, relative)
        read_only = get_attr(artifact, 'readOnly', True)
        specs.append({
            'sourcePath': source,
            'targetPath': target,
            'relativePath': relative,
            'readOnly': read_only is not False,
            'artifactUuid': get_attr(artifact, 'artifactUuid') or get_attr(artifact, 'uuid'),
            'name': get_attr(artifact, 'name'),
        })
    return root, specs


def _mkdir_for_bind_target(source_path, target_path):
    parent = os.path.dirname(target_path)
    linux.mkdir(parent, 0o755)
    if os.path.isfile(source_path):
        if not os.path.exists(target_path):
            open(target_path, 'a').close()
    else:
        linux.mkdir(target_path, 0o755)


def bind_readonly(source_path, target_path, read_only=True):
    ensure_under(source_path, MODEL_CENTER_ROOT, 'sourcePath')
    ensure_under(target_path, VM_VIEW_ROOT, 'targetPath')
    if not os.path.exists(source_path):
        raise Exception('sourcePath[%s] does not exist' % source_path)

    _mkdir_for_bind_target(source_path, target_path)
    if not linux.is_mounted(path=target_path):
        ret = bash.bash_r('mount --bind %s %s' % (shell_quote(source_path), shell_quote(target_path)))
        if ret != 0:
            raise Exception('failed to bind mount %s to %s' % (source_path, target_path))

    if read_only:
        ret = bash.bash_r('mount -o remount,bind,ro %s' % shell_quote(target_path))
        if ret != 0:
            raise Exception('failed to remount %s as readonly bind' % target_path)


def _mountinfo_target(line):
    parts = line.split(' - ', 1)[0].split()
    return parts[4] if len(parts) > 4 else None


def list_mounts_under(root):
    root = os.path.realpath(root)
    mounts = []
    try:
        with open('/proc/self/mountinfo') as fd:
            for line in fd:
                target = _mountinfo_target(line)
                if target and (target == root or target.startswith(root + os.sep)):
                    mounts.append(target)
    except IOError:
        return []
    mounts.sort(key=lambda p: len(p), reverse=True)
    return mounts


def unmount_if_needed(path):
    if linux.is_mounted(path=path):
        linux.umount(path, is_exception=False)


def remove_path(path):
    ensure_under(path, VM_VIEW_ROOT, 'path')
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def cleanup_view(vm_uuid, keep_paths=None):
    root = vm_view_root(vm_uuid)
    keep = set([os.path.realpath(p) for p in (keep_paths or [])])
    def should_keep(path):
        real_path = os.path.realpath(path)
        if real_path in keep:
            return True
        for keep_path in keep:
            if keep_path.startswith(real_path + os.sep):
                return True
        return False

    if not os.path.exists(root):
        linux.mkdir(root, 0o755)
        return root

    for mount in list_mounts_under(root):
        if not should_keep(mount):
            unmount_if_needed(mount)

    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not should_keep(path):
            remove_path(path)
    return root


def sync_artifact_view(vm_uuid, artifacts):
    root, specs = make_view_bind_specs(vm_uuid, artifacts)
    linux.mkdir(root, 0o755)
    target_paths = []
    for spec in specs:
        bind_readonly(spec['sourcePath'], spec['targetPath'], spec['readOnly'])
        target_paths.append(spec['targetPath'])
    cleanup_view(vm_uuid, target_paths)
    return root, specs


def virtiofs_source_path(vm_uuid, source_path=None):
    root = vm_view_root(vm_uuid)
    if source_path:
        return ensure_under(source_path, root, 'sourcePath')
    return root


def build_virtiofs_device_xml(vm_uuid, tag, source_path=None, cache=None, queue=None, binary_path=None, readonly=True):
    from xml.etree.ElementTree import Element, SubElement, tostring

    source_path = virtiofs_source_path(vm_uuid, source_path)
    tag = sanitize_tag(tag)
    cache = cache or DEFAULT_VIRTIOFS_CACHE
    queue = str(queue or DEFAULT_VIRTIOFS_QUEUE)
    binary_path = binary_path or DEFAULT_VIRTIOFS_BINARY

    fs = Element('filesystem', {'type': 'mount', 'accessmode': 'passthrough'})
    SubElement(fs, 'driver', {'type': 'virtiofs', 'queue': queue})
    binary = SubElement(fs, 'binary', {'path': binary_path})
    SubElement(binary, 'cache', {'mode': cache})
    SubElement(fs, 'source', {'dir': source_path})
    SubElement(fs, 'target', {'dir': tag})
    if readonly:
        SubElement(fs, 'readonly')
    return tostring(fs, encoding='unicode')


def add_virtiofs_devices(devices, views, element_factory):
    for view in as_list(views):
        vm_uuid = get_attr(view, 'vmInstanceUuid')
        tag = get_attr(view, 'tag') or get_attr(view, 'mountTag') or get_attr(view, 'artifactUuid') or vm_uuid
        artifacts = get_attr(view, 'artifacts')
        if artifacts:
            source_path, _ = sync_artifact_view(vm_uuid, artifacts)
        else:
            source_path = get_attr(view, 'sourcePath') or get_attr(view, 'viewPath')
        source_path = virtiofs_source_path(vm_uuid, source_path)
        cache = get_attr(view, 'cache', DEFAULT_VIRTIOFS_CACHE) or DEFAULT_VIRTIOFS_CACHE
        queue = str(get_attr(view, 'queue', DEFAULT_VIRTIOFS_QUEUE) or DEFAULT_VIRTIOFS_QUEUE)
        binary_path = get_attr(view, 'binaryPath', DEFAULT_VIRTIOFS_BINARY) or DEFAULT_VIRTIOFS_BINARY
        readonly = get_attr(view, 'readOnly', True) is not False

        fs = element_factory(devices, 'filesystem', None, {'type': 'mount', 'accessmode': 'passthrough'})
        element_factory(fs, 'driver', None, {'type': 'virtiofs', 'queue': queue})
        binary = element_factory(fs, 'binary', None, {'path': binary_path})
        element_factory(binary, 'cache', None, {'mode': cache})
        element_factory(fs, 'source', None, {'dir': source_path})
        element_factory(fs, 'target', None, {'dir': sanitize_tag(tag)})
        if readonly:
            element_factory(fs, 'readonly')


def attach_virtiofs(domain, vm_uuid, tag, source_path=None, cache=None, queue=None):
    xml = build_virtiofs_device_xml(vm_uuid, tag, source_path, cache, queue)
    domain.attachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_LIVE)
    return xml


def detach_virtiofs(domain, domain_xmlobject, tag):
    tag = sanitize_tag(tag)
    for fs in domain_xmlobject.devices.get_child_node_as_list('filesystem'):
        if get_attr(get_attr(fs, 'target'), 'dir_') == tag:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                tmp.write(fs.dump().encode('utf-8'))
                tmp.close()
                domain.detachDeviceFlags(fs.dump(), libvirt.VIR_DOMAIN_AFFECT_LIVE)
            finally:
                try:
                    os.remove(tmp.name)
                except OSError:
                    pass
            return True
    return False
