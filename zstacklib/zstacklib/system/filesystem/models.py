from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiskUsage:
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int

    @property
    def used_percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100


@dataclass
class MountInfo:
    device: str
    mount_point: str
    fs_type: str
    options: str


@dataclass
class FileInfo:
    path: str
    size_bytes: int
    is_file: bool
    is_dir: bool
    is_link: bool
    mode: int
    uid: int
    gid: int
    mtime: float
