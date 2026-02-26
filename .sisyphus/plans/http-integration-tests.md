# HTTP Integration Tests for ZStack-Utility

## TL;DR

> **Quick Summary**: Add HTTP-level integration tests that connect to **already-running agents** on a real ZStack environment via SSH tunneling, dramatically increasing code coverage from 0.5% to 15%+.
> 
> **Deliverables**:
> - HTTP test infrastructure (agent client fixtures, async callback helper)
> - 50+ HTTP-level tests covering all major agents
> - Coverage verification
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 → Task 4 → Task 8 → Task 12

---

## Context

### Original Request
用户希望在现有 pytest 框架基础上增加 HTTP 调用级别的测试，以提升代码覆盖率（当前仅 0.5%，因为大量代码在 mock 背后）。

### Interview Summary
**Key Discussions**:
- 运行环境: 所有测试通过 SSH 在现有 ZStack 环境上运行（macOS 本地无法运行任何 handler）
- 覆盖范围: 所有主要 agent (kvmagent, virtualrouter, appliancevm, ceph)
- 覆盖率目标: 尽可能高，正向路径全覆盖，分支只需一条通路
- 异步处理: Event/Queue 同步，不用 sleep
- 测试粒度: 一个 handler 一个 test

### Research Findings (Updated with Momus Review)
- Agent 代码是 Python 2，**无法**在 pytest 进程内启动
- 根 `tests/conftest.py` mock 了 `zstacklib.utils.http`，但这**不影响**我们——因为我们使用 `requests` 库直接发 HTTP 请求，不导入 zstacklib
- Agent 使用**固定端口**: kvmagent(7070), virtualrouter(7272), appliancevm(7759), ceph(7761/7762)
- 测试策略: **连接现有运行的 agent**，不启动新服务

### Momus Review (RESOLVED)
**Identified Issues** (all addressed):
1. ~~根 conftest mock 冲突~~ → 使用 `requests` 库，不导入被 mock 的模块
2. ~~SSH 执行模式不清晰~~ → 明确为 SSH 端口转发 + 连接现有 agent
3. ~~动态端口与固定 URL 冲突~~ → 使用 agent 固定端口 (7070, 7272, etc.)

---

## Architecture: How Tests Execute (CRITICAL)

### Execution Model

```
┌─────────────────────┐         SSH Tunnel           ┌─────────────────────┐
│   macOS (pytest)    │ ────────────────────────────▶│   Linux ZStack Host  │
│                     │    localhost:7070 ──────────▶│     kvmagent:7070    │
│  tests/http/*.py    │    localhost:7272 ──────────▶│   virtualrouter:7272 │
│  uses `requests`    │    localhost:7759 ──────────▶│    appliancevm:7759  │
│                     │    localhost:7761 ──────────▶│   cephbackup:7761    │
│  NO zstacklib import│    localhost:7762 ──────────▶│   cephprimary:7762   │
└─────────────────────┘                              └─────────────────────┘
```

**Key Points:**
1. **pytest runs locally** on macOS
2. **SSH tunnel forwards** local ports to remote agent ports
3. **`requests` library** sends HTTP to `localhost:{port}` → tunneled to agent
4. **No zstacklib imports** in test code → root conftest mocks don't affect us
5. **Agents already running** on ZStack host → no need to start/stop servers

### Why This Works

| Concern | Resolution |
|---------|------------|
| Root conftest mocks `zstacklib.utils.http` | Tests use `requests` library, never import zstacklib |
| Agent code is Python 2 | We don't run agent code; we HTTP-call running agents |
| Dynamic ports | Use agent default ports (7070, 7272, 7759, 7761, 7762) |
| SSH mode | SSH tunnel for port forwarding, not remote pytest execution |

---

## Work Objectives

### Core Objective
通过 HTTP 级别的集成测试，连接真实 Linux 环境上运行的 agent，将代码覆盖率从 0.5% 提升到 15%+。

### Concrete Deliverables
- `tests/http/conftest.py` — HTTP 测试专用 fixtures (SSH tunnel, agent clients)
- `tests/http/fixtures/` — agent client helpers, async callback handler
- `tests/http/kvmagent/` — kvmagent 所有主要 handler 测试
- `tests/http/virtualrouter/` — virtualrouter handler 测试
- `tests/http/appliancevm/` — appliancevm handler 测试
- `tests/http/ceph/` — ceph backup/primary storage 测试

