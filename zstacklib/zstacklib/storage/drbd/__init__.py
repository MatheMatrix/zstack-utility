# Copyright (c) ZStack.io, Inc.

"""
DRBD storage management module.

This module provides classes and functions for managing DRBD (Distributed
Replicated Block Device) resources, including configuration, lifecycle
management, and replication.

Example usage:
    from zstacklib.storage.drbd import DrbdResource, DrbdRole, OperateDrbd
    
    # Create and manage a resource
    resource = DrbdResource("myresource")
    
    # Use context manager for operations requiring Primary role
    with OperateDrbd(resource) as ctx:
        # resource is now Primary
        do_something_with_device(resource.get_dev_path())
    # resource is demoted back to Secondary
    
    # Check resource state
    if resource.get_role() == DrbdRole.Primary:
        print("Resource is Primary")
    
    # List active resources
    from zstacklib.storage.drbd import list_local_up_drbd
    resources = list_local_up_drbd()

Module structure:
    - exceptions: Exception classes (DrbdError, RetryException, etc.)
    - models: Data structures (DrbdRole, DrbdNetState, DrbdHostStruct, etc.)
    - config: Configuration management (DrbdConfigStruct, get_config_path_*)
    - resource: Resource management (DrbdResource, OperateDrbd)
    - utils: Utility functions (install_drbd, list_local_up_drbd, etc.)
"""

# Exceptions
from .exceptions import (
    DrbdError,
    RetryException,
    DrbdResourceNotFoundError,
    DrbdConfigError,
    DrbdPromoteError,
    DrbdDemoteError,
    DrbdConnectionError,
    DrbdMinorConflictError,
    DrbdInstallError,
)

# Models and constants
from .models import (
    DrbdRole,
    DrbdNetState,
    DrbdDiskState,
    DrbdStruct,
    DrbdHostStruct,
    DrbdNetStruct,
    DRBD_CONFIG_DIR,
    DRBD_GLOBAL_COMMON,
    DEFAULT_SPLIT_BRAIN_HANDLER,
    DEFAULT_FENCE_PEER_HANDLER,
    DEFAULT_FENCING,
)

# Configuration
from .config import (
    DrbdConfigStruct,
    get_config_path_from_disk,
    get_config_path_from_name,
    get_name_from_config_path,
)

# Resource management
from .resource import (
    DrbdResource,
    OperateDrbd,
)

# Utility functions
from .utils import (
    list_local_up_drbd,
    install_drbd,
    up_all_resources,
    is_drbd_available,
    get_drbd_version,
)

__all__ = [
    # Exceptions
    'DrbdError',
    'RetryException',
    'DrbdResourceNotFoundError',
    'DrbdConfigError',
    'DrbdPromoteError',
    'DrbdDemoteError',
    'DrbdConnectionError',
    'DrbdMinorConflictError',
    'DrbdInstallError',
    
    # Models and constants
    'DrbdRole',
    'DrbdNetState',
    'DrbdDiskState',
    'DrbdStruct',
    'DrbdHostStruct',
    'DrbdNetStruct',
    'DRBD_CONFIG_DIR',
    'DRBD_GLOBAL_COMMON',
    'DEFAULT_SPLIT_BRAIN_HANDLER',
    'DEFAULT_FENCE_PEER_HANDLER',
    'DEFAULT_FENCING',
    
    # Configuration
    'DrbdConfigStruct',
    'get_config_path_from_disk',
    'get_config_path_from_name',
    'get_name_from_config_path',
    
    # Resource management
    'DrbdResource',
    'OperateDrbd',
    
    # Utility functions
    'list_local_up_drbd',
    'install_drbd',
    'up_all_resources',
    'is_drbd_available',
    'get_drbd_version',
]
