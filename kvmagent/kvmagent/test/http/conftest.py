# -*- coding: utf-8 -*-
"""
Fixtures for HTTP-level plugin tests.

Strategy: install Py3-compat sys.modules mocks for zstacklib modules that use
Py2 syntax, plus a Py3-native jsonobject shim, so the stub handlers and the
HttpTestClient get real serialization behavior. These mocks are intentionally
scoped to the http/ subtree to avoid polluting sibling test directories
(e.g. nfs_testsuit/, ha/) that import the real zstacklib.utils.bash etc.
"""
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

logger = logging.getLogger(__name__)


# ---- Py3 compatibility mocks for zstacklib (scoped to http/ tests only) ----
# Use setdefault so we never clobber a real zstacklib module already imported
# by sibling test directories.
_mock_log = types.ModuleType('zstacklib.utils.log')
_mock_logger = MagicMock()
_mock_log.get_logger = lambda name: _mock_logger
_mock_log.LogConfig = MagicMock()
sys.modules.setdefault('log', _mock_log)
sys.modules.setdefault('zstacklib.utils.log', _mock_log)

_mock_bash = types.ModuleType('zstacklib.utils.bash')
_mock_bash.log = _mock_log
_mock_bash.bash_roe = lambda *a, **kw: (0, '', '')
_mock_bash.bash_ro = lambda *a, **kw: (0, '')
_mock_bash.bash_r = lambda *a, **kw: 0
_mock_bash.bash_o = lambda *a, **kw: ''
sys.modules.setdefault('bash', _mock_bash)
sys.modules.setdefault('zstacklib.utils.bash', _mock_bash)

for _mod_name in (
    'libvirt',
    'zstacklib.utils.plugin',
    'zstacklib.utils.shell',
    'zstacklib.utils.lock',
    'zstacklib.utils.linux',
    'zstacklib.utils.daemon',
    'zstacklib.utils.filedb',
    'zstacklib.utils.salt',
    'zstacklib.utils.ovs',
    'zstacklib.utils.qemu',
    'zstacklib.utils.sizeunit',
    'zstacklib.utils.thread',
    'zstacklib.utils.qga',
    'zstacklib.utils.jsonobject',
    'zstacklib.utils.lvm',
    'zstacklib.utils.report',
):
    sys.modules.setdefault(_mod_name, MagicMock())

sys.modules.setdefault('kvmagent.kvmagent', MagicMock())


# ---- VM integration test fixture (autouse for this subtree) ----------------

@pytest.fixture(autouse=True, scope="module")
def ztest_vm_env(request):
    """Auto-detect __ENV_SETUP__ and orchestrate VM-based test execution.

    Behavior by --vm-backend value:
      skip (default): skip modules with __ENV_SETUP__, run safe tests normally
      ssh:            run integration tests on an existing VM via SSH
      libvirt:        auto-create a KVM VM and run integration tests inside it
    """
    env_setup = getattr(request.module, '__ENV_SETUP__', None)
    if env_setup is None:
        yield
        return

    backend_name = request.config.getoption("--vm-backend")
    if backend_name == "skip":
        pytest.skip("VM integration test skipped (use --vm-backend=ssh|libvirt to enable)")
        return

    from zstacklib.test.utils.vm_backend import get_backend
    from zstacklib.test.utils.vm_orchestrator import VMOrchestrator

    backend = get_backend(backend_name, request.config)
    keep_on_failure = request.config.getoption("--keep-vm-on-failure")
    rsync_dest = request.config.getoption("--vm-rsync-path")

    orchestrator = VMOrchestrator(
        backend=backend,
        rsync_dest=rsync_dest,
        keep_on_failure=keep_on_failure,
    )

    case_name = request.module.__name__
    case_path = str(request.fspath)
    failed = False

    try:
        orchestrator.provision(env_setup, case_name)
        exit_code, stdout, stderr = orchestrator.run_test_in_vm(case_path)

        if exit_code != 0:
            failed = True
            pytest.fail(
                "VM integration test failed (exit code %d):\n"
                "--- stdout ---\n%s\n"
                "--- stderr ---\n%s" % (exit_code, stdout, stderr)
            )
        yield
    except Exception:
        failed = True
        raise
    finally:
        orchestrator.teardown(failed=failed)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "remote_xfail(reason): expected to fail against real kvmagent "
        "(auto-converted to xfail in remote mode)",
    )


