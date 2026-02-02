from __future__ import annotations

import os
import uuid

from zstacklib.utils import shell

from .exceptions import LockAcquireError, LockNotHeldError, LockReleaseError
from .models import LockBackend, LockHandle, LockResource


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, 0o755, exist_ok=True)


def acquire_lock(resource: LockResource, timeout: int = 30) -> LockHandle:
    token = str(uuid.uuid4())
    if resource.backend == LockBackend.SANLOCK:
        cmd = f"sanlock direct acquire -r {resource.name}:{resource.path}:{resource.host_id}:{resource.version}"
        if timeout:
            cmd = f"timeout {timeout} {cmd}"
        result = shell.run(cmd)
        if result != 0:
            raise LockAcquireError(resource.name, "sanlock acquire failed")
        return LockHandle(resource=resource, token=token, held=True)

    _ensure_parent(resource.path)
    cmd = f"flock -w {timeout} {resource.path} -c 'true'"
    result = shell.run(cmd)
    if result != 0:
        raise LockAcquireError(resource.name, "file lock acquire failed")
    return LockHandle(resource=resource, token=token, held=True)


def release_lock(handle: LockHandle) -> None:
    if not handle.held:
        raise LockNotHeldError(handle.resource.name)

    resource = handle.resource
    if resource.backend == LockBackend.SANLOCK:
        cmd = f"sanlock direct release -r {resource.name}:{resource.path}:{resource.host_id}:{resource.version}"
        result = shell.run(cmd)
        if result != 0:
            raise LockReleaseError(resource.name, "sanlock release failed")
        handle.held = False
        return

    if not os.path.exists(resource.path):
        raise LockReleaseError(resource.name, "lock file does not exist")
    handle.held = False


def is_lock_held(handle: LockHandle) -> bool:
    return handle.held