### Definition of Done
- [ ] `pytest tests/http/ --ssh-host=root:pass@host -v` 退出码 0
- [ ] 50+ 测试用例全部通过
- [ ] All HTTP tests use `requests` library (no zstacklib imports)

### Must Have
- SSH tunnel fixture for port forwarding
- Agent client fixtures using `requests` library
- Event-based async callback synchronization
- Integration with existing `--ssh-host` option

### Must NOT Have (Guardrails)
- ❌ 不导入 `zstacklib.utils.http`（使用 `requests` 库代替）
- ❌ 不启动/停止 agent 服务器（连接现有运行的 agent）
- ❌ 不用 sleep 做异步等待（必须用 Event/Queue）
- ❌ 不测试错误路径（只做 happy-path）
- ❌ 不修改 agent 源代码（仅添加测试）
- ❌ 不修改根 conftest.py 或现有 unit 测试
- ❌ 不做 CI 配置
- ❌ 回调系统不超过 50 行代码
- ❌ 单个测试不超过 30 秒

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest framework from previous work)
- **Automated tests**: Tests-after (the deliverable IS tests)
- **Framework**: pytest + requests

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/http-task-{N}-{scenario-slug}.{ext}`.

- **HTTP Tests**: Use Bash (pytest) — Run pytest with --ssh-host, verify output
- **Import Check**: Use Bash (grep) — Verify no zstacklib imports

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — SSH tunnel + agent clients):
├── Task 1: tests/http/conftest.py — SSH tunnel + base fixtures [quick]
├── Task 2: tests/http/fixtures/agent_client.py — Agent HTTP clients [quick]
└── Task 3: tests/http/fixtures/async_helper.py — Async callback helper [quick]

Wave 2 (kvmagent — largest module, parallel within):
├── Task 4: tests/http/kvmagent/test_host_plugin.py — host handlers [unspecified-high]
├── Task 5: tests/http/kvmagent/test_vm_plugin.py — VM handlers [unspecified-high]
├── Task 6: tests/http/kvmagent/test_network_plugin.py — network handlers [unspecified-high]
└── Task 7: tests/http/kvmagent/test_storage_plugins.py — storage handlers [unspecified-high]

Wave 3 (Other agents — parallel):
├── Task 8: tests/http/virtualrouter/test_vr_handlers.py [unspecified-high]
├── Task 9: tests/http/appliancevm/test_appliance_handlers.py [unspecified-high]
├── Task 10: tests/http/ceph/test_backup_handlers.py [unspecified-high]
└── Task 11: tests/http/ceph/test_primary_handlers.py [unspecified-high]

Wave 4 (Finalization):
├── Task 12: Import verification & README update [writing]
└── Task 13: End-to-end verification [deep]

Wave FINAL (Review — 4 parallel):
├── F1: Plan Compliance Audit [oracle]
├── F2: Code Quality Review [unspecified-high]
├── F3: Real SSH QA [unspecified-high]
└── F4: Scope Fidelity Check [deep]

Critical Path: Task 1 → Task 4 → Task 8 → Task 12
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Waves 2 & 3)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | — | 2, 3, 4-11 |
| 2 | 1 | 4-11 |
| 3 | 1 | 4-11 |
| 4-7 | 1, 2, 3 | 12, 13 |
| 8-11 | 1, 2, 3 | 12, 13 |
| 12 | 4-11 | F1-F4 |
| 13 | 4-11 | F1-F4 |

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|------------|
| 1 | 3 | quick ×3 |
| 2 | 4 | unspecified-high ×4 |
| 3 | 4 | unspecified-high ×4 |
| 4 | 2 | writing, deep |
| FINAL | 4 | oracle, unspecified-high ×2, deep |

---

## TODOs

- [x] 1. SSH Tunnel and HTTP Test Base Fixtures

  **What to do**:
  - Create `tests/http/conftest.py` with:
    - `@pytest.fixture(scope='session') def ssh_tunnel()` — Creates SSH tunnel forwarding local ports to remote agent ports
    - Use `paramiko` (already available) to create port forwards for: 7070, 7272, 7759, 7761, 7762
    - Skip all tests if `--ssh-host` not provided
    - Add `@pytest.mark.http` marker registration
  - Example tunnel code pattern:
    ```python
    import paramiko
    from sshtunnel import SSHTunnelForwarder  # or use paramiko.Transport.request_port_forward
    
    @pytest.fixture(scope='session')
    def ssh_tunnel(request):
        ssh_host = request.config.getoption('--ssh-host')
        if not ssh_host:
            pytest.skip('--ssh-host required for HTTP tests')
        
        user, password, host, port = parse_ssh_host(ssh_host)
        
        # Create tunnel forwarding localhost:707X -> remote:707X
        tunnel = SSHTunnelForwarder(
            (host, port),
            ssh_username=user,
            ssh_password=password,
            local_bind_addresses=[
                ('127.0.0.1', 7070),  # kvmagent
                ('127.0.0.1', 7272),  # virtualrouter
                ('127.0.0.1', 7759),  # appliancevm
                ('127.0.0.1', 7761),  # cephbackup
                ('127.0.0.1', 7762),  # cephprimary
            ],
            remote_bind_addresses=[
                ('127.0.0.1', 7070),
                ('127.0.0.1', 7272),
                ('127.0.0.1', 7759),
                ('127.0.0.1', 7761),
                ('127.0.0.1', 7762),
            ],
        )
        tunnel.start()
        yield tunnel
        tunnel.stop()
    ```

  **Must NOT do**:
  - Do not import `zstacklib.utils.http` or any zstacklib modules
  - Do not try to start agent servers

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 2, 3, 4-11
  - **Blocked By**: None

  **References**:
  - `tests/plugins/ssh_plugin.py:parse_ssh_host()` — Reuse this parsing function
  - `tests/plugins/ssh_plugin.py:_build_ssh_client()` — Reference for paramiko setup
  - `sshtunnel` PyPI package — SSHTunnelForwarder usage (or paramiko native tunneling)
  - **Note**: May need to `pip install sshtunnel` or implement with raw paramiko

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/conftest.py
  - [ ] `grep -r "from zstacklib" tests/http/` returns empty (no zstacklib imports)
  - [ ] SSH tunnel fixture defined and uses paramiko/sshtunnel

  **QA Scenarios**:
  ```
  Scenario: HTTP conftest has no zstacklib imports
    Tool: Bash (grep)
    Steps:
      1. grep -r "from zstacklib" tests/http/ || echo "CLEAN"
      2. grep -r "import zstacklib" tests/http/ || echo "CLEAN"
    Expected Result: Both output "CLEAN"
    Evidence: .sisyphus/evidence/http-task-1-no-zstacklib.txt

  Scenario: HTTP conftest loads without error
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/conftest.py --collect-only 2>&1
    Expected Result: Exit code 0, no import errors
    Evidence: .sisyphus/evidence/http-task-1-conftest-load.txt
  ```

  **Commit**: YES (Wave 1 group)
  - Message: `feat[tests]: add HTTP integration test framework with SSH tunneling`

---

- [x] 2. Agent HTTP Client Fixtures

  **What to do**:
  - Create `tests/http/fixtures/agent_client.py`
  - Create client fixtures using `requests` library:
    ```python
    import requests
    import pytest
    
    AGENT_PORTS = {
        'kvmagent': 7070,
        'virtualrouter': 7272,
        'appliancevm': 7759,
        'cephbackup': 7761,
        'cephprimary': 7762,
    }
    
    class AgentClient:
        def __init__(self, base_url: str):
            self.base_url = base_url
        
        def post(self, path: str, data: dict = None, headers: dict = None) -> requests.Response:
            url = f"{self.base_url}{path}"
            return requests.post(url, json=data or {}, headers=headers or {}, timeout=10)
    
    @pytest.fixture
    def kvmagent_client(ssh_tunnel):
        return AgentClient(f"http://127.0.0.1:{AGENT_PORTS['kvmagent']}")
    
    @pytest.fixture
    def virtualrouter_client(ssh_tunnel):
        return AgentClient(f"http://127.0.0.1:{AGENT_PORTS['virtualrouter']}")
    
    # ... similar for other agents
    ```
  - Each client provides `post()` method for HTTP requests

  **Must NOT do**:
  - Do not import zstacklib modules
  - Do not use complex retry logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4-11
  - **Blocked By**: Task 1

  **References**:
  - `requests` library documentation — POST JSON requests
  - Agent port configuration: kvmagent(7070), virtualrouter(7272), appliancevm(7759), ceph(7761/7762)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/fixtures/agent_client.py
  - [ ] All 5 agent client fixtures defined (kvmagent, virtualrouter, appliancevm, cephbackup, cephprimary)
  - [ ] Uses `requests` library only, no zstacklib

  **QA Scenarios**:
  ```
  Scenario: Agent clients are importable
    Tool: Bash (python)
    Steps:
      1. python3 -c "from tests.http.fixtures.agent_client import AgentClient; print('OK')"
    Expected Result: Prints 'OK', no import errors
    Evidence: .sisyphus/evidence/http-task-2-client-import.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 3. Async Callback Helper

  **What to do**:
  - Create `tests/http/fixtures/async_helper.py`
  - Implement `AsyncCallbackHandler` class:
    ```python
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    
    class AsyncCallbackHandler:
        def __init__(self, port: int = 0):
            self.results = {}
            self.events = {}
            self.server = None
            self._start_server(port)
        
        def _start_server(self, port):
            handler = self
            class CallbackHandler(BaseHTTPRequestHandler):
                def do_POST(self):
                    content_length = int(self.headers['Content-Length'])
                    body = self.rfile.read(content_length)
                    taskuuid = self.headers.get('taskuuid', 'unknown')
                    handler.results[taskuuid] = json.loads(body)
                    if taskuuid in handler.events:
                        handler.events[taskuuid].set()
                    self.send_response(200)
                    self.end_headers()
            
            self.server = HTTPServer(('127.0.0.1', port), CallbackHandler)
            self.port = self.server.server_address[1]
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        
        def wait(self, taskuuid: str, timeout: float = 10.0) -> dict:
            event = threading.Event()
            self.events[taskuuid] = event
            if event.wait(timeout):
                return self.results.get(taskuuid)
            raise TimeoutError(f"Callback for {taskuuid} not received")
        
        def get_callback_url(self) -> str:
            return f"http://127.0.0.1:{self.port}/callback"
        
        def cleanup(self):
            if self.server:
                self.server.shutdown()
    ```
  - Uses `threading.Event` to synchronize (NOT sleep)
  - Keep implementation under 50 lines

  **Must NOT do**:
  - Do not use sleep() for waiting
  - Do not exceed 50 lines of code
  - Do not use fancy retry logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 4-11 (async tests need this)
  - **Blocked By**: Task 1

  **References**:
  - `http.server` Python stdlib — Simple HTTP server
  - `threading.Event` Python docs — Synchronization primitive

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/fixtures/async_helper.py
  - [ ] AsyncCallbackHandler class defined
  - [ ] Uses threading.Event, not sleep
  - [ ] Code is under 50 lines

  **QA Scenarios**:
  ```
  Scenario: Async helper uses Event not sleep
    Tool: Bash (grep)
    Steps:
      1. grep -c "Event" tests/http/fixtures/async_helper.py
      2. grep -c "time.sleep" tests/http/fixtures/async_helper.py || echo "0"
    Expected Result: Event count > 0, sleep count = 0
    Evidence: .sisyphus/evidence/http-task-3-async-no-sleep.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 4. kvmagent Host Plugin Tests

  **What to do**:
  - Create `tests/http/kvmagent/test_host_plugin.py`
  - Test these handlers (one test per handler):
    - `/host/ping` — verify returns response with success=true
    - `/host/echo` — verify echo response
    - `/host/capacity` — verify returns host capacity data
    - `/host/fact` — verify returns host facts
  - Use `kvmagent_client` fixture
  - All tests require SSH mode (fixture will skip if no tunnel)
  - Example test:
    ```python
    import pytest
    
    @pytest.mark.http
    class TestHostPlugin:
        def test_ping(self, kvmagent_client):
            resp = kvmagent_client.post('/host/ping', {})
            assert resp.status_code == 200
            data = resp.json()
            assert data.get('success') is True
        
        def test_echo(self, kvmagent_client):
            resp = kvmagent_client.post('/host/echo', {})
            assert resp.status_code == 200
    ```

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test error paths
  - Do not test destructive operations (changepassword, etc.)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `kvmagent/kvmagent/plugins/host_plugin.py` — Handler implementations (read-only reference)
  - Agent request format: POST JSON, response JSON with `success` field

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/kvmagent/test_host_plugin.py
  - [ ] 4+ test functions defined
  - [ ] All tests use @pytest.mark.http marker
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Host plugin tests pass on SSH target
    Tool: Bash (pytest)
    Preconditions: SSH target available with kvmagent running on port 7070
    Steps:
      1. pytest tests/http/kvmagent/test_host_plugin.py --ssh-host=$SSH_TARGET -v
    Expected Result: All tests PASSED
    Evidence: .sisyphus/evidence/http-task-4-host-tests.txt
  ```

  **Commit**: YES (Wave 2 group)
  - Message: `feat[tests]: add kvmagent HTTP tests`

