# Copyright (c) ZStack.io, Inc.

"""
qemu-img command wrapper.

Provides functions for working with QEMU disk images.
"""

import json
import logging
from distutils.version import LooseVersion
from typing import List, Optional

from zstacklib.utils import shell

from .models import QemuImgCheckResult


logger = logging.getLogger(__name__)

# Cached qemu-img version
_QEMU_IMG_VERSION = None  # type: Optional[str]

# Subcommands that support --force-share option (QEMU 2.10+)
FORCE_SHARE_SUBCMDS = ['info', 'check', 'compare', 'convert', 'rebase']


def get_qemu_img_version():
    # type: () -> str
    """Get the qemu-img version.
    
    Returns:
        Version string (e.g., '2.12.0').
    """
    global _QEMU_IMG_VERSION
    if _QEMU_IMG_VERSION is None:
        command = "qemu-img --version | grep 'qemu-img version' | cut -d ' ' -f 3 | cut -d '(' -f 1"
        _QEMU_IMG_VERSION = shell.call(command).strip('\t\r\n ,')
    return _QEMU_IMG_VERSION


def build_subcmd(subcmd, force_share=True):
    # type: (str, bool) -> str
    """Build a qemu-img subcommand with appropriate options.
    
    Automatically adds --force-share for QEMU 2.10+ when applicable.
    
    Args:
        subcmd: The subcommand (e.g., 'info', 'check', 'convert').
        force_share: Whether to add --force-share option.
        
    Returns:
        Complete qemu-img command prefix.
    """
    version = get_qemu_img_version()
    options = ''
    
    if force_share and LooseVersion(version) >= LooseVersion('2.10.0'):
        if subcmd in FORCE_SHARE_SUBCMDS:
            options = ' --force-share '
    
    return 'qemu-img {} {} '.format(subcmd, options)


def check_image(path):
    # type: (str) -> QemuImgCheckResult
    """Run qemu-img check on an image file.
    
    Args:
        path: Path to the image file.
        
    Returns:
        QemuImgCheckResult with check results.
        
    Raises:
        Exception: If the check command fails.
    """
    check_cmd = "{}--output json {}".format(build_subcmd('check'), path)
    output = shell.call(check_cmd)
    result = json.loads(output)
    
    return QemuImgCheckResult(
        image_end_offset=result.get('image-end-offset'),
        total_clusters=result.get('total-clusters'),
        check_errors=result.get('check-errors'),
        allocated_clusters=result.get('allocated-clusters'),
        filename=result.get('filename'),
        format=result.get('format')
    )


def get_image_info(path, output_format='json'):
    # type: (str, str) -> dict
    """Get information about an image file.
    
    Args:
        path: Path to the image file.
        output_format: Output format ('json' or 'human').
        
    Returns:
        Dict with image information.
    """
    cmd = "{}--output {} {}".format(build_subcmd('info'), output_format, path)
    output = shell.call(cmd)
    
    if output_format == 'json':
        return json.loads(output)
    return {'raw_output': output}


def create_image(path, size, fmt='qcow2', backing_file=None, backing_fmt=None):
    # type: (str, str, str, Optional[str], Optional[str]) -> None
    """Create a new disk image.
    
    Args:
        path: Path for the new image.
        size: Size of the image (e.g., '10G', '100M').
        fmt: Image format (default: 'qcow2').
        backing_file: Path to backing file for COW image.
        backing_fmt: Format of the backing file.
    """
    cmd_parts = ['qemu-img create', '-f', fmt]
    
    if backing_file:
        cmd_parts.extend(['-b', backing_file])
        if backing_fmt:
            cmd_parts.extend(['-F', backing_fmt])
    
    cmd_parts.extend([path, size])
    
    shell.call(' '.join(cmd_parts))


def convert_image(src_path, dst_path, src_fmt=None, dst_fmt='qcow2', 
                  compress=False, sparse_size=None):
    # type: (str, str, Optional[str], str, bool, Optional[str]) -> None
    """Convert an image from one format to another.
    
    Args:
        src_path: Source image path.
        dst_path: Destination image path.
        src_fmt: Source format (auto-detected if None).
        dst_fmt: Destination format (default: 'qcow2').
        compress: Whether to compress the output (qcow2 only).
        sparse_size: Sparse file detection size.
    """
    cmd_parts = [build_subcmd('convert')]
    
    if src_fmt:
        cmd_parts.extend(['-f', src_fmt])
    
    cmd_parts.extend(['-O', dst_fmt])
    
    if compress and dst_fmt == 'qcow2':
        cmd_parts.append('-c')
    
    if sparse_size:
        cmd_parts.extend(['-S', sparse_size])
    
    cmd_parts.extend([src_path, dst_path])
    
    shell.call(' '.join(cmd_parts))


def resize_image(path, size):
    # type: (str, str) -> None
    """Resize an image.
    
    Args:
        path: Path to the image.
        size: New size (e.g., '+10G', '100G').
    """
    cmd = 'qemu-img resize {} {}'.format(path, size)
    shell.call(cmd)


def snapshot_image(path, snapshot_name, action='create'):
    # type: (str, str, str) -> None
    """Manage internal snapshots.
    
    Args:
        path: Path to the image.
        snapshot_name: Name of the snapshot.
        action: 'create', 'apply', 'delete', or 'list'.
    """
    action_flags = {
        'create': '-c',
        'apply': '-a',
        'delete': '-d',
        'list': '-l',
    }
    
    if action not in action_flags:
        raise ValueError('Invalid action: {}'.format(action))
    
    if action == 'list':
        cmd = 'qemu-img snapshot {} {}'.format(action_flags[action], path)
    else:
        cmd = 'qemu-img snapshot {} {} {}'.format(
            action_flags[action], snapshot_name, path
        )
    
    shell.call(cmd)


def rebase_image(path, backing_file, backing_fmt=None, unsafe=False):
    # type: (str, str, Optional[str], bool) -> None
    """Rebase an image to a new backing file.
    
    Args:
        path: Path to the image.
        backing_file: New backing file path.
        backing_fmt: Format of the backing file.
        unsafe: Use unsafe rebase (faster but requires identical old backing).
    """
    cmd_parts = [build_subcmd('rebase')]
    
    if unsafe:
        cmd_parts.append('-u')
    
    if backing_fmt:
        cmd_parts.extend(['-F', backing_fmt])
    
    cmd_parts.extend(['-b', backing_file, path])
    
    shell.call(' '.join(cmd_parts))


def commit_image(path):
    # type: (str) -> None
    """Commit changes from a COW image to its backing file.
    
    Args:
        path: Path to the COW image.
    """
    cmd = 'qemu-img commit {}'.format(path)
    shell.call(cmd)
