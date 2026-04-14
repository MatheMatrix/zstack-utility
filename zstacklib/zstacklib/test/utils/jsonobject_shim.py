# -*- coding: utf-8 -*-
"""
Py3-native shim for zstacklib.utils.jsonobject.

The real jsonobject module depends on simplejson and uses Py2 types
(types.DictType, etc.).  This shim provides the same public API using
stdlib json, for use in the Py3 test environment.

Supported API:
    JsonObject  — attribute-access wrapper around dict
    loads(s)    — parse JSON string → JsonObject / list / primitive
    dumps(obj)  — serialize object → JSON string
"""
import json


class JsonObject:
    """Attribute-access wrapper matching the real JsonObject behavior."""

    def put(self, name, val):
        setattr(self, name, val)

    def dump(self):
        return json.dumps(self.__dict__, ensure_ascii=True)

    def hasattr(self, name):
        return getattr(self, name, None) is not None

    def __getitem__(self, name):
        return getattr(self, name)

    def __getattr__(self, name):
        # Allow trailing underscore as alias (e.g. obj.foo_ == obj.foo)
        if name.startswith('_'):
            raise AttributeError(name)
        if name.endswith('_'):
            n = name[:-1]
            try:
                return object.__getattribute__(self, n)
            except AttributeError:
                return None
        return None

    def __len__(self):
        return len(self.__dict__)

    def to_dict(self):
        return self.__dict__

    def __repr__(self):
        return 'JsonObject(%s)' % self.__dict__


def _parse_dict(d):
    obj = JsonObject()
    for k, v in d.items():
        if isinstance(v, dict):
            setattr(obj, k, _parse_dict(v))
        elif isinstance(v, list):
            setattr(obj, k, _parse_list(v))
        else:
            setattr(obj, k, v)
    return obj


def _parse_list(lst):
    result = []
    for item in lst:
        if isinstance(item, dict):
            result.append(_parse_dict(item))
        elif isinstance(item, list):
            result.append(_parse_list(item))
        else:
            result.append(item)
    return result


def loads(jstr):
    """Parse a JSON string into a JsonObject (or list/primitive)."""
    if jstr is None or (isinstance(jstr, str) and jstr.strip() == ''):
        return JsonObject()
    root = json.loads(jstr)
    if isinstance(root, dict):
        return _parse_dict(root)
    if isinstance(root, list):
        return _parse_list(root)
    return root


def _dump_obj(obj, include_protected_attr=False):
    """Recursively convert an object to a JSON-serializable dict."""
    if isinstance(obj, (bool, int, float, str)):
        return obj
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _dump_obj(v, include_protected_attr) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_dump_obj(v, include_protected_attr) for v in obj]
    # Object with __dict__
    ret = {}
    for k, v in obj.__dict__.items():
        if k.startswith('_') and not include_protected_attr:
            continue
        dumped = _dump_obj(v, include_protected_attr)
        if dumped is not None:
            ret[k] = dumped
    return ret


def dumps(obj, pretty=False, include_protected_attr=False):
    """Serialize an object to a JSON string."""
    data = _dump_obj(obj, include_protected_attr)
    if pretty:
        return json.dumps(data, ensure_ascii=True, sort_keys=True, indent=4)
    return json.dumps(data, ensure_ascii=True)


def nj():
    return JsonObject()


def from_dict(obj, include_protected_attr=False):
    return loads(dumps(obj, include_protected_attr=include_protected_attr))