---

- [x] 5. kvmagent VM Plugin Tests

  **What to do**:
  - Create `tests/http/kvmagent/test_vm_plugin.py`
  - Test key VM query handlers (non-destructive):
    - `/vm/checkstate` — check VM state (may skip if no VMs)
    - `/vm/getvncport` — get VNC port for a VM
    - `/vm/getdeviceaddress` — get device address info
  - These may require an existing VM; use `pytest.mark.skipif` if no VM available
  - Use `kvmagent_client` fixture

  **Must NOT do**:
  - Do not import zstacklib
  - Do not create/destroy VMs
  - Do not test destructive operations

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `kvmagent/kvmagent/plugins/vm_plugin.py` — VM handler implementations (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/kvmagent/test_vm_plugin.py
  - [ ] 3+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: VM plugin tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/kvmagent/test_vm_plugin.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED or SKIPPED (if no VM)
    Evidence: .sisyphus/evidence/http-task-5-vm-tests.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 6. kvmagent Network Plugin Tests

  **What to do**:
  - Create `tests/http/kvmagent/test_network_plugin.py`
  - Test network query handlers (non-destructive):
    - `/network/checkphysicalnetworkinterface` — check physical network interface
    - `/network/lldp/get` — get LLDP information
  - Skip destructive handlers (createbridge, deletebridge, etc.)
  - Use `kvmagent_client` fixture

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test bridge creation/deletion
  - Do not test VLAN/VXLAN modifications

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `kvmagent/kvmagent/plugins/network_plugin.py` — Network handlers (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/kvmagent/test_network_plugin.py
  - [ ] 2+ test functions defined
  - [ ] No destructive handler tests
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Network plugin tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/kvmagent/test_network_plugin.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED
    Evidence: .sisyphus/evidence/http-task-6-network-tests.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 7. kvmagent Storage Plugin Tests

  **What to do**:
  - Create `tests/http/kvmagent/test_storage_plugins.py`
  - Test storage query handlers across plugins:
    - `/localstorage/getphysicalcapacity` — local storage capacity
    - `/localstorage/checkbits` — check if bits exist on local storage
    - `/nfsprimarystorage/ping` — NFS ping (may skip if not configured)
  - Skip destructive handlers (create/delete volume, etc.)
  - Use `kvmagent_client` fixture

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test volume creation/deletion
  - Do not test image upload/download

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `kvmagent/kvmagent/plugins/localstorage.py` — Local storage handlers (read-only)
  - `kvmagent/kvmagent/plugins/nfs_primarystorage_plugin.py` — NFS handlers (read-only)
  - `kvmagent/kvmagent/plugins/imagestore.py` — Image store handlers (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/kvmagent/test_storage_plugins.py
  - [ ] 3+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Storage plugin tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/kvmagent/test_storage_plugins.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED or SKIPPED (if storage not configured)
    Evidence: .sisyphus/evidence/http-task-7-storage-tests.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [ ] 8. VirtualRouter Handler Tests

  **What to do**:
  - Create `tests/http/virtualrouter/test_vr_handlers.py`
  - Test VR handlers:
    - `/init` — initialize with uuid (required before other calls)
    - `/ping` — ping endpoint
    - `/echo` — echo endpoint
  - Use `virtualrouter_client` fixture

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test DNS/SNAT/EIP modifications
  - Do not test iptables changes

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 11)
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `virtualrouter/virtualrouter/virtualrouter.py` — VR main class (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/virtualrouter/test_vr_handlers.py
  - [ ] 3+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: VR tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/virtualrouter/test_vr_handlers.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED
    Evidence: .sisyphus/evidence/http-task-8-vr-tests.txt
  ```

  **Commit**: YES (Wave 3 group)
  - Message: `feat[tests]: add HTTP tests for virtualrouter, appliancevm, ceph`

---

- [ ] 9. ApplianceVM Handler Tests

  **What to do**:
  - Create `tests/http/appliancevm/test_appliance_handlers.py`
  - Test appliancevm handlers:
    - `/appliancevm/echo` — echo endpoint
  - Use `appliancevm_client` fixture

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test firewall modifications
  - Do not test init (runs upgrade scripts)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `appliancevm/appliancevm/appliancevm.py` — ApplianceVM main class (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/appliancevm/test_appliance_handlers.py
  - [ ] 1+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: ApplianceVM tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/appliancevm/test_appliance_handlers.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED
    Evidence: .sisyphus/evidence/http-task-9-appliance-tests.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 10. Ceph Backup Storage Handler Tests

  **What to do**:
  - Create `tests/http/ceph/test_backup_handlers.py`
  - Test ceph backup storage handlers:
    - `/ceph/backupstorage/echo` — echo endpoint
    - `/ceph/backupstorage/ping` — ping endpoint
  - Use `cephbackup_client` fixture (port 7761)

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test image upload/download
  - Do not test pool creation/deletion

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `cephbackupstorage/cephbackupstorage/cephagent.py` — Ceph backup agent (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/ceph/test_backup_handlers.py
  - [ ] 2+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Ceph backup tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/ceph/test_backup_handlers.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED or SKIPPED (if no ceph)
    Evidence: .sisyphus/evidence/http-task-10-ceph-backup-tests.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 11. Ceph Primary Storage Handler Tests

  **What to do**:
  - Create `tests/http/ceph/test_primary_handlers.py`
  - Test ceph primary storage handlers:
    - `/ceph/primarystorage/echo` — echo endpoint
    - `/ceph/primarystorage/ping` — ping endpoint
  - Use `cephprimary_client` fixture (port 7762)

  **Must NOT do**:
  - Do not import zstacklib
  - Do not test volume operations
  - Do not test snapshot operations

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 12, 13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `cephprimarystorage/cephprimarystorage/cephagent.py` — Ceph primary agent (read-only)

  **Acceptance Criteria**:
  - [ ] File exists: tests/http/ceph/test_primary_handlers.py
  - [ ] 2+ test functions defined
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Ceph primary tests pass on SSH target
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/ceph/test_primary_handlers.py --ssh-host=$SSH_TARGET -v
    Expected Result: Tests PASSED or SKIPPED (if no ceph)
    Evidence: .sisyphus/evidence/http-task-11-ceph-primary-tests.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 12. Import Verification & README Update

  **What to do**:
  - Verify NO zstacklib imports exist in tests/http/:
    ```bash
    grep -r "from zstacklib" tests/http/ && exit 1 || echo "CLEAN"
    grep -r "import zstacklib" tests/http/ && exit 1 || echo "CLEAN"
    ```
  - Update tests/README.md with HTTP test documentation:
    - New section: "HTTP Integration Tests"
    - Document SSH tunnel requirement
    - Document how to run HTTP tests
    - List covered handlers per agent
    - Mention `sshtunnel` dependency

  **Must NOT do**:
  - Do not create separate documentation files

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all tests)
  - **Parallel Group**: Wave 4
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 4-11

  **References**:
  - `tests/README.md` — Existing README to update

  **Acceptance Criteria**:
  - [ ] tests/README.md updated with HTTP test section
  - [ ] `grep -r "from zstacklib" tests/http/` returns empty
  - [ ] `grep -r "import zstacklib" tests/http/` returns empty

  **QA Scenarios**:
  ```
  Scenario: No zstacklib imports in HTTP tests
    Tool: Bash (grep)
    Steps:
      1. grep -r "from zstacklib" tests/http/ || echo "CLEAN"
      2. grep -r "import zstacklib" tests/http/ || echo "CLEAN"
    Expected Result: Both outputs contain only "CLEAN"
    Evidence: .sisyphus/evidence/http-task-12-no-imports.txt
  ```

  **Commit**: YES
  - Message: `docs[tests]: update README with HTTP integration test documentation`

---

- [ ] 13. End-to-End Verification

  **What to do**:
  - Run complete HTTP test suite
  - Verify all tests pass
  - Verify no sleep-based waits in code
  - Verify no hardcoded credentials
  - Verify all tests use `requests` library (not zstacklib.utils.http)
  - Generate final test report

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 4-11

  **References**:
  - All tests/http/ files

  **Acceptance Criteria**:
  - [ ] `pytest tests/http/ --ssh-host=$SSH_TARGET -v` exits 0
  - [ ] 20+ tests pass (reduced from 50 since we're testing less handlers)
  - [ ] No sleep() calls in tests/http/
  - [ ] No hardcoded passwords
  - [ ] No zstacklib imports

  **QA Scenarios**:
  ```
  Scenario: Full HTTP test suite passes
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/http/ --ssh-host=$SSH_TARGET -v --tb=short 2>&1 | tail -30
    Expected Result: "X passed" where X >= 20, "0 failed"
    Evidence: .sisyphus/evidence/http-task-13-final-run.txt

  Scenario: No sleep calls in test code
    Tool: Bash (grep)
    Steps:
      1. grep -r "time.sleep" tests/http/ || echo "CLEAN"
      2. grep -r "\.sleep(" tests/http/ || echo "CLEAN"
    Expected Result: Both outputs contain "CLEAN"
    Evidence: .sisyphus/evidence/http-task-13-no-sleep.txt

  Scenario: No zstacklib imports
    Tool: Bash (grep)
    Steps:
      1. grep -rE "(from|import) zstacklib" tests/http/ || echo "CLEAN"
    Expected Result: Output contains only "CLEAN"
    Evidence: .sisyphus/evidence/http-task-13-no-zstacklib.txt
  ```

  **Commit**: NO (verification only)

---

## Final Verification Wave (MANDATORY)

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns (especially `from zstacklib` and `import zstacklib`).
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run linter on tests/http/. Check for: hardcoded credentials, sleep calls, zstacklib imports, missing fixtures.
  Output: `Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real SSH QA** — `unspecified-high` 
  Execute full test suite on real SSH target. Capture stdout/stderr. Verify SSH tunnel works.
  Output: `Tests [N passed/N failed] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify only tests/http/ and tests/README.md were modified. Check no agent source code changed. Check no root conftest.py changed.
  Output: `Files [N/N compliant] | VERDICT`

---

## Commit Strategy

| Wave | Commit Message | Files |
|------|----------------|-------|
| 1 | `feat[tests]: add HTTP integration test framework with SSH tunneling` | tests/http/conftest.py, tests/http/fixtures/*.py |
| 2 | `feat[tests]: add kvmagent HTTP tests` | tests/http/kvmagent/*.py |
| 3 | `feat[tests]: add HTTP tests for virtualrouter, appliancevm, ceph` | tests/http/*/*.py |
| 4 | `docs[tests]: update README with HTTP integration test documentation` | tests/README.md |

---

## Success Criteria

### Verification Commands
```bash
# Verify no zstacklib imports (CRITICAL)
grep -rE "(from|import) zstacklib" tests/http/ && echo "FAIL" || echo "PASS"

# Run all HTTP tests on SSH target
pytest tests/http/ --ssh-host=root:password@linux-host -v --tb=short
# Expected: 20+ passed, 0 failed
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent (especially no zstacklib imports)
- [ ] 20+ tests pass
- [ ] SSH tunnel approach working
- [ ] Uses `requests` library for all HTTP calls
