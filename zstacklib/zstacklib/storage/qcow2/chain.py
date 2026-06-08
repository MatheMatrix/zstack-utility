# Copyright (c) ZStack.io, Inc.

"""
QCOW2 backing file chain utilities.

Provides functions to work with qcow2 backing file chains.
"""

import abc
import os
import logging
from typing import Callable, List, Optional, Tuple

from zstacklib.utils import shell

from .info import get_backing_file, _get_qemu_img_subcmd
from .convert import rebase_unsafe


logger = logging.getLogger(__name__)


def get_file_chain(path):
    # type: (str) -> List[str]
    """Get the backing file chain of an image.
    
    Returns all images in the chain from the given image to the base.
    
    Args:
        path: Path to the image.
        
    Returns:
        List of image paths from derived to base.
    """
    out = shell.call(
        "{} --backing-chain {} | grep 'image:' | awk '{{print $2}}'".format(
            _get_qemu_img_subcmd('info'), path
        )
    )
    return out.splitlines()


def get_chain_size(path):
    # type: (str) -> int
    """Get the total disk usage of a backing file chain.
    
    Args:
        path: Path to the derived image.
        
    Returns:
        Total size in bytes of all images in the chain.
    """
    chain = get_file_chain(path)
    total_size = 0
    
    for image_path in chain:
        if os.path.exists(image_path):
            # Get actual disk usage
            out = shell.call("du -sb {} | awk '{{print $1}}'".format(image_path))
            total_size += int(out.strip())
    
    return total_size


def get_base_backing_file(path):
    # type: (str) -> str
    """Get the base (root) backing file of a chain.
    
    Args:
        path: Path to a derived image.
        
    Returns:
        Path to the base image (with no backing file).
    """
    chain = get_file_chain(path)
    return chain[-1] if chain else path


def find_base_image_in_cache(vol_dir, cache_dir):
    # type: (str, str) -> Optional[str]
    """Find the base image in a cache directory.
    
    Searches for qcow2 files in vol_dir that have backing files in cache_dir.
    
    Args:
        vol_dir: Volume installation directory.
        cache_dir: Image cache directory.
        
    Returns:
        Path to the base image, or None if not found.
        
    Raises:
        Exception: If multiple base images are found.
    """
    real_vol_dir = os.path.realpath(vol_dir)
    real_cache_dir = os.path.realpath(cache_dir)
    
    backing_files = shell.call(
        "set -o pipefail; find {} -type f -name '*.qcow2' -exec {} {{}} \\;| grep 'backing file:' | awk '{{print $3}}'".format(
            real_vol_dir, _get_qemu_img_subcmd('info')
        )
    ).splitlines()
    
    base_images = set()
    for backing_file in backing_files:
        if not backing_file:
            continue
        real_path = os.path.realpath(backing_file)
        if real_path.startswith(real_cache_dir):
            base_images.add(real_path)
    
    if len(base_images) == 1:
        return base_images.pop()
    elif len(base_images) == 0:
        return None
    else:
        raise Exception('More than one base image found in cache directory')


class AbstractFileConverter(object):
    """Abstract base class for file converters.
    
    Used for uploading/downloading image chains to/from different storage backends.
    """
    
    # Use ABCMeta for Python 2/3 compatibility
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def convert_to_file(self, src, dst):
        # type: (str, str) -> None
        """Convert a source to a local file."""
        pass

    @abc.abstractmethod
    def convert_from_file_with_backing(self, src, dst, backing, backing_fmt):
        # type: (str, str, str, str) -> int
        """Convert a local file to destination with backing file."""
        pass

    @abc.abstractmethod
    def get_backing_file(self, path):
        # type: (str) -> str
        """Get the backing file of an image."""
        pass

    @abc.abstractmethod
    def get_size(self, path):
        # type: (str) -> int
        """Get the size of an image."""
        pass

    @abc.abstractmethod
    def exists(self, path):
        # type: (str) -> bool
        """Check if an image exists."""
        pass


def upload_chain_to_filesystem(converter, first_node_path, dst_vol_dir, overwrite=False):
    # type: (AbstractFileConverter, str, str, bool) -> None
    """Upload a backing file chain to the local filesystem.
    
    Converts all images in the chain and rebases them to maintain the chain structure.
    
    Args:
        converter: FileConverter implementation.
        first_node_path: Path to the derived image.
        dst_vol_dir: Destination directory.
        overwrite: Whether to overwrite existing files.
    """
    from zstacklib.utils.linux import rm_file_force
    
    def upload(src_path):
        """Upload."""
        dst_path = os.path.join(dst_vol_dir, os.path.basename(src_path))
        if os.path.exists(dst_path):
            if overwrite:
                rm_file_force(dst_path)
            else:
                return dst_path
        
        converter.convert_to_file(src_path, dst_path)
        return dst_path
    
    dst_current = upload(first_node_path)
    parent_path = converter.get_backing_file(first_node_path)
    
    while parent_path:
        dst_parent = upload(parent_path)
        rebase_unsafe(dst_current, dst_parent)
        
        dst_current = dst_parent
        parent_path = converter.get_backing_file(parent_path)


def download_chain_from_filesystem(converter, first_node_path, dst_vol_dir, overwrite=False):
    # type: (AbstractFileConverter, str, str, bool) -> List[Tuple[str, int]]
    """Download a backing file chain from the local filesystem.
    
    Converts all images in the chain to the destination storage.
    
    Args:
        converter: FileConverter implementation.
        first_node_path: Path to the derived image.
        dst_vol_dir: Destination directory/path prefix.
        overwrite: Whether to overwrite existing files.
        
    Returns:
        List of (path, size) tuples for downloaded images.
    """
    from .info import get_image_format
    
    downloaded_chain = []  # type: List[Tuple[str, int]]
    
    def download(src_path, backing_file, backing_fmt):
        """Download."""
        dst_path = os.path.join(dst_vol_dir, os.path.basename(src_path))
        if converter.exists(dst_path):
            if overwrite:
                # Handle overwrite - implementation depends on converter
                pass
            else:
                size = converter.get_size(dst_path)
                return dst_path, size
        
        size = converter.convert_from_file_with_backing(
            src_path, dst_path, backing_file, backing_fmt
        )
        return dst_path, size
    
    # Build chain list (from base to derived)
    chain = []
    current = first_node_path
    while current:
        chain.append(current)
        current = get_backing_file(current)
    
    # Download from base to derived
    chain.reverse()
    prev_dst = ''
    prev_fmt = ''
    
    for src_path in chain:
        if prev_dst:
            prev_fmt = get_image_format(src_path)
        dst_path, size = download(src_path, prev_dst, prev_fmt)
        downloaded_chain.append((dst_path, size))
        prev_dst = dst_path
    
    return downloaded_chain