def pytest_addoption(parser):
    parser.addoption('--direct-host', default=None,
                     help='Send requests to a real kvmagent at this host')
    parser.addoption('--direct-port', default=None,
                     help='Port of the real kvmagent (default: 7070)')
    parser.addoption('--callback-ssh-host', default=None,
                     help='SSH host for polling callbacks (if different from direct-host)')
    parser.addoption('--ssh-password', default='password',
                     help='SSH password for callback host (default: password)')
    parser.addoption('--ssh-port', default=22, type=int,
                     help='SSH port for callback host (default: 22)')
    parser.addoption('--skip-collector-check', action='store_true', default=False,
                     help='Skip callback collector start/check (use when collector is pre-running, e.g. Docker)')
    parser.addoption('--remote-coverage', action='store_true', default=False,
                     help='Enable coverage collection on remote kvmagent')
    parser.addoption('--mn-ip', default=None,
                     help='MN IP to block via iptables (prevents MN interference)')
    parser.addoption('--coverage-output', default='/tmp/cov-backup',
                     help='Local directory for coverage data')
    parser.addoption('--mn-url', default=os.getenv('ZSTACK_MN_URL'),
                     help='Management node base URL, e.g. http://172.24.189.175:8080/zstack')
    parser.addoption('--mn-account', default=os.getenv('ZSTACK_MN_ACCOUNT', 'admin'),
                     help='Management node account name (default: admin)')
    parser.addoption('--mn-password', default=os.getenv('ZSTACK_MN_PASSWORD'),
                     help='Management node account password (plain text, will be sha512 hashed)')
    parser.addoption('--storage-migrate-vm-uuid',
                     default=os.getenv('ZSTACK_STORAGE_MIGRATE_VM_UUID'),
                     help='VM UUID used by storage migration remote tests')
    parser.addoption('--storage-migrate-dst-ps-uuid',
                     default=os.getenv('ZSTACK_STORAGE_MIGRATE_DST_PS_UUID'),
                     help='Destination primary storage UUID used by storage migration remote tests')
    parser.addoption('--storage-migrate-dst-host-uuid',
                     default=os.getenv('ZSTACK_STORAGE_MIGRATE_DST_HOST_UUID'),
                     help='Destination host UUID used by storage migration remote tests')
    parser.addoption('--storage-migrate-bandwidth', type=int,
                     default=int(os.getenv('ZSTACK_STORAGE_MIGRATE_BANDWIDTH', '0')),
                     help='Optional storage migration bandwidth in bytes/s for remote tests')
    parser.addoption('--storage-migrate-timeout', type=int,
                     default=int(os.getenv('ZSTACK_STORAGE_MIGRATE_TIMEOUT', '900')),
                     help='Storage migration timeout in seconds for remote tests')
    parser.addoption('--storage-migrate-poll-interval', type=int,
                     default=int(os.getenv('ZSTACK_STORAGE_MIGRATE_POLL_INTERVAL', '3')),
                     help='Polling interval in seconds for storage migration remote tests')


# ---------------------------------------------------------------------------
# Ensure zstacklib is on sys.path (may not be set if tests/conftest.py
# wasn't loaded, e.g. when testpaths overrides to this directory).
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[4]
_zstacklib_path = str(_repo_root / 'zstacklib')
if _zstacklib_path not in sys.path:
    sys.path.insert(0, _zstacklib_path)

