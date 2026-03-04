from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProcessState(str, Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    UNKNOWN = "unknown"


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cmdline: str = ""
    state: ProcessState = ProcessState.UNKNOWN
    ppid: int = 0
    uid: int = 0
    memory_rss_kb: int = 0
    cpu_percent: float = 0.0
