# Copyright (c) ZStack.io, Inc.

"""
QCOW2 image creation utilities.

Provides functions to create qcow2 and raw disk images.
"""

import os
import re
import logging
from typing import Any, Optional

from zstacklib.utils import shell

from .info import get_image_format


logger = logging.getLogger(__name__)

# Default file permissions for created images
DEFAULT_IMAGE_MODE = 0o660


def create_qcow2(path, size, options=None):
    # type: (str, str, Optional[str]) -> None
    """Create a new qcow2 image.
    
    Args:
        path: Path for the new image.
        size: Size string (e.g., '10G', '100M').
        options: Additional qemu-img options (e.g., '-o preallocation=metadata').
    """
    if options:
        cmd = '/usr/bin/qemu-img create -f qcow2 {} {} {}'.format(options, path, size)
    else:
        cmd = '/usr/bin/qemu-img create -f qcow2 {} {}'.format(path, size)
    
    shell.check_run(cmd)
    os.chmod(path, DEFAULT_IMAGE_MODE)


def create_raw(path, size):
    # type: (str, str) -> None
    """Create a new raw image.
    
    Args:
        path: Path for the new image.
        size: Size string (e.g., '10G', '100M').
    """
    shell.check_run('/usr/bin/qemu-img create -f raw {} {}'.format(path, size))
    os.chmod(path, DEFAULT_IMAGE_MODE)


def create_qcow2_with_backing(backing_file, path, size=None, options=None):
    # type: (str, str, Optional[str], Optional[str]) -> None
    """Create a qcow2 image with a backing file.
    
    Args:
        backing_file: Path to the backing file.
        path: Path for the new image.
        size: Optional size override.
        options: Additional qemu-img options.
    """
    backing_fmt = get_image_format(backing_file)
    
    # Remove preallocation option (not compatible with backing files)
    if options:
        pattern = re.compile(r'-o\s+preallocation=\w+\s*')
        options = re.sub(pattern, ' ', options)
    
    size_arg = size or ''
    opt_arg = options or ''
    
    cmd = '/usr/bin/qemu-img create -F {} {} -b {} -f qcow2 {} {}'.format(
        backing_fmt, opt_arg, backing_file, path, size_arg
    )
    
    shell.call(cmd)
    os.chmod(path, DEFAULT_IMAGE_MODE)


def clone_qcow2(src, dst, size=None):
    # type: (str, str, Optional[str]) -> None
    """Clone a qcow2 image (create with backing file).
    
    Args:
        src: Source image path (becomes backing file).
        dst: Destination image path.
        size: Optional size override.
    """
    create_qcow2_with_backing(src, dst, size)


def clone_raw(src, dst):
    # type: (str, str) -> None
    """Clone a raw image (create with backing file).
    
    Args:
        src: Source image path (becomes backing file).
        dst: Destination image path.
    """
    shell.check_run('/usr/bin/qemu-img create -b {} -f raw {}'.format(src, dst))
    os.chmod(dst, DEFAULT_IMAGE_MODE)


def create_with_cmd(path, size, cmd=None):
    # type: (str, str, Optional[Any]) -> None
    """Create a qcow2 image using optional command config.
    
    Args:
        path: Path for the new image.
        size: Size string.
        cmd: Command object with optional kvmHostAddons.qcow2Options.
    """
    if cmd is None:
        create_qcow2(path, size)
        return
    
    kvm_addons = getattr(cmd, 'kvmHostAddons', None)
    if kvm_addons is None:
        create_qcow2(path, size)
        return
    
    qcow2_options = getattr(kvm_addons, 'qcow2Options', None)
    if qcow2_options is None:
        create_qcow2(path, size)
    else:
        create_qcow2(path, size, options=qcow2_options)


def clone_with_cmd(src, dst, cmd=None):
    # type: (str, str, Optional[Any]) -> None
    """Clone an image using optional command config.
    
    Args:
        src: Source image path.
        dst: Destination image path.
        cmd: Command object with optional virtualSize and kvmHostAddons.qcow2Options.
    """
    if cmd is None:
        clone_qcow2(src, dst)
        return
    
    size = getattr(cmd, 'virtualSize', None)
    kvm_addons = getattr(cmd, 'kvmHostAddons', None)
    
    if kvm_addons is None:
        clone_qcow2(src, dst, size)
        return
    
    qcow2_options = getattr(kvm_addons, 'qcow2Options', None)
    if qcow2_options is None:
        clone_qcow2(src, dst, size)
    else:
        create_qcow2_with_backing(src, dst, size, qcow2_options)


def create_backing_with_cmd(backing_file, path, cmd=None, size=None):
    # type: (str, str, Optional[Any], Optional[str]) -> None
    """Create a qcow2 with backing file using optional command config.
    
    Args:
        backing_file: Backing file path.
        path: New image path.
        cmd: Command object with optional kvmHostAddons.qcow2Options.
        size: Optional size override.
    """
    if cmd is None:
        create_qcow2_with_backing(backing_file, path, size)
        return
    
    kvm_addons = getattr(cmd, 'kvmHostAddons', None)
    if kvm_addons is None:
        create_qcow2_with_backing(backing_file, path, size)
        return
    
    qcow2_options = getattr(kvm_addons, 'qcow2Options', None)
    if qcow2_options is None:
        create_qcow2_with_backing(backing_file, path, size)
    else:
        create_qcow2_with_backing(backing_file, path, size, qcow2_options)


def resize(path, size, fmt='qcow2', shrink=False):
    # type: (str, str, str, bool) -> None
    """Resize an image.
    
    Args:
        path: Path to the image.
        size: New size (e.g., '+10G', '100G').
        fmt: Image format.
        shrink: Allow shrinking (dangerous).
    """
    fmt_option = '-f {}'.format(fmt)
    shrink_option = '--shrink' if shrink else ''
    
    shell.check_run('/usr/bin/qemu-img resize {} {} {} {}'.format(
        fmt_option, shrink_option, path, size
    ))


def fill(path, offset, length, raise_exception=False):
    # type: (str, int, int, bool) -> None
    """Write zeros to a region of a qcow2 image.
    
    Args:
        path: Path to the image.
        offset: Start offset in bytes.
        length: Length to fill in bytes.
        raise_exception: Whether to raise on error.
    """
    cmd = shell.ShellCmd("qemu-io -c 'write {} {}' {} -n".format(offset, length, path))
    cmd(raise_exception)
    logger.debug('qcow2_fill return code: %s, stdout: %s, stderr: %s',
                 cmd.return_code, cmd.stdout, cmd.stderr)


def discard(path):
    # type: (str) -> None
    """Discard unused blocks in a qcow2 image.
    
    Args:
        path: Path to the image.
    """
    from .info import get_virtual_size
    
    virtual_size = get_virtual_size(path)
    chunk_size = 2145386496  # ~2GB chunks
    
    script = '''#!/bin/bash
i=0
while(($i < {0}))
do
qemu-io -c "discard $[i*{1}] {1}" -f qcow2 -d unmap {2}
let i+=1
done
qemu-io -c "discard $[i*{1}] {3}" -f qcow2 -d unmap {2}
'''.format(virtual_size // chunk_size, chunk_size, path, virtual_size % chunk_size)
    
    cmd = shell.ShellCmd(script)
    cmd(False)
    logger.debug('qcow2 discard return code: %s, stderr: %s', cmd.return_code, cmd.stderr)