# ---------------------------------------------------------------------------
# Install jsonobject shim FIRST — before any import that touches jsonobject.
# The parent conftest.py replaces zstacklib.utils.jsonobject with MagicMock,
# so we must overwrite it here with our Py3-native shim.
# ---------------------------------------------------------------------------
from zstacklib.test.utils import jsonobject_shim

sys.modules['zstacklib.utils.jsonobject'] = jsonobject_shim
# Also alias bare 'jsonobject' in case any code does `import jsonobject`
sys.modules['jsonobject'] = jsonobject_shim

# Now we can safely import things that depend on jsonobject
from zstacklib.test.utils.http_test_client import HttpTestClient
from zstacklib.test.utils.system_mock import system_mock  # re-export fixture  # noqa: F401

jsonobject = jsonobject_shim

REQUEST_BODY = 'body'
REQUEST_HEADER = 'header'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ssh_run(host, password='password', port=22):
    """Create a simple ssh_run callable using sshpass+ssh subprocess."""
    def _run(cmd):
        result = subprocess.run(
            ['sshpass', '-p', password, 'ssh',
             '-p', str(port),
             '-o', 'StrictHostKeyChecking=no',
             '-o', 'UserKnownHostsFile=/dev/null',
             'root@%s' % host, cmd],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    return _run


def _deploy_remote_file(host, password, content, remote_path):
    """Write content to remote host via temp file + SCP."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        subprocess.run(
            ['sshpass', '-p', password, 'scp', '-o', 'StrictHostKeyChecking=no',
             tmp, 'root@%s:%s' % (host, remote_path)],
            capture_output=True, timeout=30, check=True,
        )
    finally:
        os.unlink(tmp)


def _scp_from_remote(host, password, remote_path, local_path):
    """SCP a file from remote to local."""
    subprocess.run(
        ['sshpass', '-p', password, 'scp', '-o', 'StrictHostKeyChecking=no',
         'root@%s:%s' % (host, remote_path), local_path],
        capture_output=True, timeout=30,
    )


def _deploy_callback_collector(host, password):
    collector_local = str(
        _repo_root / 'tests' / 'http' / 'scripts' / 'callback_collector.py'
    )
    collector_remote = (
        '/tmp/zstack-test/zstack-utility/tests/http/scripts/callback_collector.py'
    )
    if not os.path.exists(collector_local):
        return

    subprocess.run(
        ['sshpass', '-p', password, 'ssh',
         '-o', 'StrictHostKeyChecking=no',
         'root@%s' % host,
         'mkdir -p /tmp/zstack-test/zstack-utility/tests/http/scripts'],
        capture_output=True, timeout=30, check=True,
    )
    subprocess.run(
        ['sshpass', '-p', password, 'scp',
         '-o', 'StrictHostKeyChecking=no',
         collector_local,
         'root@%s:%s' % (host, collector_remote)],
        capture_output=True, timeout=30, check=True,
    )


def _generate_coverage_runner():
    """Generate a Python script that starts kvmagent with coverage.

    Two critical fixes applied:
    1. Daemon.daemonize is patched to skip the double-fork. Without this,
       the forked child process loses the coverage tracer.
    2. source=["kvmagent"] uses the package name (not filesystem path) to
       avoid lib/lib64 symlink mismatch in should_trace path comparison.
    """
    return '''\
import os, sys, signal, time, threading, atexit

# === 1. Patch Daemon.daemonize to skip fork ===
from zstacklib.utils.daemon import Daemon

def _no_fork_daemonize(self):
    """Skip the double-fork but still write pidfile and redirect IO."""
    os.chdir("/")
    os.umask(0)
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(self.stdin, "r")
    so = open(self.stdout, "a+")
    se = open(self.stderr, "a+", buffering=1)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    Daemon.register_atexit_hook(self.delpid)
    atexit.register(Daemon._atexit)
    pid = os.getpid()
    try:
        open(self.pidfile, "w").write("%d\\n" % pid)
    except IOError:
        pass

Daemon.daemonize = _no_fork_daemonize

# === 2. Start coverage ===
import coverage
cov = coverage.Coverage(
    data_file="/tmp/.coverage.kvmagent",
    source=["kvmagent"],
    concurrency=["thread"],
)
cov.start()

# === 3. Periodic save (every 15s) ===
def _periodic_save():
    while True:
        time.sleep(15)
        try:
            cov.save()
        except Exception:
            pass

threading.Thread(target=_periodic_save, daemon=True).start()

# === 4. SIGUSR1 handler for on-demand save ===
def _sigusr1_handler(signum, frame):
    try:
        cov.save()
    except Exception:
        pass

signal.signal(signal.SIGUSR1, _sigusr1_handler)

# === 5. atexit cleanup ===
def _cleanup():
    try:
        cov.stop()
    except Exception:
        pass
    try:
        cov.save()
    except Exception:
        pass

atexit.register(_cleanup)

# === 6. Start kvmagent ===
from kvmagent import kdaemon
kdaemon.main()
'''


@pytest.fixture(scope='module')
def http_client(request):
    """Start an HttpTestClient for the module, stop on teardown.

    When --direct-host is set, creates a remote-mode client that sends
    requests to the real kvmagent instead of a local stub server.
    """
    direct_host = request.config.getoption('--direct-host', default=None)
    direct_port = request.config.getoption('--direct-port', default=None)

    if direct_host:
        # SSH-poll target: use --callback-ssh-host if set (e.g. when using
        # SSH tunnel with --direct-host 127.0.0.1), else fall back to direct_host.
        ssh_target = (request.config.getoption('--callback-ssh-host', default=None)
                      or direct_host)
        ssh_password = request.config.getoption('--ssh-password', default='password')
        ssh_port = request.config.getoption('--ssh-port', default=22)
        skip_collector = request.config.getoption('--skip-collector-check', default=False)
        if not skip_collector:
            _deploy_callback_collector(ssh_target, ssh_password)
        ssh_run = _make_ssh_run(ssh_target, password=ssh_password, port=ssh_port)

        # When --remote-coverage is active, route HTTP through SSH tunnel
        # (kvmagent rejects non-localhost IPs with 403)
        use_coverage = request.config.getoption('--remote-coverage', default=False)
        http_host = '127.0.0.1' if use_coverage else direct_host
        http_port = 17070 if use_coverage else direct_port

        client = HttpTestClient(
            direct_host=http_host,
            direct_port=http_port,
            ssh_run_fn=ssh_run,
            skip_collector_check=skip_collector,
        )
    else:
        client = HttpTestClient()

    yield client
    client.stop()


@pytest.fixture(autouse=True)
def _handle_remote_xfail(request, http_client):
    """Convert remote_xfail marker to xfail when running in remote mode."""
    marker = request.node.get_closest_marker('remote_xfail')
    if marker and http_client.is_remote:
        reason = (marker.args[0] if marker.args
                  else marker.kwargs.get('reason', 'expected to fail in remote mode'))
        request.node.add_marker(pytest.mark.xfail(reason=reason, strict=False))


# ---------------------------------------------------------------------------
# Stub plugin — mirrors HostPlugin routes in pure Py3
# ---------------------------------------------------------------------------

class _StubAgentResponse:
    def __init__(self, success=True, error=''):
        self.success = success
        self.error = error


class StubHostPlugin:
    """Minimal Py3 stub that registers the same routes as the real HostPlugin.

    Each handler follows the real contract:
      - receives entity = {REQUEST_BODY: json_str, REQUEST_HEADER: dict}
      - returns jsonobject.dumps(response)
    """
    CONNECT_PATH = '/host/connect'
    ECHO_PATH = '/host/echo'
    PING_PATH = '/host/ping'
    CAPACITY_PATH = '/host/capacity'
    FACT_PATH = '/host/fact'

    def __init__(self):
        self.host_uuid = None
        self.config = {}

    # -- handlers --

    def echo(self, req):
        rsp = _StubAgentResponse()
        return jsonobject.dumps(rsp)

    def connect(self, req):
        cmd = jsonobject.loads(req[REQUEST_BODY])
        self.host_uuid = cmd.hostUuid
        self.config['sendCommandUrl'] = cmd.sendCommandUrl
        self.config['version'] = getattr(cmd, 'version', '') or ''
        rsp = _StubAgentResponse()
        return jsonobject.dumps(rsp)

    def ping(self, req):
        rsp = _StubAgentResponse()
        rsp.hostUuid = self.host_uuid
        rsp.sendCommandUrl = self.config.get('sendCommandUrl', '')
        rsp.version = self.config.get('version', '')
        return jsonobject.dumps(rsp)

    def capacity(self, req):
        rsp = _StubAgentResponse()
        rsp.cpuNum = 8
        rsp.totalMemory = 16 * 1024 * 1024 * 1024
        rsp.usedMemory = 4 * 1024 * 1024 * 1024
        rsp.usedCpu = 200
        return jsonobject.dumps(rsp)

    def fact(self, req):
        rsp = _StubAgentResponse()
        rsp.osDistribution = 'linux'
        rsp.osVersion = '3.12'
        return jsonobject.dumps(rsp)


@pytest.fixture(scope='module')
def host_plugin(http_client):
    """Create a StubHostPlugin, register its routes, start the server.

    In remote mode, register calls are no-ops and start() launches the
    callback collector on the remote host instead of a local server.
    The bootstrap /host/connect is verified so async callbacks work.
    """
    plugin = StubHostPlugin()

    # In remote mode these register calls are no-ops
    http_client.register_sync_uri(plugin.CONNECT_PATH, plugin.connect)
    http_client.register_sync_uri(plugin.ECHO_PATH, plugin.echo)
    http_client.register_async_uri(plugin.PING_PATH, plugin.ping)
    http_client.register_async_uri(plugin.CAPACITY_PATH, plugin.capacity)
    http_client.register_async_uri(plugin.FACT_PATH, plugin.fact)

    if not http_client._started:
        http_client.start()

    # In remote mode, verify the bootstrap connect succeeded
    if http_client.is_remote:
        try:
            rsp = http_client.post_sync('/host/echo/', {})
            if not getattr(rsp, 'success', False):
                logger.warning('remote echo failed: %s', getattr(rsp, 'error', ''))
        except Exception as e:
            logger.warning('remote echo check failed: %s', e)

    return plugin


@pytest.fixture(scope='module')
def remote_env(http_client):
    """Discover available resources on the real host for conditional test skipping.

    Returns a dict with discovered resources; tests use this to skip when
    the required resource is absent instead of blanket xfail.
    """
    if not http_client.is_remote:
        yield None
        return

    ssh = http_client._ssh_run
    env = {}

    # Running VMs (from libvirt)
    rc, out, _ = ssh('virsh list --name 2>/dev/null | grep -v "^$" | head -1')
    env['vm_name'] = out.strip() if rc == 0 and out.strip() else None

    if env['vm_name']:
        rc, out, _ = ssh('virsh domuuid %s 2>/dev/null' % env['vm_name'])
        env['vm_uuid'] = out.strip() if rc == 0 and out.strip() else None
    else:
        env['vm_uuid'] = None

    # SR-IOV capable NIC
    rc, out, _ = ssh(
        'find /sys/class/net/*/device/sriov_totalvfs 2>/dev/null | head -1')
    env['sriov_path'] = out.strip() if rc == 0 and out.strip() else None

    # mdev-capable device (GPU)
    rc, out, _ = ssh('ls /sys/class/mdev_bus/ 2>/dev/null | head -1')
    env['mdev_device'] = out.strip() if rc == 0 and out.strip() else None

    # USB devices (non-hub)
    rc, out, _ = ssh(
        'lsusb 2>/dev/null | grep -v "Hub" | head -1')
    env['usb_device'] = out.strip() if rc == 0 and out.strip() else None

    # PCI devices (always present, grab first non-bridge)
    rc, out, _ = ssh(
        'lspci -D 2>/dev/null | grep -v -i bridge | head -1 | cut -d" " -f1')
    env['pci_address'] = out.strip() if rc == 0 and out.strip() else None

    logger.info('remote_env discovered: %s', env)
    yield env


@pytest.fixture(scope='session', autouse=True)
def remote_coverage(request):
    """Inject coverage.py into remote kvmagent when --remote-coverage is set.

    Automates the full coverage collection pipeline:
    1. Install coverage.py if not present
    2. Stop existing kvmagent, deploy coverage runner script
    3. Start kvmagent under coverage (with fork patched out)
    4. Optionally block MN IP via iptables
    5. Set up SSH tunnel (kvmagent rejects non-localhost IPs)
    6. Start periodic local SCP backup
    7. Teardown: SIGUSR1 save, collect data, restore normal kvmagent
    """
    if not request.config.getoption('--remote-coverage', default=False):
        yield None
        return

    host = request.config.getoption('--direct-host')
    if not host:
        logger.warning('--remote-coverage requires --direct-host, skipping')
        yield None
        return

    ssh_host = (request.config.getoption('--callback-ssh-host', default=None)
                or host)
    ssh_password = request.config.getoption('--ssh-password', default='password')
    mn_ip = request.config.getoption('--mn-ip', default=None)
    cov_output = request.config.getoption('--coverage-output',
                                          default='/tmp/cov-backup')

    ssh_run = _make_ssh_run(ssh_host, password=ssh_password)

    # --- 1. Install coverage if needed ---
    rc, _, _ = ssh_run(
        '/var/lib/zstack/virtualenv/kvm/bin/python -c "import coverage" 2>&1'
    )
    if rc != 0:
        logger.info('Installing coverage.py on remote...')
        ssh_run('/var/lib/zstack/virtualenv/kvm/bin/pip install coverage')

    # --- 2. Deploy coverage runner + callback_collector ---
    runner_script = _generate_coverage_runner()
    _deploy_remote_file(ssh_host, ssh_password, runner_script,
                        '/tmp/run_kvm_coverage.py')
    logger.info('Deployed coverage runner script')

    collector_local = str(
        _repo_root / 'tests' / 'http' / 'scripts' / 'callback_collector.py'
    )
    collector_remote = (
        '/tmp/zstack-test/zstack-utility/tests/http/scripts/callback_collector.py'
    )
    ssh_run('mkdir -p /tmp/zstack-test/zstack-utility/tests/http/scripts')
    if os.path.exists(collector_local):
        subprocess.run(
            ['sshpass', '-p', ssh_password, 'scp',
             '-o', 'StrictHostKeyChecking=no',
             collector_local,
             'root@%s:%s' % (ssh_host, collector_remote)],
            capture_output=True, timeout=30,
        )
        logger.info('Deployed callback_collector.py')

    # --- 3. Block MN if requested ---
    mn_blocked = False
    if mn_ip:
        ssh_run('iptables -I INPUT -s %s -j DROP' % mn_ip)
        mn_blocked = True
        logger.info('Blocked MN IP: %s', mn_ip)

    # --- 4. Stop existing kvmagent, start under coverage ---
    ssh_run('rm -f /tmp/.coverage.kvmagent')
    # Stop existing kvmagent (ignore errors if not running)
    ssh_run('systemctl stop zstack-kvmagent 2>/dev/null; '
            'pkill -f "from kvmagent import kdaemon" 2>/dev/null; '
            'sleep 2')

    # Start kvmagent under our coverage runner (no fork, with periodic save)
    ssh_run(
        'nohup /var/lib/zstack/virtualenv/kvm/bin/python '
        '/tmp/run_kvm_coverage.py start '
        '> /tmp/kvmagent-cov.log 2>&1 &'
    )

    # Record the PID for later cleanup
    kvm_pid = None
    for _i in range(30):
        time.sleep(1)
        rc, out, _ = ssh_run('ss -tlnp | grep 7070')
        if rc == 0 and '7070' in out:
            # Extract PID from ss output
            rc2, pid_out, _ = ssh_run(
                'pgrep -f "run_kvm_coverage.py" | head -1')
            kvm_pid = pid_out.strip() if rc2 == 0 else None
            break
    else:
        logger.error('kvmagent failed to start with coverage after 30s')
        yield None
        return
    logger.info('kvmagent started with coverage (PID=%s, took ~%ds)',
                kvm_pid, _i + 1)

    # --- 5. Start SSH tunnel (kvmagent rejects non-localhost IPs) ---
    tunnel_port = 17070
    tunnel_proc = subprocess.Popen(
        ['sshpass', '-p', ssh_password, 'ssh',
         '-o', 'StrictHostKeyChecking=no',
         '-L', '%d:127.0.0.1:7070' % tunnel_port,
         '-N', 'root@%s' % ssh_host],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    import socket
    for _t in range(10):
        time.sleep(0.5)
        try:
            with socket.create_connection(('127.0.0.1', tunnel_port), timeout=1):
                break
        except OSError:
            pass
    else:
        logger.error('SSH tunnel failed to establish on port %d', tunnel_port)
    logger.info('SSH tunnel: localhost:%d -> %s:7070', tunnel_port, ssh_host)

    # --- 6. Start local SCP backup thread ---
    os.makedirs(cov_output, exist_ok=True)
    _stop_backup = threading.Event()

    def _backup_loop():
        while not _stop_backup.is_set():
            try:
                _scp_from_remote(
                    ssh_host, ssh_password,
                    '/tmp/.coverage.kvmagent',
                    os.path.join(cov_output, '.coverage.kvmagent.latest'),
                )
            except Exception:
                pass
            _stop_backup.wait(20)

    backup_thread = threading.Thread(target=_backup_loop, daemon=True)
    backup_thread.start()
    logger.info('Coverage backup loop started (every 20s -> %s)', cov_output)

    yield {
        'cov_output': cov_output,
        'tunnel_port': tunnel_port,
        'kvm_pid': kvm_pid,
    }

    # --- Teardown ---
    logger.info('Collecting final coverage data...')
    _stop_backup.set()

    # Trigger final save via SIGUSR1
    if kvm_pid:
        ssh_run('kill -USR1 %s' % kvm_pid)
        time.sleep(2)

    # Final SCP
    try:
        _scp_from_remote(
            ssh_host, ssh_password,
            '/tmp/.coverage.kvmagent',
            os.path.join(cov_output, '.coverage.kvmagent.final'),
        )
        logger.info('Final coverage data saved to %s', cov_output)
    except Exception as e:
        logger.warning('Final coverage SCP failed: %s', e)

    # Kill SSH tunnel
    if tunnel_proc and tunnel_proc.poll() is None:
        tunnel_proc.terminate()
        tunnel_proc.wait(timeout=5)
        logger.info('SSH tunnel terminated')

    # Kill coverage kvmagent
    if kvm_pid:
        ssh_run('kill -9 %s 2>/dev/null' % kvm_pid)
        time.sleep(1)

    # Unblock MN
    if mn_blocked:
        ssh_run('iptables -D INPUT -s %s -j DROP' % mn_ip)
        logger.info('Unblocked MN IP: %s', mn_ip)

    # Restart kvmagent clean
    ssh_run('systemctl start zstack-kvmagent')
    logger.info('Restored kvmagent without coverage')
