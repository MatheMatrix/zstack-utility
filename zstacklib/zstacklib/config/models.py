from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfigFormat(Enum):
    JSON = "json"
    YAML = "yaml"


@dataclass
class ConfigSource:
    path: str
    format: ConfigFormat
    required: bool = True


@dataclass
class ConfigData:
    source: ConfigSource
    data: dict[str, Any] = field(default_factory=dict)
