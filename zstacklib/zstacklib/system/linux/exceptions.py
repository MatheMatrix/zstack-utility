"""Linux system exceptions.

This module defines exceptions for Linux system operations.
"""
from __future__ import annotations


class LinuxError(Exception):
    """Base exception for Linux system errors."""
    pass


class DistroError(LinuxError):
    """Error detecting or working with Linux distribution."""
    pass


class ArchError(LinuxError):
    """Error related to CPU architecture."""
    pass


class KernelError(LinuxError):
    """Error related to kernel operations."""
    pass


class ModuleLoadError(KernelError):
    """Error loading kernel module."""
    
    def __init__(self, module: str, message: str = ""):
        self.module = module
        self.message = message
        super().__init__(f"Failed to load kernel module '{module}': {message}" if message else f"Failed to load kernel module '{module}'")


class SysctlError(KernelError):
    """Error getting or setting sysctl parameter."""
    
    def __init__(self, param: str, message: str = ""):
        self.param = param
        self.message = message
        super().__init__(f"Sysctl error for '{param}': {message}" if message else f"Sysctl error for '{param}'")
