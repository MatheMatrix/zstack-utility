# -*- coding: utf-8 -*-
"""
Lightweight HTTP test client for kvmagent plugin testing.

Provides a Py3-native HTTP server that implements the same route registration
interface as zstacklib.utils.http.HttpServer, so plugins can register their
handlers without modification. Uses threading + http.server instead of CherryPy
to avoid Py2 compatibility issues in the test environment.

Usage:
    client = HttpTestClient()
    client.register_plugin(plugin_instance)
    client.start()
    rsp = client.post_sync('/host/echo', {})
    assert rsp.success is True
    client.stop()
"""
import json
import socket
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

# Use the Py3-native shim; it may already be installed in sys.modules by
# the test conftest, or we import it directly as a fallback.
try:
    from zstacklib.utils import jsonobject
    # Verify it's the real/shim module, not a MagicMock
    if not callable(getattr(jsonobject, 'loads', None)):
        raise ImportError('jsonobject is a MagicMock')
except (ImportError, AttributeError):
    from zstacklib.test.utils import jsonobject_shim as jsonobject


REQUEST_HEADER = 'header'
REQUEST_BODY = 'body'
TASK_UUID = 'taskuuid'
CALLBACK_URI = 'callbackurl'
ERROR_CODE = 'error'


def _find_free_port():
    """Ask the OS for an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _wait_for_port(port, timeout=5.0):
    """Block until the server is accepting connections on the given port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError('Server did not start on port %d within %.1fs' % (port, timeout))


class _RouteEntry:
    """Holds a registered handler and its metadata."""
    __slots__ = ('uri', 'func', 'is_async', 'callback_uri', 'cmd')

    def __init__(self, uri, func, is_async=False, callback_uri=None, cmd=None):
        self.uri = uri
        self.func = func
        self.is_async = is_async
        self.callback_uri = callback_uri
        self.cmd = cmd


