# KVMAgent 测试指南

## 测试分层

```
test/
├── unit/                    # 纯单元测试 (mock 一切外部依赖)
├── http/                    # HTTP 集成测试 (插件路由级别)
│   ├── conftest.py          # 核心 fixtures: http_client, remote_coverage, remote_env
│   ├── test_host_plugin_http.py
│   ├── test_vm_plugin_http.py
│   ├── test_network_plugin_http.py
│   └── ...
├── integration/             # 集成测试 (需要部分真实环境)
├── *_testsuite/             # 遗留测试套件 (逐步迁移到 http/)
└── test_*.py                # 遗留独立测试文件
```

| 层级 | 依赖 | 速度 | 运行方式 |
|------|------|------|---------|
| unit | 无 | 秒级 | `pytest test/unit/` |
| http (local) | 无，Py3 stub server | 秒级 | `pytest test/http/` |
| http (remote) | 真实 kvmagent | 分钟级 | `pytest test/http/ --direct-host <IP>` |
| *_testsuite | 视情况 | 分钟级 | `pytest test/<suite>/` |

## 常用命令

### 本地跑全部 (不需要真实环境)

```bash
cd zstack-utility
python -m pytest kvmagent/kvmagent/test/http/ -v
```

Py3 stub server 模拟 kvmagent 路由，验证请求/响应契约。

### 对真实 kvmagent 跑

```bash
python -m pytest kvmagent/kvmagent/test/http/ \
  --direct-host 172.25.x.x \
  --ssh-password password \
  -v
```

发真实 HTTP 请求到运行中的 kvmagent。缺少特定资源 (VM、SR-IOV、mdev) 的测试会 **自动 skip**，不会 xfail。

### 对真实环境跑存储迁移观测用例

```bash
python -m pytest kvmagent/kvmagent/test/http/test_vm_storage_migration_http.py \
  --direct-host <当前源host管理IP> \
  --callback-ssh-host <当前源host管理IP> \
  --ssh-password password \
  --mn-url http://<mn-ip>:8080/zstack \
  --mn-password <mn-password> \
  --storage-migrate-vm-uuid <vm-uuid> \
  --storage-migrate-dst-ps-uuid <dst-ps-uuid> \
  --storage-migrate-dst-host-uuid <dst-host-uuid> \
  --storage-migrate-bandwidth 16777216 \
  -v
```

说明：

- `--direct-host` 必须指向 **迁移发起时的源 host**
- 用例会通过 `MN API` 触发 `PrimaryStorageMigrateVm`
- 请求体会显式带 `withSnapshots=false`、`withDataVolumes=false`
- 用例会同时轮询：
  - `MN api-job`
  - 源 host 上的 `query-block-jobs`
  - `/vm/volume/queryblockjobstatus`

### 带 coverage 跑 (全自动)

```bash
python -m pytest kvmagent/kvmagent/test/http/ \
  --direct-host 172.25.x.x \
  --ssh-password password \
  --remote-coverage \
  --mn-ip 172.25.y.y \
  -v
```

一条命令自动完成：

| 步骤 | 做了什么 |
|------|---------|
| 装 coverage | `pip install coverage` (如果没装) |
| 部署 runner 脚本 | 含 Daemon.daemonize no-fork 补丁 + 内联 coverage |
| 阻断 MN | `iptables -I INPUT -s <MN_IP> -j DROP` (防止 MN 干扰) |
| 启动 kvmagent | 在 coverage 下运行 (无 fork，同进程追踪 HTTP handler) |
| SSH 隧道 | `localhost:17070 → host:7070` (绕过 kvmagent IP 白名单) |
| 本地备份 | 每 20s SCP `.coverage` 文件到本地 (防 host 被回收) |
| 跑完后清理 | SIGUSR1 保存数据、SCP 回收、kill 进程、解除 iptables、重启 clean kvmagent |

> **技术细节**: kvmagent 的 `Daemon.daemonize()` 做 double-fork，fork 后的子进程会丢失
> coverage tracer。runner 脚本补丁掉 fork 但保留其他初始化。`source=["kvmagent"]`
> 用包名而非路径，避免 virtualenv `lib/` vs `lib64/` 软链接导致 should_trace 路径不匹配。

Coverage 输出在 `/tmp/cov-backup/`，可用 `--coverage-output` 覆盖。

