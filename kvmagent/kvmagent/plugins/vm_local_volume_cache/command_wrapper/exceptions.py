"""
Custom exception classes for vm_local_volume_cache module.
Provides fine-grained error classification for pool and cache operations.
"""


class VmLocalVolumeCacheError(Exception):
    """Base exception for all vm_local_volume_cache errors."""
    pass


# ============================================================================
# Pool Exceptions
# ============================================================================

class PoolNotInitializedError(VmLocalVolumeCacheError):
    """Raised when a pool operation requires an initialized pool but the pool is not initialized."""
    pass


class PoolNotFoundError(VmLocalVolumeCacheError):
    """Raised when a requested pool processor does not exist."""
    pass


class PoolOperationError(VmLocalVolumeCacheError):
    """Raised when a pool operation (create/connect/extend/delete) fails."""
    pass


# ============================================================================
# Cache Exceptions
# ============================================================================

class CacheNotInstantiatedError(VmLocalVolumeCacheError):
    """Raised when a cache file is expected to exist but has not been instantiated."""
    pass


class CacheOperationError(VmLocalVolumeCacheError):
    """Raised when a cache operation (create/flush/delete) fails."""
    pass


# ============================================================================
# Volume / Device Exceptions
# ============================================================================

class UnsupportedDeviceTypeError(VmLocalVolumeCacheError):
    """Raised when the backing volume device type is not supported."""
    pass


class VolumeValidationError(VmLocalVolumeCacheError):
    """Raised when volume parameters fail validation (e.g. missing required fields)."""
    pass
