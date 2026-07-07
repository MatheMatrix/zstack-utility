# Copyright (c) 2025, ZStack, Inc.

import re
from xml.sax.saxutils import quoteattr as xml_quoteattr


DEFAULT_CACHE_MODE = 'none'
DEFAULT_QUEUE = 1024
DEFAULT_BINARY = '/usr/libexec/virtiofsd'
VALID_CACHE_MODES = ('none', 'auto', 'always')


def sanitize_tag(value):
    tag = re.sub(r'[^A-Za-z0-9_.-]', '_', str(value or 'artifact'))
    tag = tag.strip('._-')
    return tag[:96] if tag else 'artifact'


def normalize_cache_mode(cache_mode, default=DEFAULT_CACHE_MODE):
    if cache_mode in VALID_CACHE_MODES:
        return cache_mode
    return default


def normalize_queue(queue, default=DEFAULT_QUEUE):
    try:
        queue = int(queue)
        if queue <= 0:
            raise ValueError()
        return queue
    except Exception:
        return default


class VirtiofsDeviceSpec(object):
    def __init__(self, tag, source_path, cache_mode=None, queue=None,
                 binary_path=None, readonly=False, sandbox=True, xattr=True):
        if tag is None or str(tag) == '':
            raise Exception('tag is required')
        if not source_path:
            raise Exception('sourcePath is required')
        self.tag = str(tag)
        self.source_path = str(source_path)
        self.cache_mode = normalize_cache_mode(cache_mode)
        self.queue = normalize_queue(queue)
        self.binary_path = binary_path or DEFAULT_BINARY
        self.readonly = readonly is True
        self.sandbox = sandbox is not False
        self.xattr = xattr is not False


def build_filesystem_xml(spec):
    binary_attrs = " path=%s" % xml_quoteattr(spec.binary_path)
    if spec.xattr:
        binary_attrs += " xattr='on'"

    readonly_xml = "\n    <readonly/>" if spec.readonly else ""
    sandbox_xml = "\n        <sandbox mode='namespace'/>" if spec.sandbox else ""

    return '''<filesystem type='mount' accessmode='passthrough'>
    <driver type='virtiofs' queue='%s'/>
    <source dir=%s/>
    <target dir=%s/>
    <binary%s>
        <cache mode='%s'/>%s
    </binary>%s
</filesystem>''' % (
        spec.queue,
        xml_quoteattr(spec.source_path),
        xml_quoteattr(spec.tag),
        binary_attrs,
        spec.cache_mode,
        sandbox_xml,
        readonly_xml,
    )


def add_filesystem_element(devices, spec, element_factory):
    fs = element_factory(devices, 'filesystem', None, {'type': 'mount', 'accessmode': 'passthrough'})
    element_factory(fs, 'driver', None, {'type': 'virtiofs', 'queue': str(spec.queue)})
    binary_attrs = {'path': spec.binary_path}
    if spec.xattr:
        binary_attrs['xattr'] = 'on'
    binary = element_factory(fs, 'binary', None, binary_attrs)
    element_factory(binary, 'cache', None, {'mode': spec.cache_mode})
    if spec.sandbox:
        element_factory(binary, 'sandbox', None, {'mode': 'namespace'})
    element_factory(fs, 'source', None, {'dir': spec.source_path})
    element_factory(fs, 'target', None, {'dir': spec.tag})
    if spec.readonly:
        element_factory(fs, 'readonly')
    return fs


def build_virtiofs_xml(tag, source_path, cache_mode=None, queue=None,
                       binary_path=None, readonly=False, sandbox=True, xattr=True):
    spec = VirtiofsDeviceSpec(tag, source_path, cache_mode, queue, binary_path, readonly, sandbox, xattr)
    return build_filesystem_xml(spec)