## CLI 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--direct-host` | None | 真实 kvmagent IP (启用 remote 模式) |
| `--direct-port` | 7070 | kvmagent 端口 |
| `--callback-ssh-host` | 同 direct-host | SSH 目标 (用 SSH tunnel 时需要) |
| `--ssh-password` | `password` | SSH 密码 |
| `--skip-collector-check` | false | 跳过 callback collector 启动检查 (Docker) |
| `--remote-coverage` | false | 启用远程 coverage 收集 |
| `--mn-ip` | None | 要阻断的 MN IP (可选) |
| `--coverage-output` | `/tmp/cov-backup` | coverage 数据本地目录 |

## HTTP 测试架构

```
Local 模式:                          Remote 模式:

pytest                               pytest
  │                                    │
  ▼                                    ▼
HttpTestClient                       HttpTestClient (remote)
  │ 启动本地 stub server                │ SSH: 启动 callback_collector
  │                                    │ POST /host/connect (bootstrap)
  ▼                                    ▼
Py3 stub handlers                    真实 kvmagent:7070
  │ sync: 直接返回 JSON                │ sync: 直接返回 JSON
  │ async: POST 回 callback            │ async: POST 到 127.0.0.1:18080
  ▼                                    ▼
断言                                 SSH 轮询 /tmp/callbacks/{uuid}.json
```

## 核心 Fixtures

| Fixture | Scope | 用途 |
|---------|-------|------|
| `remote_coverage` | session | Coverage 注入全生命周期 (autouse，无 `--remote-coverage` 时 no-op) |
| `http_client` | module | HTTP 客户端 — 本地 stub 或远程代理 |
| `host_plugin` | module | Stub HostPlugin: connect/echo/ping/capacity/fact |
| `remote_env` | module | 探测主机资源 (VM, SR-IOV, mdev, USB, PCI) 用于条件 skip |
| `system_mock` | function | Mock shell 命令 (仅 local 模式) |

## 写新测试

### 基本模式

```python
class TestMyPlugin:
    def test_sync_route(self, http_client, host_plugin):
        rsp = http_client.post_sync('/my/route', {'key': 'value'})
        assert rsp.success is True

    def test_async_route(self, http_client, host_plugin):
        rsp = http_client.post_async('/my/async/route', {'key': 'value'})
        assert rsp.success is True
```

### 需要特定资源时用条件 skip

```python
def test_needs_vm(self, http_client, host_plugin, remote_env):
    if http_client.is_remote and not (remote_env or {}).get('vm_uuid'):
        pytest.skip('no running VM on host')
    rsp = http_client.post_async('/vm/operation', {'vmUuid': '...'})
    assert rsp.success is True

def test_needs_sriov(self, http_client, host_plugin, remote_env):
    if http_client.is_remote and not (remote_env or {}).get('sriov_path'):
        pytest.skip('no SR-IOV capable NIC')
    ...

def test_destructive_op(self, http_client, host_plugin):
    if http_client.is_remote:
        pytest.skip('destructive: would reboot real host')
    ...
```

### `remote_env` 可用的资源 key

| Key | 含义 | 探测方式 |
|-----|------|---------|
| `vm_name` | 运行中的 VM 名称 | `virsh list --name` |
| `vm_uuid` | 运行中的 VM UUID | `virsh domuuid` |
| `sriov_path` | SR-IOV 网卡 sysfs 路径 | `/sys/class/net/*/device/sriov_totalvfs` |
| `mdev_device` | mdev 设备 (GPU) | `/sys/class/mdev_bus/` |
| `usb_device` | USB 设备 (非 hub) | `lsusb` |
| `pci_address` | PCI 设备地址 | `lspci -D` |

## 分析 Coverage

```bash
cd /tmp/cov-backup
cp .coverage.kvmagent.final .coverage
python -m coverage report --include='*/kvmagent/plugins/*' --show-missing
```

> 注意：coverage 文件记录的是远程路径 (`/var/lib/zstack/virtualenv/kvm/lib/...`)，
> 需要用 `--include` 或 `.coveragerc` 的 `[paths]` 做路径映射。

## 从 Jenkins 偷 Host

1. `get_running_builds` (Jenkins MCP) 找运行中的 CI
2. `get_nested_mn_ip` 拿嵌套 MN IP
3. SSH 到 MN，从数据库查已连接的 KVM host
4. 用 `--mn-ip` 阻断 MN，或手动 `iptables -I INPUT -s <MN_IP> -j DROP`
5. 对该 host 跑测试
