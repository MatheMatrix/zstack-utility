from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LockBackend(Enum):
    SANLOCK = "sanlock"
    FILE = "file"


@dataclass
class LockResource:
    name: str
    path: str
    backend: LockBackend = LockBackend.FILE
    host_id: int = 0
    version: int = 1


@dataclass
class LockHandle:
    resource: LockResource
    token: str
    held: bool = True
