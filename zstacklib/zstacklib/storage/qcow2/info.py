# Copyright (c) ZStack.io, Inc.

"""
QCOW2 image information utilities.

Provides functions to query QCOW2 image metadata.
"""

import json
import logging
import os
import struct
from typing import Optional, Tuple

from zstacklib.utils import shell

from .exceptions import Qcow2FormatError, Qcow2InfoError


logger = logging.getLogger(__name__)

# QCOW2 magic number
QCOW2_MAGIC = b'QFI\xfb'

# Supported image formats
SUPPORTED_FORMATS = ['raw', 'qcow2', 'vmdk']


def _get_qemu_img_subcmd(subcmd):
    # type: (str) -> str
    """Get qemu-img subcommand with appropriate options.
    
    Tries to use the virtualization.qemu module if available,
    otherwise falls back to basic command.
    """
    try:
        from zstacklib.virtualization.qemu import build_subcmd
        return build_subcmd(subcmd)
    except ImportError:
        # Fallback for environments without the qemu module
        return 'qemu-img {} '.format(subcmd)


def get_image_format(path):
    # type: (str) -> str
    """Get the format of an image file.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Image format string ('raw', 'qcow2', 'vmdk').
        
    Raises:
        Qcow2FormatError: If format is unknown or unsupported.
    """
    cmd = "set -o pipefail; {} {} | grep -w '^file format' | awk '{{print $3}}'".format(
        _get_qemu_img_subcmd('info'), path
    )
    fmt = shell.call(cmd).strip(' \t\r\n')
    
    if fmt not in SUPPORTED_FORMATS:
        logger.debug('/usr/bin/qemu-img info %s', path)
        raise Qcow2FormatError(path, fmt)
    
    return fmt


def get_image_file_format(path):
    # type: (str) -> str
    """Get the format of an image file, detecting ISO files.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Image format string ('raw', 'qcow2', 'vmdk', 'iso').
    """
    fmt = get_image_format(path)
    if fmt == 'raw':
        result = shell.call("set -o pipefail; file {} | awk '{{print $2, $3}}'".format(path))
        if 'ISO' in result:
            return 'iso'
    return fmt


def get_image_info_json(path):
    # type: (str) -> dict
    """Get image information as JSON.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Dict with image information.
        
    Raises:
        Qcow2InfoError: If info cannot be retrieved.
    """
    cmd = shell.ShellCmd('set -o pipefail; {} {} --output=json'.format(
        _get_qemu_img_subcmd('info'), path
    ))
    cmd(False)
    
    if cmd.return_code != 0:
        raise Qcow2InfoError(
            path,
            'Cannot get info: {} {}'.format(cmd.stdout, cmd.stderr)
        )
    
    return json.loads(cmd.stdout.strip())


def get_virtual_and_actual_size(path):
    # type: (str) -> Tuple[Optional[int], Optional[int]]
    """Get the virtual size and actual disk usage of an image.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Tuple of (virtual_size, actual_size) in bytes.
        
    Raises:
        Qcow2InfoError: If sizes cannot be retrieved.
    """
    info = get_image_info_json(path)
    
    virtual_size = info.get('virtual-size')
    actual_size = info.get('actual-size')
    
    if virtual_size is None and actual_size is None:
        raise Qcow2InfoError(
            path,
            'Cannot get virtual/actual size from info'
        )
    
    return (int(virtual_size) if virtual_size else None,
            int(actual_size) if actual_size else None)


def get_virtual_size(path):
    # type: (str) -> int
    """Get the virtual size of an image.
    
    For local qcow2 files, reads directly from the header for efficiency.
    For remote images (e.g., RBD), uses qemu-img info.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Virtual size in bytes.
    """
    if not os.path.exists(path):
        # For remote images (e.g., RBD)
        out = shell.call(
            "{} {} | grep -P -o 'virtual size:\\K.*' | awk -F '[()a-zA-Z]' '{{print $3}}'".format(
                _get_qemu_img_subcmd('info'), path
            )
        )
        return int(out.strip())
    
    with open(path, 'rb') as f:
        magic = f.read(4)
        if magic != QCOW2_MAGIC:
            # Not a qcow2 file, return file size
            return os.path.getsize(path)
        
        # Read virtual size from qcow2 header (offset 24, 8 bytes, big-endian)
        f.seek(24)
        return struct.unpack('>Q', f.read(8))[0]


