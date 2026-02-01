# Copyright (c) ZStack.io, Inc.

"""
Decorators for IP route operations.

Provides logging and error-handling decorators for iproute commands.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from zstacklib.utils import log

logger = log.get_logger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def log_iproute_call(text):
    # type: (str) -> Callable[[F], F]
    """
    Decorator to log iproute function calls.
    
    Logs the function name, arguments, and return value or exception.
    
    Args:
        text: Description text for the operation
    
    Example:
        >>> @log_iproute_call("address add")
        ... def add_address(ip, prefixlen, ...):
        ...     pass
    """
    def wrap(func):
        # type: (F) -> F
        @wraps(func)
        def inner(*args, **kwargs):
            # type: (*Any, **Any) -> Any
            cmd = '%s: args=%s, kwargs=%s' % (text, args, kwargs)
            try:
                ret = func(*args, **kwargs)
                if ret is None:
                    logger.debug(cmd)
                else:
                    logger.debug('%s, return %s' % (cmd, ret))
                return ret
            except Exception as e:
                logger.warn('%s, raise: %s' % (cmd, e))
                raise
        return inner  # type: ignore
    return wrap


def no_error_do(func):
    # type: (F) -> F
    """
    Decorator to catch exceptions and return False instead.
    
    Wraps a function so that it returns True on success
    and False if any exception is raised (swallowing the exception).
    
    Args:
        func: Function to wrap
    
    Returns:
        Wrapped function that returns bool
    
    Example:
        >>> @no_error_do
        ... def risky_operation():
        ...     raise Exception("Error")
        >>> risky_operation()
        False
    """
    @wraps(func)
    def aim_to_do(*args, **kwargs):
        # type: (*Any, **Any) -> bool
        try:
            func(*args, **kwargs)
            return True
        except Exception:
            return False
    return aim_to_do  # type: ignore
