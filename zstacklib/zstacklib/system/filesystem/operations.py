from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .models import DiskUsage, FileInfo, MountInfo


def mkdir_p(path: str | Path, mode: int = 0o755) -> None:
    Path(path).mkdir(parents=True, exist_ok=True, mode=mode)


def rmdir_recursive(path: str | Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def read_file(path: str | Path) -> str:
    return Path(path).read_text()


def read_file_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def write_file(path: str | Path, content: str, mode: int = 0o644) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    os.chmod(p, mode)


def write_file_bytes(path: str | Path, content: bytes, mode: int = 0o644) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    os.chmod(p, mode)


def safe_write(path: str | Path, content: str, mode: int = 0o644) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=p.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp_path, mode)
        os.rename(tmp_path, p)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def copy_file(src: str | Path, dst: str | Path) -> None:
    shutil.copy2(src, dst)


def move_file(src: str | Path, dst: str | Path) -> None:
    shutil.move(src, dst)


def get_disk_usage(path: str | Path) -> DiskUsage:
    stat = os.statvfs(path)
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = total - free
    return DiskUsage(
        path=str(path),
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
    )


def get_free_space(path: str | Path) -> int:
    return get_disk_usage(path).free_bytes


def get_file_info(path: str | Path) -> FileInfo:
    p = Path(path)
    stat = p.stat()
    return FileInfo(
        path=str(p),
        size_bytes=stat.st_size,
        is_file=p.is_file(),
        is_dir=p.is_dir(),
        is_link=p.is_symlink(),
        mode=stat.st_mode,
        uid=stat.st_uid,
        gid=stat.st_gid,
        mtime=stat.st_mtime,
    )


def list_files(path: str | Path, pattern: str = "*") -> list[Path]:
    return list(Path(path).glob(pattern))


def get_mounts() -> list[MountInfo]:
    mounts = []
    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                mounts.append(MountInfo(
                    device=parts[0],
                    mount_point=parts[1],
                    fs_type=parts[2],
                    options=parts[3],
                ))
    return mounts


def is_mounted(path: str) -> bool:
    path = os.path.abspath(path)
    for mount in get_mounts():
        if mount.mount_point == path:
            return True
    return False
