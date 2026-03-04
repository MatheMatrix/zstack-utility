# -*- coding: utf-8 -*-
"""Async callback helper for HTTP integration tests."""
from __future__ import annotations
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
import pytest

class AsyncCallbackHelper:
    """HTTP callback receiver with Event-based synchronization."""
    def __init__(self, port: int = 0):
        self.results: Dict[str, Any] = {}
        self.events: Dict[str, threading.Event] = {}
        helper = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_len)
                taskuuid = self.headers.get('taskuuid', 'unknown')
                helper.results[taskuuid] = json.loads(body) if body else {}
                if taskuuid in helper.events:
                    helper.events[taskuuid].set()
                self.send_response(200)
                self.end_headers()
            def log_message(self, format, *args):
                pass
        self.server = HTTPServer(('127.0.0.1', port), Handler)
        self.server.socket.setsockopt(__import__('socket').SOL_SOCKET, __import__('socket').SO_REUSEADDR, 1)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
    def wait(self, taskuuid: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for callback. Raises TimeoutError if not received."""
        event = threading.Event()
        self.events[taskuuid] = event
        if not event.wait(timeout):
            raise TimeoutError(f"Callback for {taskuuid} not received in {timeout}s")
        return self.results.get(taskuuid, {})
    def get_callback_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/callback"
    def cleanup(self):
        if hasattr(self, 'server'):
            self.server.shutdown()

@pytest.fixture
def async_callback():
    helper = AsyncCallbackHelper()
    yield helper
    helper.cleanup()
