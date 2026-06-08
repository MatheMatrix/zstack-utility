"""Common decorators for Linux system operations.

This module provides decorator functions for retry, error handling, and
architecture-specific execution.
"""
from __future__ import annotations

import functools
import logging
import pprint
import time
import traceback
from typing import Callable, TypeVar, ParamSpec

from .models import SUPPORTED_ARCH
from .arch import HOST_ARCH


P = ParamSpec('P')
T = TypeVar('T')

# Default logger (can be overridden)
_logger: logging.Logger | None = None


def set_logger(logger: logging.Logger) -> None:
    """Set the logger to use for decorators.
    
    Args:
        logger: Logger instance to use.
    """
    global _logger
    _logger = logger


def _get_logger() -> logging.Logger:
    """Get the configured logger or a default one."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
    return _logger


def retry(times: int = 3, sleep_time: float = 3.0, exceptions: tuple = (Exception,)):
    """Decorator to retry a function on failure.
    
    Args:
        times: Maximum number of retry attempts.
        sleep_time: Seconds to sleep between retries.
        exceptions: Tuple of exception types to catch and retry.
        
    Returns:
        Decorator function.
        
    Example:
        @retry(times=5, sleep_time=1.0)
        def flaky_operation():
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < times - 1:
                        time.sleep(sleep_time)
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def retry_with_check(handler: Callable[[tuple, Exception], bool] | None = None):
    """Decorator to retry a function with a custom check handler.
    
    Args:
        handler: Function that receives (args, exception) and returns True to retry.
        
    Returns:
        Decorator function.
        
    Example:
        def should_retry(args, exc):
            return isinstance(exc, ConnectionError)
            
        @retry_with_check(handler=should_retry)
        def connect():
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if handler is not None and handler(args, e):
                    return func(*args, **kwargs)
                raise
        return wrapper
    return decorator


def ignoreerror(func: Callable[P, T]) -> Callable[P, T | None]:
    """Decorator to catch and log exceptions without raising.
    
    The function returns None if an exception occurs.
    
    Args:
        func: Function to wrap.
        
    Returns:
        Wrapped function that catches exceptions.
        
    Example:
        @ignoreerror
        def cleanup_files():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = _get_logger()
            content = traceback.format_exc()
            err = f'{e}\n{content}\nargs:{pprint.pformat([args, kwargs])}'
            logger.warning(err)
            return None
    return wrapper


class IgnoreError:
    """Context manager to ignore and log errors.
    
    Example:
        with IgnoreError():
            risky_operation()
    """
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger = _get_logger()
            content = traceback.format_exc()
            err = f'{exc_val}\n{content}'
            logger.warning(err)
            return True  # Suppress exception
        return False


def with_arch(todo_list: list[str] | None = None, host_arch: str | None = None):
    """Decorator to run function only on specified architectures.
    
    If the current architecture is not in the allowed list, the function
    is skipped and returns None.
    
    Args:
        todo_list: List of architectures to run on. Defaults to SUPPORTED_ARCH.
        host_arch: Override host architecture detection.
        
    Returns:
        Decorator function.
        
    Raises:
        ValueError: If unknown architectures are specified.
        
    Example:
        @with_arch(todo_list=['x86_64', 'aarch64'])
        def x86_and_arm_only():
            ...
    """
    if todo_list is None:
        todo_list = SUPPORTED_ARCH
    if host_arch is None:
        host_arch = HOST_ARCH
    
    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            unknown_arch = set(todo_list) - set(SUPPORTED_ARCH)
            if unknown_arch:
                raise ValueError(f"Unknown architecture(s): {unknown_arch}")
            
            if host_arch in todo_list:
                return func(*args, **kwargs)
            else:
                logger = _get_logger()
                logger.info(f"Skip function[{func.__name__}] on {host_arch} host.")
                return None
        return wrapper
    return decorator


def on_redhat_based(distro: str, exclude: list[str] | None = None):
    """Decorator to run function only on Red Hat based distributions.
    
    Args:
        distro: Current distribution name.
        exclude: List of distributions to exclude.
        
    Returns:
        Decorator function.
        
    Raises:
        ValueError: If distro is not provided.
        
    Example:
        @on_redhat_based(distro=get_distro_name())
        def redhat_only():
            ...
    """
    from .models import RPM_BASED_OS
    
    if exclude is None:
        exclude = []
    
    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            if not distro:
                raise ValueError("Distro info is needed.")
            allowed = set(RPM_BASED_OS) - set(exclude)
            if distro in allowed:
                return func(*args, **kwargs)
            return None
        return wrapper
    return decorator


def on_debian_based(distro: str, exclude: list[str] | None = None):
    """Decorator to run function only on Debian based distributions.
    
    Args:
        distro: Current distribution name.
        exclude: List of distributions to exclude.
        
    Returns:
        Decorator function.
        
    Raises:
        ValueError: If distro is not provided.
        
    Example:
        @on_debian_based(distro=get_distro_name())
        def debian_only():
            ...
    """
    from .models import DEB_BASED_OS
    
    if exclude is None:
        exclude = []
    
    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            if not distro:
                raise ValueError("Distro info is needed.")
            allowed = set(DEB_BASED_OS) - set(exclude)
            if distro in allowed:
                return func(*args, **kwargs)
            return None
        return wrapper
    return decorator
