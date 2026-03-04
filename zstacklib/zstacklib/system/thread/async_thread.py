from __future__ import annotations

import functools
import logging
import pprint
import threading
import traceback
from typing import Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


def run_in_thread(
    target: Callable[P, T],
    args: tuple = (),
    kwargs: dict | None = None
) -> threading.Thread:
    kwargs = kwargs or {}
    
    def safe_run(*sargs, **skwargs):
        try:
            target(*sargs, **skwargs)
        except Exception as e:
            content = traceback.format_exc()
            err = f'{e}\n{content}\nargs:{pprint.pformat([args, kwargs])}'
            logger.warning(err)
    
    t = threading.Thread(target=safe_run, name=target.__name__, args=args, kwargs=kwargs)
    t.start()
    return t


class AsyncThread:
    def __init__(self, func: Callable):
        self.func = func
    
    def __get__(self, obj, objtype=None):
        return self.__class__(self.func.__get__(obj, objtype))
    
    def __call__(self, *args, **kwargs) -> threading.Thread:
        return run_in_thread(self.func, args=args, kwargs=kwargs)
