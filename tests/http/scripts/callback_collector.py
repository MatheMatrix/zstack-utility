#!/usr/bin/env python
"""Callback collector for kvmagent async HTTP tests.

Runs on the compute host (same machine as kvmagent) so kvmagent can
deliver callbacks to 127.0.0.1:18080. Each callback is saved as
/tmp/callbacks/<taskuuid>.json for the test runner to read via SSH.

Usage:
    python callback_collector.py [PORT]

Default port: 18080
"""
import json
import os
import sys

# Python 2/3 compatible imports
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

CALLBACK_DIR = '/tmp/callbacks'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18080


class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        taskuuid = self.headers.get('taskuuid', 'unknown')

        if not os.path.isdir(CALLBACK_DIR):
            os.makedirs(CALLBACK_DIR)

        filepath = os.path.join(CALLBACK_DIR, '%s.json' % taskuuid)
        with open(filepath, 'wb') as f:
            f.write(body)

        sys.stderr.write('[collector] %s -> %s (%d bytes)\n'
                         % (taskuuid, filepath, len(body)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, fmt, *args):
        pass  # suppress default logging


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    if not os.path.isdir(CALLBACK_DIR):
        os.makedirs(CALLBACK_DIR)
    server = ReuseHTTPServer(('127.0.0.1', PORT), CallbackHandler)
    sys.stderr.write('Callback collector listening on 127.0.0.1:%d\n' % PORT)
    sys.stderr.write('Saving to %s/<taskuuid>.json\n' % CALLBACK_DIR)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
