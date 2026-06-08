# Copyright (c) ZStack.io, Inc.

"""
QCOW2 image format module.

Provides utilities for working with QCOW2 disk images including:
- Image information and metadata queries
- Image creation and cloning
- Format conversion and rebasing
- Backing file chain operations

Example usage:

    from zstacklib.storage import qcow2

    # Check if file is qcow2
    if qcow2.is_qcow2('/path/to/image.qcow2'):
        # Get image info
        size = qcow2.get_virtual_size('/path/to/image.qcow2')
        backing = qcow2.get_backing_file('/path/to/image.qcow2')

    # Create new image
    qcow2.create_qcow2('/path/to/new.qcow2', '10G')

    # Clone with backing file
    qcow2.clone_qcow2('/path/to/base.qcow2', '/path/to/derived.qcow2')

    # Convert formats
    qcow2.convert('/path/to/source.raw', '/path/to/dest.qcow2')
"""

# Exceptions
from .exceptions import (
    Qcow2Error,
    Qcow2FormatError,
    Qcow2InfoError,
    Qcow2CreateError,
    Qcow2ConvertError,
    Qcow2ChainError,
)

# Info functions
from .info import (
    QCOW2_MAGIC,
    SUPPORTED_FORMATS,
    get_image_format,
    get_image_file_format,
    get_image_info_json,
    get_virtual_size,
    get_virtual_size_via_info,
    get_virtual_and_actual_size,
    get_cluster_size,
    get_backing_file,
    get_backing_file_direct,
    measure_required_size,
    is_qcow2,
)

# Create functions
from .create import (
    DEFAULT_IMAGE_MODE,
    create_qcow2,
    create_raw,
    create_qcow2_with_backing,
    clone_qcow2,
    clone_raw,
    create_with_cmd,
    clone_with_cmd,
    create_backing_with_cmd,
    resize,
    fill,
    discard,
)

# Convert functions
from .convert import (
    convert,
    convert_qcow2_to_raw,
    convert_raw_to_qcow2,
    convert_qcow2_to_qcow2,
    create_template,
    rebase,
    rebase_unsafe,
    commit,
)

# Chain functions
from .chain import (
    get_file_chain,
    get_chain_size,
    get_base_backing_file,
    find_base_image_in_cache,
    AbstractFileConverter,
    upload_chain_to_filesystem,
    download_chain_from_filesystem,
)


__all__ = [
    # Exceptions
    'Qcow2Error',
    'Qcow2FormatError',
    'Qcow2InfoError',
    'Qcow2CreateError',
    'Qcow2ConvertError',
    'Qcow2ChainError',
    # Constants
    'QCOW2_MAGIC',
    'SUPPORTED_FORMATS',
    'DEFAULT_IMAGE_MODE',
    # Info
    'get_image_format',
    'get_image_file_format',
    'get_image_info_json',
    'get_virtual_size',
    'get_virtual_size_via_info',
    'get_virtual_and_actual_size',
    'get_cluster_size',
    'get_backing_file',
    'get_backing_file_direct',
    'measure_required_size',
    'is_qcow2',
    # Create
    'create_qcow2',
    'create_raw',
    'create_qcow2_with_backing',
    'clone_qcow2',
    'clone_raw',
    'create_with_cmd',
    'clone_with_cmd',
    'create_backing_with_cmd',
    'resize',
    'fill',
    'discard',
    # Convert
    'convert',
    'convert_qcow2_to_raw',
    'convert_raw_to_qcow2',
    'convert_qcow2_to_qcow2',
    'create_template',
    'rebase',
    'rebase_unsafe',
    'commit',
    # Chain
    'get_file_chain',
    'get_chain_size',
    'get_base_backing_file',
    'find_base_image_in_cache',
    'AbstractFileConverter',
    'upload_chain_to_filesystem',
    'download_chain_from_filesystem',
]
