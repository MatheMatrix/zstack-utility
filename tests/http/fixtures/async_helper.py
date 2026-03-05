# -*- coding: utf-8 -*-
"""Async callback helper for HTTP integration tests."""
from __future__ import annotations
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
import pytest

class AsyncCallbackHelper:
    """HTTP callback receiver with Event-based synchronization."""
    def __init__(self, port: int = 0, callback_url: Optional[str] = None):
        self.results: Dict[str, Any] = {}
        self.events: Dict[str, threading.Event] = {}
        self._callback_url = callback_url
        helper = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_len)
                taskuuid = self.headers.get('taskuuid', 'unknown')
                try:
                    helper.results[taskuuid] = json.loads(body) if body else {}
                except (json.JSONDecodeError, ValueError):
                    helper.results[taskuuid] = {'_raw': body.decode('utf-8', errors='replace')}
                if taskuuid in helper.events:
                    helper.events[taskuuid].set()
                self.send_response(200)
                self.end_headers()
            def log_message(self, format, *args):
                pass
        class ReuseHTTPServer(HTTPServer):
            allow_reuse_address = True
            allow_reuse_port = True
        self.server = ReuseHTTPServer(('127.0.0.1', port), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
    def wait(self, taskuuid: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for callback. Raises TimeoutError if not received."""
        if taskuuid in self.results:
            return self.results[taskuuid]
        event = threading.Event()
        self.events[taskuuid] = event
        try:
            if taskuuid in self.results:
                return self.results[taskuuid]
            if not event.wait(timeout):
                raise TimeoutError("Callback for %s not received in %ss" % (taskuuid, timeout))
            return self.results.get(taskuuid, {})
        finally:
            self.events.pop(taskuuid, None)
    def get_callback_url(self) -> str:
        if self._callback_url:
            return self._callback_url
        return "http://127.0.0.1:%d/callback" % self.port
    def cleanup(self):
        if hasattr(self, 'server'):
            self.server.shutdown()

@pytest.fixture
def async_callback(request):
    """Async callback helper with optional relay URL override.

    Modes:
    1. --callback-url: Use pre-configured relay. Binds to port 18080.
    2. Default: callback server on random port, URL is local.
    """
    callback_url = request.config.getoption("--callback-url", default=None)

    if callback_url:
        helper = AsyncCallbackHelper(port=18080, callback_url=callback_url)
    else:
        helper = AsyncCallbackHelper()

    yield helper

    helper.cleanup()