def get_virtual_size_via_info(path):
    # type: (str) -> int
    """Get virtual size using qemu-img info command.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Virtual size in bytes.
        
    Raises:
        Qcow2InfoError: If size cannot be retrieved.
    """
    cmd = shell.ShellCmd(
        "set -o pipefail; {} {} | grep -w 'virtual size' | awk -F '(' '{{print $2}}' | awk '{{print $1}}'".format(
            _get_qemu_img_subcmd('info'), path
        )
    )
    cmd(False)
    
    if cmd.return_code != 0:
        raise Qcow2InfoError(
            path,
            'Cannot get virtual size: {} {}'.format(cmd.stdout, cmd.stderr)
        )
    
    return int(cmd.stdout.strip())


def get_cluster_size(path):
    # type: (str) -> int
    """Get the cluster size of a qcow2 image.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Cluster size in bytes.
    """
    out = shell.call(
        "{} {} | grep 'cluster_size:' | cut -d ':' -f 2".format(
            _get_qemu_img_subcmd('info'), path
        )
    )
    return int(out.strip())


def get_backing_file(path):
    # type: (str) -> str
    """Get the backing file path of a qcow2 image.
    
    For local files, reads directly from the qcow2 header for efficiency.
    For remote images, uses qemu-img info.
    
    Args:
        path: Path to the image file.
        
    Returns:
        Backing file path, or empty string if no backing file.
    """
    if not os.path.exists(path):
        # For remote images (e.g., RBD)
        out = shell.call(
            "{} {} | grep 'backing file:' | cut -d ':' -f 2".format(
                _get_qemu_img_subcmd('info'), path
            )
        )
        return out.strip()
    
    with open(path, 'rb') as f:
        magic = f.read(4)
        if magic != QCOW2_MAGIC:
            return ''
        
        # Read backing file info from header
        f.seek(8)
        backing_file_info = f.read(12)
        backing_file_offset = struct.unpack('>Q', backing_file_info[:8])[0]
        
        if backing_file_offset == 0:
            return ''
        
        backing_file_size = struct.unpack('>I', backing_file_info[8:])[0]
        f.seek(backing_file_offset)
        return f.read(backing_file_size).decode('utf-8')


def get_backing_file_direct(path):
    # type: (str) -> str
    """Get backing file using direct I/O (for block devices).
    
    Args:
        path: Path to the image/device.
        
    Returns:
        Backing file path, or empty string if no backing file.
    """
    o = shell.call('dd if={} bs=4k count=1 iflag=direct'.format(path))
    o_bytes = o.encode('latin-1') if isinstance(o, str) else o
    
    if len(o_bytes) < 20 or o_bytes[:4] != QCOW2_MAGIC:
        return ''
    
    # Read backing file info from header
    backing_file_info = o_bytes[8:20]
    backing_file_offset = struct.unpack('>Q', backing_file_info[:8])[0]
    
    if backing_file_offset == 0:
        return ''
    
    backing_file_size = struct.unpack('>I', backing_file_info[8:])[0]
    return o_bytes[backing_file_offset:backing_file_offset + backing_file_size].decode('utf-8')


def measure_required_size(path):
    # type: (str) -> int
    """Measure the required size for converting an image to qcow2.
    
    Args:
        path: Path to the source image.
        
    Returns:
        Required size in bytes.
    """
    out = shell.call(
        "/usr/bin/qemu-img measure -f qcow2 -O qcow2 {} | grep 'required size' | cut -d ':' -f 2".format(path)
    )
    return int(out.strip())


def is_qcow2(path):
    # type: (str) -> bool
    """Check if a file is a qcow2 image.
    
    Args:
        path: Path to the file.
        
    Returns:
        True if the file is a qcow2 image.
    """
    if not os.path.exists(path):
        try:
            fmt = get_image_format(path)
            return fmt == 'qcow2'
        except Exception:
            return False
    
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
            return magic == QCOW2_MAGIC
    except Exception:
        return False
