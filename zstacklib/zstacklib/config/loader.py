from __future__ import annotations

import json
import os
from typing import Any

from .exceptions import ConfigLoadError, ConfigValidationError
from .models import ConfigData, ConfigFormat, ConfigSource


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return stream.read()
    except OSError as exc:
        raise ConfigLoadError(path, str(exc))


def _load_yaml(content: str, path: str) -> dict[str, Any]:
    try:
        import yaml
    except Exception as exc:
        raise ConfigLoadError(path, f"yaml unavailable: {exc}")
    try:
        data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            raise ConfigValidationError(path, "root must be a mapping")
        return data
    except ConfigValidationError:
        raise
    except Exception as exc:
        raise ConfigLoadError(path, str(exc))


def _load_json(content: str, path: str) -> dict[str, Any]:
    try:
        data = json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(path, str(exc))
    if not isinstance(data, dict):
        raise ConfigValidationError(path, "root must be a mapping")
    return data


def detect_format(path: str) -> ConfigFormat:
    lowered = path.lower()
    if lowered.endswith(".json"):
        return ConfigFormat.JSON
    if lowered.endswith(".yml") or lowered.endswith(".yaml"):
        return ConfigFormat.YAML
    raise ConfigValidationError(path, "unsupported config format")


def load_config(path: str, required: bool = True) -> ConfigData:
    if not os.path.exists(path):
        if required:
            raise ConfigLoadError(path, "file not found")
        source = ConfigSource(path=path, format=detect_format(path), required=False)
        return ConfigData(source=source, data={})

    fmt = detect_format(path)
    content = _read_file(path)
    if fmt == ConfigFormat.JSON:
        data = _load_json(content, path)
    else:
        data = _load_yaml(content, path)
    source = ConfigSource(path=path, format=fmt, required=required)
    return ConfigData(source=source, data=data)


def validate_required_fields(config: ConfigData, fields: list[str]) -> None:
    missing = [field for field in fields if field not in config.data]
    if missing:
        raise ConfigValidationError(config.source.path, f"missing required fields: {', '.join(missing)}")
