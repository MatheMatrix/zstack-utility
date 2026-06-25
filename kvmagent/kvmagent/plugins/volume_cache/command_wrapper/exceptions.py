"""
Custom exception classes for volume_cache module.
Provides fine-grained error classification for pool and cache operations.
"""


class VolumeCacheError(Exception):
    """Base exception for all volume_cache errors."""
    pass


# ============================================================================
# Pool Exceptions
# ============================================================================

class PoolNotInitializedError(VolumeCacheError):
    """Raised when a pool operation requires an initialized pool but the pool is not initialized."""
    pass


class PoolNotFoundError(VolumeCacheError):
    """Raised when a requested pool processor does not exist."""
    pass


class PoolOperationError(VolumeCacheError):
    """Raised when a pool operation (create/connect/extend/delete) fails."""
    pass


# ============================================================================
# Cache Exceptions
# ============================================================================

class CacheNotInstantiatedError(VolumeCacheError):
    """Raised when a cache file is expected to exist but has not been instantiated."""
    pass


class CacheOperationError(VolumeCacheError):
    """Raised when a cache operation (create/flush/delete) fails."""
    pass


# ============================================================================
# Volume / Device Exceptions
# ============================================================================

class UnsupportedDeviceTypeError(VolumeCacheError):
    """Raised when the backing volume device type is not supported."""
    pass


class VolumeValidationError(VolumeCacheError):
    """Raised when volume parameters fail validation (e.g. missing required fields)."""
    pass
