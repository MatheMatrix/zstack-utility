from __future__ import annotations

import functools
import logging
import threading
import traceback
from typing import Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')

_local = threading.local()


def _get_defer_stack() -> list[list[Callable[[], None]]]:
    """Get defer stack."""
    if not hasattr(_local, 'defer_stack'):
        _local.defer_stack = []
    return _local.defer_stack


def defer(f: Callable[[], None]) -> None:
    """Defer."""
    stack = _get_defer_stack()
    if not stack:
        raise RuntimeError(
            'defer() must be called from within a function decorated with @protect'
        )
    stack[-1].append(f)


def protect(f: Callable[P, T]) -> Callable[P, T]:
    """Protect."""
    @functools.wraps(f)
    def inner(*args: P.args, **kwargs: P.kwargs) -> T:
        """Inner."""
        stack = _get_defer_stack()
        stack.append([])
        
        try:
            return f(*args, **kwargs)
        finally:
            deferred = stack.pop()
            for df in reversed(deferred):
                try:
                    df()
                except Exception:
                    logger.warning(f'unhandled defer error:\n{traceback.format_exc()}')
    
    return inner
