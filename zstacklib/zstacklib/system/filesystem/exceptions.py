from __future__ import annotations


class FileSystemError(Exception):
    pass


class MountError(FileSystemError):
    def __init__(self, path: str, message: str):
        super().__init__(f"Mount error for {path}: {message}")
        self.path = path


class DiskFullError(FileSystemError):
    def __init__(self, path: str, free_bytes: int):
        super().__init__(f"Disk full at {path}, only {free_bytes} bytes free")
        self.path = path
        self.free_bytes = free_bytes


class FileNotFoundError(FileSystemError):
    pass


class PermissionError(FileSystemError):
    pass