class _RequestHandler(BaseHTTPRequestHandler):
    """Dispatches POST requests to registered plugin handlers."""

    def log_message(self, format, *args):
        # Suppress noisy per-request logs during tests
        pass

    def do_POST(self):
        path = self.path.rstrip('/')
        routes = self.server.route_table  # type: dict[str, _RouteEntry]

        entry = routes.get(path)
        if entry is None:
            self.send_error(404, 'No handler for %s' % path)
            return

        content_length = int(self.headers.get('Content-Length', 0))
        raw_body = self.requestline  # fallback
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
        else:
            raw_body = b''

        body_str = raw_body.decode('utf-8') if isinstance(raw_body, bytes) else raw_body

        # Build the entity dict that plugin handlers expect
        headers = dict(self.headers)
        entity = {
            REQUEST_HEADER: headers,
            REQUEST_BODY: body_str if body_str else None,
        }

        if entry.is_async:
            self._handle_async(entry, entity, headers)
        else:
            self._handle_sync(entry, entity)

    def _handle_sync(self, entry, entity):
        try:
            result = entry.func(entity)
            response_body = result if result else ''
            if isinstance(response_body, bytes):
                data = response_body
            else:
                data = str(response_body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            err_msg = str(e).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def _handle_async(self, entry, entity, headers):
        """Run handler in background thread, POST result to callback URL."""
        task_uuid = headers.get(TASK_UUID) or headers.get('Taskuuid')
        if not task_uuid:
            self.send_error(400, 'taskuuid missing in request header for async call')
            return

        # Acknowledge the async request immediately
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        callback_uri = (headers.get(CALLBACK_URI)
                        or headers.get('Callbackurl')
                        or entry.callback_uri)

        def _run():
            cb_headers = {TASK_UUID: task_uuid}
            try:
                content = entry.func(entity)
            except Exception as ex:
                content = str(ex)
                cb_headers[ERROR_CODE] = content

            if callback_uri:
                _post_callback(callback_uri, content, cb_headers)

        t = threading.Thread(target=_run, daemon=True)
        t.start()


def _post_callback(url, body, headers):
    """POST the async result to the callback URL using urllib (Py3)."""
    import urllib.request
    data = body.encode('utf-8') if isinstance(body, str) else (body or b'')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Best-effort callback in tests


class HttpTestClient:
    """
    Lightweight test client that starts a Py3-native HTTP server
    with the same route registration interface as HttpServer.

    Plugins call http_server.register_sync_uri() / register_async_uri()
    and this class stores the routes, then serves them via http.server.

    Remote mode (direct_host is set):
      - POST requests go to the real kvmagent at direct_host:direct_port
      - Async callbacks use SSH-poll via callback_collector.py on the remote
      - No local server is started; stub registrations are ignored
    """

    def __init__(self, port=None, direct_host=None, direct_port=None,
                 ssh_run_fn=None, skip_collector_check=False):
        self.port = port or _find_free_port()
        self.direct_host = direct_host
        self.direct_port = int(direct_port) if direct_port else 7070
        self._ssh_run = ssh_run_fn
        self._skip_collector_check = skip_collector_check
        self._routes = {}  # type: dict[str, _RouteEntry]
        self._server = None
        self._thread = None
        self._started = False
        self._callback_server = None
        self._callback_thread = None

    @property
    def is_remote(self):
        return self.direct_host is not None

    @property
    def _base_url(self):
        if self.is_remote:
            return 'http://%s:%s' % (self.direct_host, self.direct_port)
        return 'http://127.0.0.1:%d' % self.port

    # --- Route registration (same interface as HttpServer) ---
    # In remote mode these are no-ops: the real kvmagent already has routes.

    def register_sync_uri(self, uri, func, cmd=None):
        if self.is_remote:
            return
        path = uri.rstrip('/')
        self._routes[path] = _RouteEntry(uri=path, func=func, is_async=False, cmd=cmd)

    def register_async_uri(self, uri, func, callback_uri=None, cmd=None):
        if self.is_remote:
            return
        path = uri.rstrip('/')
        self._routes[path] = _RouteEntry(
            uri=path, func=func, is_async=True,
            callback_uri=callback_uri, cmd=cmd,
        )

    def register_raw_uri(self, uri, func):
        if self.is_remote:
            return
        path = uri.rstrip('/')
        self._routes[path] = _RouteEntry(uri=path, func=func, is_async=False)

    def register_raw_stream_uri(self, uri, func):
        self.register_raw_uri(uri, func)

    # --- Plugin loading ---

    def register_plugin(self, plugin_instance):
        """Call plugin.start() so it registers routes on this client.

        Before calling start(), we monkey-patch kvmagent.get_http_server()
        to return this client instance, so the plugin's register calls
        land in our route table.
        """
        import sys
        kvmagent_mod = sys.modules.get('kvmagent.kvmagent')
        if kvmagent_mod:
            kvmagent_mod.get_http_server = lambda: self

        plugin_instance.start()

    # --- Server lifecycle ---

    def start(self):
        if self._started:
            return

        if self.is_remote:
            # Remote mode: ensure callback_collector is running on remote.
            if self._ssh_run:
                self._ssh_run(
                    'mkdir -p /tmp/callbacks && rm -f /tmp/callbacks/*.json'
                )
            if self._skip_collector_check:
                # Docker mode: collector is pre-running in the container,
                # skip ss/start checks, go straight to bootstrap.
                self._bootstrap_remote_connect()
                self._started = True
                return
            if self._ssh_run:
                # Check if collector is already running
                rc, out, _ = self._ssh_run('ss -tlnp | grep 18080')
                if rc != 0 or '18080' not in out:
                    # Kill stale processes by PID to avoid matching SSH args
                    self._ssh_run(
                        'kill -9 $(cat /tmp/callback_collector.pid '
                        '2>/dev/null) 2>/dev/null; sleep 0.3'
                    )
                    # Start collector via a wrapper script that detaches
                    self._ssh_run(
                        'sh -c \'echo $$ > /tmp/callback_collector.pid; '
                        'exec python '
                        '/tmp/zstack-test/zstack-utility/tests/http/scripts/'
                        'callback_collector.py 18080 '
                        '>/tmp/callback_collector.log 2>&1 </dev/null\' &'
                    )
                    # Verify collector is up
                    for _ in range(10):
                        time.sleep(0.5)
                        rc, out, _ = self._ssh_run(
                            'ss -tlnp | grep 18080'
                        )
                        if rc == 0 and '18080' in out:
                            break
                    else:
                        raise RuntimeError(
                            'callback_collector failed to start on remote. '
                            'Start it manually: ssh root@<host> '
                            '"nohup python /tmp/zstack-test/zstack-utility/'
                            'tests/http/scripts/callback_collector.py 18080 '
                            '>/tmp/callback_collector.log 2>&1 &"'
                        )

            # Bootstrap: send /host/connect so kvmagent callbacks go to
            # our collector instead of the unreachable MN.
            self._bootstrap_remote_connect()

            self._started = True
            return

        server = HTTPServer(('127.0.0.1', self.port), _RequestHandler)
        server.route_table = self._routes
        self._server = server

        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        _wait_for_port(self.port)
        self._started = True

    def stop(self):
        if self.is_remote:
            # Don't kill the callback collector — leave it running for
            # subsequent test modules.  It will be cleaned up manually
            # or by the next start() if needed.
            self._started = False
            return
        if self._server:
            self._server.shutdown()
            self._thread.join(timeout=5)
            self._server.server_close()
            self._started = False
        if self._callback_server:
            self._callback_server.shutdown()
            self._callback_thread.join(timeout=5)
            self._callback_server.server_close()

    # --- Remote bootstrap ---

    def _bootstrap_remote_connect(self):
        """Send /host/connect to the remote kvmagent so its sendCommandUrl
        points to our callback collector (127.0.0.1:18080) instead of
        the unreachable management node.  This prevents crashes when
        handlers try to phone home."""
        import urllib.request
        url = '%s/host/connect' % self._base_url
        body = jsonobject.dumps({
            'sendCommandUrl': 'http://127.0.0.1:18080/api',
            'hostUuid': 'test-coverage-host',
            'iptablesRules': [],
            'version': '5.5.6',
            'tcpServerPort': 18888,
            'pageTableExtensionDisabled': False,
            'ignoreMsrs': True,
        }).encode('utf-8')
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('commandpath', '/host/connect')
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            resp.read()
        except Exception:
            pass  # Best-effort; connect may fail but sets sendCommandUrl

    # --- Request helpers ---

    def post_sync(self, path, body_dict, headers=None):
        """Send a sync POST, return parsed jsonobject response."""
        import urllib.request
        url = '%s%s' % (self._base_url, path)
        data = jsonobject.dumps(body_dict).encode('utf-8') if body_dict else b'{}'
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        if self.is_remote:
            req.add_header('commandpath', path)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urllib.request.urlopen(req, timeout=30)
        resp_body = resp.read().decode('utf-8')
        if not resp_body or resp_body.strip() == '':
            return jsonobject.loads('{"success": true}')
        return jsonobject.loads(resp_body)

    def post_async(self, path, body_dict, timeout=None):
        """Send an async POST with a taskuuid, collect the callback result.

        Local mode: starts a temporary callback server on 127.0.0.1.
        Remote mode: uses callback_collector.py on the remote host,
        polls /tmp/callbacks/<taskuuid>.json via SSH.
        """
        if timeout is None:
            timeout = 30 if self.is_remote else 10

        if self.is_remote:
            return self._post_async_remote(path, body_dict, timeout)

        result_holder = {'body': None}
        result_event = threading.Event()

        class _CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length) if length else b''
                result_holder['body'] = raw.decode('utf-8')
                self.send_response(200)
                self.end_headers()
                result_event.set()

        cb_port = _find_free_port()
        cb_server = HTTPServer(('127.0.0.1', cb_port), _CallbackHandler)
        self._callback_server = cb_server
        self._callback_thread = threading.Thread(
            target=cb_server.serve_forever, daemon=True)
        self._callback_thread.start()
        _wait_for_port(cb_port)

        callback_url = 'http://127.0.0.1:%d/callback' % cb_port
        task_uuid = str(uuid.uuid4()).replace('-', '')

        import urllib.request
        url = '%s%s' % (self._base_url, path)
        data = jsonobject.dumps(body_dict).encode('utf-8') if body_dict else b'{}'
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header(TASK_UUID, task_uuid)
        req.add_header(CALLBACK_URI, callback_url)

        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # async returns immediately, may be empty

        if not result_event.wait(timeout=timeout):
            cb_server.shutdown()
            raise TimeoutError('Async callback not received within %ds' % timeout)

        cb_server.shutdown()

        body_text = result_holder['body']
        if not body_text or body_text.strip() == '':
            return jsonobject.loads('{"success": true}')
        return jsonobject.loads(body_text)

    def _post_async_remote(self, path, body_dict, timeout=10):
        """Async POST in remote mode: send to real kvmagent, SSH-poll callback."""
        import urllib.request

        task_uuid = str(uuid.uuid4()).replace('-', '')
        callback_url = 'http://127.0.0.1:18080/callback'

        url = '%s%s' % (self._base_url, path)
        data = jsonobject.dumps(body_dict).encode('utf-8') if body_dict else b'{}'
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header(TASK_UUID, task_uuid)
        req.add_header(CALLBACK_URI, callback_url)
        req.add_header('commandpath', path)

        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

        # SSH-poll for callback result
        deadline = time.monotonic() + timeout
        cb_path = '/tmp/callbacks/%s.json' % task_uuid
        while time.monotonic() < deadline:
            exit_code, stdout, _ = self._ssh_run('cat %s 2>/dev/null' % cb_path)
            if exit_code == 0 and stdout.strip():
                return jsonobject.loads(stdout.strip())
            time.sleep(0.5)

        raise TimeoutError(
            'Remote async callback for %s not received within %ds' % (path, timeout)
        )
