"""CPU architecture detection.

This module provides functions to detect and work with CPU architectures.
"""
from __future__ import annotations

import platform

from .models import SUPPORTED_ARCH
from .exceptions import ArchError


# Host architecture (cached at module load time)
HOST_ARCH: str = platform.machine()


def get_arch() -> str:
    """Get the current CPU architecture.
    
    Returns:
        Architecture string (e.g., 'x86_64', 'aarch64').
    """
    return HOST_ARCH


def is_supported_arch(arch: str | None = None) -> bool:
    """Check if the architecture is supported.
    
    Args:
        arch: Architecture to check. If None, uses current arch.
        
    Returns:
        True if architecture is supported.
    """
    if arch is None:
        arch = HOST_ARCH
    return arch in SUPPORTED_ARCH


def is_x86_64(arch: str | None = None) -> bool:
    """Check if the architecture is x86_64.
    
    Args:
        arch: Architecture to check. If None, uses current arch.
        
    Returns:
        True if x86_64.
    """
    if arch is None:
        arch = HOST_ARCH
    return arch == 'x86_64'


def is_aarch64(arch: str | None = None) -> bool:
    """Check if the architecture is aarch64 (ARM64).
    
    Args:
        arch: Architecture to check. If None, uses current arch.
        
    Returns:
        True if aarch64.
    """
    if arch is None:
        arch = HOST_ARCH
    return arch == 'aarch64'


def is_mips64el(arch: str | None = None) -> bool:
    """Check if the architecture is mips64el.
    
    Args:
        arch: Architecture to check. If None, uses current arch.
        
    Returns:
        True if mips64el.
    """
    if arch is None:
        arch = HOST_ARCH
    return arch == 'mips64el'


def is_loongarch64(arch: str | None = None) -> bool:
    """Check if the architecture is loongarch64.
    
    Args:
        arch: Architecture to check. If None, uses current arch.
        
    Returns:
        True if loongarch64.
    """
    if arch is None:
        arch = HOST_ARCH
    return arch == 'loongarch64'


def require_arch(*architectures: str):
    """Decorator factory that requires specific architectures.
    
    Args:
        architectures: Allowed architectures.
        
    Returns:
        Decorator function.
        
    Raises:
        ArchError: If current architecture is not in allowed list.
        
    Example:
        @require_arch('x86_64', 'aarch64')
        def some_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if HOST_ARCH not in architectures:
                raise ArchError(f"Function {func.__name__} requires architecture in {architectures}, but running on {HOST_ARCH}")
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
