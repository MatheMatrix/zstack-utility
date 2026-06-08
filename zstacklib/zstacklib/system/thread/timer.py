from __future__ import annotations

import functools
import logging
import pprint
import threading
import traceback
from typing import Callable, Any

logger = logging.getLogger(__name__)


class PeriodicTimer:
    def __init__(
        self,
        interval: float,
        callback: Callable[..., bool | None],
        args: list | None = None,
        kwargs: dict | None = None,
        stop_on_exception: bool = True
    ):
        self.interval = interval
        self.args = args or []
        self.kwargs = kwargs or {}
        self.stop_on_exception = stop_on_exception
        self._thread: threading.Timer | None = None
        self._original_callback = callback
        
        @functools.wraps(callback)
        def wrapper(*wargs, **wkwargs):
            result = not self.stop_on_exception
            try:
                result = callback(*wargs, **wkwargs)
            except Exception as e:
                content = traceback.format_exc()
                err = f'{e}\n{content}\nargs:{pprint.pformat([wargs, wkwargs])}'
                logger.warning(err)
                logger.warning('timer thread will terminate due to exception')
            
            if result:
                self._thread = threading.Timer(
                    self.interval, self._callback, self.args, self.kwargs
                )
                self._thread.start()
        
        self._callback = wrapper

    def start(self) -> None:
        from zstacklib.system.thread.async_thread import run_in_thread
        
        def _start():
            self._thread = threading.Timer(
                self.interval, self._callback, self.args, self.kwargs
            )
            self._thread.start()
        
        run_in_thread(_start)

    def cancel(self) -> None:
        if self._thread:
            self._thread.cancel()

    def is_alive(self) -> bool:
        return self._thread.is_alive() if self._thread else False
