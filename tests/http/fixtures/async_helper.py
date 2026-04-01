# -*- coding: utf-8 -*-
"""Async callback helper for HTTP integration tests."""
from __future__ import annotations
import json, subprocess, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
import pytest


class AsyncCallbackHelper:
    """HTTP callback receiver with Event-based synchronization.

    Modes:
    - Local: starts HTTP server, kvmagent posts callbacks directly.
    - SSH-poll: kvmagent posts to a collector on the compute host;
      wait() polls /tmp/callbacks/<taskuuid>.json via SSH.
    """
    def __init__(self, port: int = 0, callback_url: Optional[str] = None,
                 ssh_poll_host: Optional[str] = None,
                 ssh_jump: Optional[str] = None):
        self.results: Dict[str, Any] = {}
        self.events: Dict[str, threading.Event] = {}
        self._callback_url = callback_url
        self._ssh_poll_host = ssh_poll_host
        self._ssh_jump = ssh_jump
        self.server = None

        if ssh_poll_host:
            # SSH-poll mode: no local server needed
            self.port = 0
            return

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

    def _ssh_read_callback(self, taskuuid: str) -> Optional[Dict[str, Any]]:
        """Read callback JSON from remote compute host via SSH."""
        remote_path = '/tmp/callbacks/%s.json' % taskuuid
        ssh_cmd = ['sshpass', '-p', 'password', 'ssh',
                    '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5']
        if self._ssh_jump:
            ssh_cmd += ['-J', 'root@%s' % self._ssh_jump]
        ssh_cmd += ['root@%s' % self._ssh_poll_host,
                    'cat %s 2>/dev/null' % remote_path]
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
            pass
        return None

    def wait(self, taskuuid: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for callback. Raises TimeoutError if not received."""
        if taskuuid in self.results:
            return self.results[taskuuid]

        if self._ssh_poll_host:
            # SSH-poll mode: poll remote file
            deadline = time.time() + timeout
            while time.time() < deadline:
                data = self._ssh_read_callback(taskuuid)
                if data is not None:
                    self.results[taskuuid] = data
                    return data
                time.sleep(1.0)
            raise TimeoutError("Callback for %s not received in %ss" % (taskuuid, timeout))

        # Local HTTP server mode
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
        if self.server:
            self.server.shutdown()


@pytest.fixture
def async_callback(request):
    """Async callback helper with multiple modes.

    Modes:
    1. --callback-ssh-host + --callback-ssh-jump: SSH-poll mode.
       kvmagent callbacks go to collector on compute host;
       wait() reads /tmp/callbacks/<uuid>.json via SSH.
    2. --callback-url: relay mode. Binds to port 18080.
    3. Default: local HTTP server on random port.
    """
    ssh_host = request.config.getoption("--callback-ssh-host", default=None)
    ssh_jump = request.config.getoption("--callback-ssh-jump", default=None)
    callback_url = request.config.getoption("--callback-url", default=None)

    if ssh_host:
        helper = AsyncCallbackHelper(
            callback_url="http://127.0.0.1:18080/callback",
            ssh_poll_host=ssh_host,
            ssh_jump=ssh_jump,
        )
    elif callback_url:
        helper = AsyncCallbackHelper(port=18080, callback_url=callback_url)
    else:
        helper = AsyncCallbackHelper()

    yield helper

    helper.cleanup()
