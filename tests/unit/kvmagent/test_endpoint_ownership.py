# -*- coding: utf-8 -*-
"""Static ownership checks for KVM agent HTTP endpoints."""

import os
import re


PLUGIN_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'kvmagent', 'kvmagent', 'plugins'))

OWNED_PATHS = (
    '/virtiofs/attach',
    '/virtiofs/detach',
)

ARTIFACT_VIEW_PATHS = (
    '/vm/artifactview/sync',
    '/vm/artifactview/delete',
    '/vm/artifactview/cleanup',
)


def _plugin_files():
    for name in os.listdir(PLUGIN_DIR):
        if name.endswith('.py'):
            yield os.path.join(PLUGIN_DIR, name)


def _read(path):
    with open(path, 'r') as fd:
        return fd.read()


def _count_registered_paths():
    counts = {}
    assignment_re = re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*[\'"]([^\'"]+)[\'"]', re.M)
    register_attr_re = re.compile(r'register_async_uri\(\s*self\.([A-Z][A-Z0-9_]*)')
    register_literal_re = re.compile(r'register_async_uri\(\s*[\'"]([^\'"]+)[\'"]')

    for path in _plugin_files():
        text = _read(path)
        constants = dict(assignment_re.findall(text))

        for literal in register_literal_re.findall(text):
            counts[literal] = counts.get(literal, 0) + 1

        for attr in register_attr_re.findall(text):
            literal = constants.get(attr)
            if literal:
                counts[literal] = counts.get(literal, 0) + 1

    return counts


def test_existing_endpoints_have_exactly_one_runtime_owner():
    counts = _count_registered_paths()

    for path in OWNED_PATHS:
        assert counts.get(path, 0) == 1


def test_artifact_view_endpoints_remain_unique():
    counts = _count_registered_paths()

    for path in ARTIFACT_VIEW_PATHS:
        assert counts.get(path, 0) == 1
