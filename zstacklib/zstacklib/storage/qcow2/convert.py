# Copyright (c) ZStack.io, Inc.

"""
QCOW2 image conversion and rebase utilities.

Provides functions to convert between image formats and manage backing files.
"""

import logging
from typing import Optional

from zstacklib.utils import shell

from .info import get_image_format, _get_qemu_img_subcmd


logger = logging.getLogger(__name__)


def convert_qcow2_to_raw(src, dst):
    # type: (str, str) -> None
    """Convert a qcow2 image to raw format.
    
    Args:
        src: Source qcow2 image path.
        dst: Destination raw image path.
    """
    shell.call('{} -f qcow2 -O raw {} {}'.format(
        _get_qemu_img_subcmd('convert'), src, dst
    ))


def convert_raw_to_qcow2(src, dst, compress=False):
    # type: (str, str, bool) -> None
    """Convert a raw image to qcow2 format.
    
    Args:
        src: Source raw image path.
        dst: Destination qcow2 image path.
        compress: Whether to compress the output.
    """
    if compress:
        shell.call('{} -c -f raw -O qcow2 {} {}'.format(
            _get_qemu_img_subcmd('convert'), src, dst
        ))
    else:
        shell.call('{} -f raw -O qcow2 {} {}'.format(
            _get_qemu_img_subcmd('convert'), src, dst
        ))


def convert_qcow2_to_qcow2(src, dst, compress=False):
    # type: (str, str, bool) -> None
    """Convert a qcow2 image to another qcow2 (for compacting/compressing).
    
    Args:
        src: Source qcow2 image path.
        dst: Destination qcow2 image path.
        compress: Whether to compress the output.
    """
    if compress:
        shell.call('{} -c -f qcow2 -O qcow2 {} {}'.format(
            _get_qemu_img_subcmd('convert'), src, dst
        ))
    else:
        shell.call('{} -f qcow2 -O qcow2 {} {}'.format(
            _get_qemu_img_subcmd('convert'), src, dst
        ))


def create_template(src, dst, compress=False):
    # type: (str, str, bool) -> None
    """Create a template from an image (flatten and optionally compress).
    
    Automatically detects source format and creates a qcow2 template.
    
    Args:
        src: Source image path.
        dst: Destination template path.
        compress: Whether to compress the output.
        
    Raises:
        Qcow2FormatError: If source format is unknown.
    """
    fmt = get_image_format(src)
    
    if fmt == 'raw':
        convert_raw_to_qcow2(src, dst)
    elif fmt == 'qcow2':
        convert_qcow2_to_qcow2(src, dst, compress)
    else:
        from .exceptions import Qcow2FormatError
        raise Qcow2FormatError(src, fmt)


def rebase(path, backing_file, backing_fmt=None):
    # type: (str, str, Optional[str]) -> None
    """Rebase an image to a new backing file (safe mode).
    
    This performs a full comparison and data copy if needed.
    
    Args:
        path: Path to the image to rebase.
        backing_file: New backing file path.
        backing_fmt: Backing file format (auto-detected if None).
    """
    if backing_fmt is None:
        backing_fmt = get_image_format(backing_file)
    
    shell.call('{} -F {} -f qcow2 -b {} {}'.format(
        _get_qemu_img_subcmd('rebase'), backing_fmt, backing_file, path
    ))


def rebase_unsafe(path, backing_file, backing_fmt=None):
    # type: (str, str, Optional[str]) -> None
    """Rebase an image to a new backing file (unsafe mode).
    
    This assumes the old and new backing files have identical content
    and only updates the reference. Much faster but dangerous if
    backing file content differs.
    
    Args:
        path: Path to the image to rebase.
        backing_file: New backing file path.
        backing_fmt: Backing file format (auto-detected if None).
    """
    if backing_fmt is None:
        backing_fmt = get_image_format(backing_file)
    
    shell.call('{} -F {} -u -f qcow2 -b "{}" {}'.format(
        _get_qemu_img_subcmd('rebase'), backing_fmt, backing_file, path
    ))


def commit(path):
    # type: (str) -> None
    """Commit changes from an image to its backing file.
    
    Args:
        path: Path to the image.
    """
    shell.call('{} {}'.format(_get_qemu_img_subcmd('commit'), path))


def convert(src, dst, src_fmt=None, dst_fmt='qcow2', compress=False):
    # type: (str, str, Optional[str], str, bool) -> None
    """Convert an image from one format to another.
    
    Args:
        src: Source image path.
        dst: Destination image path.
        src_fmt: Source format (auto-detected if None).
        dst_fmt: Destination format.
        compress: Whether to compress (qcow2 only).
    """
    if src_fmt is None:
        src_fmt = get_image_format(src)
    
    compress_opt = '-c' if compress and dst_fmt == 'qcow2' else ''
    
    shell.call('{} {} -f {} -O {} {} {}'.format(
        _get_qemu_img_subcmd('convert'), compress_opt, src_fmt, dst_fmt, src, dst
    ))
