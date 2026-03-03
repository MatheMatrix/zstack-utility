# Copyright (c) ZStack.io, Inc.

from __future__ import annotations

import os
import re
import socket

from zstacklib.utils import shell

from .exceptions import (
    InvalidNfsUrlError,
    InvalidMountDomainError,
    InvalidMountPathError,
    MountError,
)


MOUNT_TIMEOUT = 180


def is_mounted(path: str | None = None, url: str | None = None) -> bool:
    """Check is mounted."""
    if url:
        url = re.sub(r'/{2,}', '/', url.rstrip('/'))

    if url and path:
        cmdstr = f"mount | grep '{url} on ' | grep '{path} ' "
    elif not url:
        cmdstr = f"mount | grep '{path} '"
    elif not path:
        cmdstr = f"mount | grep '{url} on '"
    else:
        raise ValueError('path and url cannot both be None')

    return shell.run(cmdstr) == 0


def is_mounted_with_alternate_format(path: str | None = None, url: str | None = None) -> bool:
    """Check is mounted with alternate format."""
    mounted = is_mounted(path, url)
    if not url:
        return mounted

    if mounted:
        return True

    return is_mounted(path, url.replace(":/" , "://"))


def validate_nfs_url(url: str) -> bool:
    """Validate nfs url."""
    ts = url.split(':')
    if len(ts) != 2:
        raise InvalidNfsUrlError(url, 'url should have one and only one ":"')

    host = ts[0]
    path = ts[1]

    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        raise InvalidNfsUrlError(url, f'{host} cannot resolve to ip address')

    if not os.path.isabs(path):
        raise InvalidNfsUrlError(url, f'{path} is not an absolute path')

    return True


def check_mount_status(url: str, path: str, info: str | None = None) -> None:
    """Check mount status."""
    if not url or not path:
        raise ValueError('url and path are required')

    ts = url.split(':')
    if len(ts) != 2:
        raise InvalidNfsUrlError(url, 'url should have one and only one ":"')

    host = ts[0]
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        raise InvalidMountDomainError(url, f'{host} cannot resolve to ip address')

    if not os.path.exists(path):
        raise InvalidMountPathError(path, f'{path} does not exist on host')

    if info:
        if "ro," in info or "ro)" in info:
            raise InvalidMountPathError(path, f'{path} is read-only on host')


def mount(
    url: str,
    path: str,
    options: str | None = None,
    fstype: str | None = None,
    timeout: int = MOUNT_TIMEOUT
) -> None:
    """Mount."""
    cmd = shell.ShellCmd(f"mount | grep '{path}'")
    cmd(is_exception=False)
    if cmd.return_code == 0:
        raise MountError(url, f'{path} is occupied by another device. Details[{cmd.stdout}]')

    if not os.path.exists(path):
        os.makedirs(path, 0o755)

    cmdstr = "mount"

    if fstype and not options:
        cmdstr += f" -t {fstype}"

    if options:
        cmdstr += f" -o {options}"

    cmdstr = f"{cmdstr} {url} {path}"

    if "$" in cmdstr or ";" in cmdstr or "(" in cmdstr or "`" in cmdstr:
        raise MountError(url, f'unexpected options: {cmdstr}')

    o = shell.ShellCmd(f"timeout {timeout} {cmdstr}")
    o(False)
    if o.return_code == 124:
        raise MountError(url, f'mount timed out after {timeout}s')
    elif o.return_code != 0:
        raise MountError(url, f'mount failed: {cmdstr}')


def umount(path: str, raise_on_error: bool = True) -> bool:
    """Umount."""
    cmd = shell.ShellCmd(f'umount -f -l {path}')
    cmd(is_exception=raise_on_error)
    return cmd.return_code == 0


def remount(
    url: str,
    path: str,
    options: str | None = None,
    timeout: int = MOUNT_TIMEOUT
) -> None:
    """Remount."""
    if not is_mounted(path, url):
        mount(url, path, options)
        return

    o = shell.ShellCmd(f'timeout {timeout} mount -o remount {path}')
    o(False)
    if o.return_code == 124:
        raise MountError(url, f'remount timed out after {timeout}s for path [{path}]')
    elif o.return_code != 0:
        o.raise_error()


def get_mount_url(path: str) -> str | None:
    """Get mount url."""
    cmdstr = f"findmnt {path} | tail -1"
    cmd = shell.ShellCmd(cmdstr)
    out = cmd(is_exception=False)
    if out:
        parts = out.strip('\n').split(' ')
        if len(parts) >= 2:
            return parts[1]
    return None


def get_mounted_url_by_path(path: str) -> list[str]:
    """Get mounted url by path."""
    paths = []
    cmdstr = f"mount | grep '{path}'"
    cmd = shell.ShellCmd(cmdstr)
    out = cmd(is_exception=False)
    if cmd.return_code:
        return paths
    lst = out.split('\n')
    if '' in lst:
        lst.remove('')
    paths = [line.split(' ')[2] for line in lst]
    return paths


def get_mounted_paths_by_url(url: str) -> list[str]:
    """Get mounted paths by url."""
    paths = []
    if not is_mounted(url=url):
        return paths
    cmdstr = f"mount | grep '{url}'"
    cmd = shell.ShellCmd(cmdstr)
    out = cmd(is_exception=False)
    if cmd.return_code:
        return paths
    lst = out.split('\n')
    if '' in lst:
        lst.remove('')
    paths = [line.split(' ')[2] for line in lst]
    return paths


def umount_by_url(url: str) -> None:
    """Umount by url."""
    paths = get_mounted_paths_by_url(url)
    for p in paths:
        umount(p, raise_on_error=False)


def umount_by_path(path: str) -> None:
    """Umount by path."""
    paths = get_mounted_url_by_path(path)
    for p in paths:
        umount(p, raise_on_error=False)


def create_common_path(path: str, basepath: str) -> None:
    """Create common path."""
    if not path.startswith(basepath):
        raise ValueError(f'path [{path}] is not subdir of basepath [{basepath}]')

    if not is_mounted(basepath):
        raise MountError(basepath, f'the common path [{basepath}] is not mounted')

    if not os.path.exists(path):
        shell.call(f'mkdir -p {path}')


def get_mount_info(url: str) -> list[str]:
    """Get mount info."""
    if not url:
        raise ValueError('url is required')

    url = url.rstrip('/')
    cmdstr = f"mount | grep '/{url}'"
    cmd = shell.ShellCmd(cmdstr)
    cmd(is_exception=False)

    if cmd.return_code == 0:
        return str(cmd.stdout).strip().split("\n")
    else:
        raise RuntimeError(f'unable to execute mount on host: {cmd.stderr}')
