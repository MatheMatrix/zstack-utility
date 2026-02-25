# pytest 轻量级测试框架 — 完全替代 ztest

## TL;DR

> **Quick Summary**: 为 zstack-utility monorepo 从头构建基于 pytest 的轻量级测试框架，通过 conftest + fixtures + markers + 自定义 plugin 实现本地/SSH/VM 三种执行模式，完全替代沉重的 ztest 体系。
> 
> **Deliverables**:
> - `tests/` 目录结构（unit/integration/system 三层）+ conftest.py 层级
> - pytest plugin 实现三种执行模式（local / ssh / vm-deploy）
> - 标准 markers 体系（unit, integration, system, slow, destructive + 资源子类, 按模块标记）
> - 每个主要模块的示例测试
> - SSH runner（基于 paramiko）和 VM deploy runner
> - pytest 配置（pyproject.toml [tool.pytest]）
> - 清理旧 ztest 残留代码
> - 使用文档 tests/README.md
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 8 → Task 11 → Task 13 → Final

---

## Context

### Original Request
用 pytest 做 zstack-utility 的测试框架，支持本地、SSH、部署到虚拟机三种模式，目的是完全替换原本过于沉重的 ztest。

### Interview Summary
**Key Discussions**:
- 配置管理：用 pytest 原生方式（conftest + fixtures），不再依赖 envconfig.yaml
- test_for / DRY_RUN 机制：完全丢弃，不需要外部编排器集成
- 最大自由度：可以无视现有代码，按最佳实践从头设计
- VM 部署：两种子模式都要——同步代码到已有 VM + 全新部署安装
- CI：暂不考虑，先做本地能跑的框架
- 覆盖范围：第一批为所有主要模块写示例测试

**Research Findings**:
- Monorepo 含 15+ 子包，每个有 setup.py/setup.cfg
- 214+ 现有 TestCase 测试，分散在各包 test/ 目录
- ztest 重的根源：prepare_env.sh 创建 3 个 virtualenv + ansible 部署 + 外部镜像依赖
- 项目已有 paramiko SSH 能力（zstacklib/utils/ssh.py, zstacklib/test/utils/remote.py）
- 已有 Py2 兼容 conftest（zstacklib/conftest.py）mock 了 libvirt, bash, log 等模块

### Metis Review
**Identified Gaps** (addressed):
- Python 版本目标：框架 Py3 only，通过 conftest mock 层保持对 Py2 模块的导入兼容
- 测试迁移策略：不迁移现有 TestCase，pytest 原生兼容运行；新测试用 pytest 风格
- SSH 认证：同时支持密码和 SSH key
- VM 部署范围：不构建 VM provisioner，假设 VM 已存在
- 资源清理：通过 fixture finalizer 保证 SSH/VM 模式下资源清理
- 超时控制：集成 pytest-timeout
- Monorepo 子包导入：根 conftest.py 自动将所有子包目录加入 sys.path，无需 pip install 子包
- Python 版本要求：框架要求 Python >= 3.8（测试环境），生产代码不变

---

## Work Objectives

### Core Objective
构建一个轻量、标准、可扩展的 pytest 测试框架，让开发者可以用 `pytest tests/` 一行命令跑本地单测，用 `pytest --ssh-host=root:pass@ip` 跑远程测试，用 `pytest --vm-deploy --target=ip` 跑 VM 集成测试。

### Concrete Deliverables
- `tests/` 目录结构：`tests/{conftest.py, unit/, integration/, system/}`
- `tests/plugins/` 目录：`ssh_plugin.py`, `vm_deploy_plugin.py`, `markers.py`
- 根目录 `pyproject.toml` 添加 `[tool.pytest.ini_options]` 配置
- 每个主要模块的示例测试（kvmagent, zstacklib, virtualrouter, apibinding, sftpbackupstorage, bm-instance-agent, appliancevm, cephprimarystorage, cephbackupstorage）
- `tests/README.md` 使用文档

### Definition of Done
- [ ] `pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0` 成功安装测试依赖
- [ ] `pytest tests/unit/ -v` 本地跑通所有示例单测
- [ ] `pytest tests/integration/ --ssh-host=root:password@<ip>` 远程跑通示例测试
- [ ] `pytest tests/system/ --vm-deploy --target=<ip>` VM 部署模式跑通
- [ ] `pytest tests/ -m unit --collect-only` 正确过滤 marker
- [ ] `pytest tests/ --collect-only` 能发现所有主要模块的测试
- [ ] `pytest tests/` 默认行为：运行所有非 destructive 的 unit 测试（不需要 SSH/VM 时，integration/system 自动 skip）

### Must Have
- pytest 原生 CLI，不需要自定义 wrapper
- conftest.py 层级化 fixture 继承
- 三种执行模式通过 pytest plugin 实现
- 标准 markers（unit, integration, system, destructive）
- 破坏性测试安全机制：destructive marker + --allow-destructive 开关 + 资源子类（network, storage, disk, vm_lifecycle, os_ops）
- SSH runner 支持密码和 SSH key 认证
- 每个主要模块至少 1 个示例测试
- 文档说明如何使用三种模式
- Python >= 3.8 运行环境（测试框架本身，生产代码不变）
- `pytest tests/` 默认行为清晰：运行 unit 测试 + skip 需要 SSH/VM 的测试 + skip destructive 测试

### Must NOT Have (Guardrails)
- **不做 VM provisioner** — 假设 VM 已存在，不创建/销毁 VM
- **不修改现有测试文件** — 现有 TestCase 测试保持不变
- **不修改生产代码** — 只添加 tests/ 目录和配置
- **不做 CI 配置** — 不生成 GitHub Actions / GitLab CI / Jenkins 文件
- **不做分布式测试执行** — 不集成 pytest-xdist
- **不做全量测试迁移** — 不把 214+ 现有测试重写为 pytest 风格
- **不做 test_for/DRY_RUN 兼容** — 完全丢弃外部编排器接口
- **不过度抽象** — runner 实现直接明了，不搞工厂模式/策略模式
- **不删除 prepare_env.sh / install_kvm.sh** — 它们仍用于 VM 环境准备（非框架职责）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO（从头构建）
- **Automated tests**: YES (Tests-after) — 框架自身功能通过示例测试验证
- **Framework**: pytest

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Framework code**: Use Bash (python -c / pytest) — Import, call functions, compare output
- **CLI/Runner**: Use Bash (pytest) — Run commands, validate exit code + output
- **SSH mode**: Use Bash (pytest --ssh-host=...) — Remote execution, verify results
- **Configuration**: Use Bash (pytest --collect-only) — Verify discovery and marker filtering

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — can all start immediately):
├── Task 1: 项目配置 + 依赖声明 (pyproject.toml) [quick]
├── Task 2: tests/ 目录结构 + conftest.py 层级 [quick]
├── Task 3: Markers 定义 + 注册 [quick]
└── Task 4: Py2 兼容 mock 层（根 conftest） [quick]

Wave 2 (Core Plugins — depends on Wave 1):
├── Task 5: SSH Runner plugin [deep]
├── Task 6: VM Deploy Runner plugin [deep]
├── Task 7: 共享 fixtures 库（mock helpers, temp dirs, config） [unspecified-high]
└── Task 8: pytest CLI 扩展（命令行参数注册） [quick]

Wave 3 (Example Tests — depends on Wave 2):
├── Task 9: kvmagent 示例测试（unit + integration） [unspecified-high]
├── Task 10: zstacklib 示例测试（unit） [quick]
├── Task 11: virtualrouter + apibinding 示例测试 [quick]
├── Task 12: storage 模块示例测试（sftp, ceph-primary, ceph-backup） [quick]
└── Task 13: bm-instance-agent + appliancevm 示例测试 [quick]

Wave 4 (Polish — depends on Wave 3):
├── Task 14: 使用文档 tests/README.md [writing]
├── Task 15: 旧 ztest 残留代码清理标记 [quick]
└── Task 16: 端到端验证（三种模式全流程） [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 5 → Task 8 → Task 9 → Task 16 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 4 (Wave 1 & Wave 3)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2,3,4,5,6,7,8 | 1 |
| 2 | — | 5,6,7,9-13 | 1 |
| 3 | — | 8,9-13 | 1 |
| 4 | — | 7,9-13 | 1 |
| 5 | 1,2 | 8,9,16 | 2 |
| 6 | 1,2,5 | 16 | 2 |
| 7 | 1,2,4 | 9-13 | 2 |
| 8 | 1,3,5,6 | 16 | 2 |
| 9 | 2,3,4,5,7 | 16 | 3 |
| 10 | 2,3,4,7 | 16 | 3 |
| 11 | 2,3,4,7 | 16 | 3 |
| 12 | 2,3,4,7 | 16 | 3 |
| 13 | 2,3,4,7 | 16 | 3 |
| 14 | 8,9 | — | 4 |
| 15 | — | — | 4 |
| 16 | 5,6,8,9-13 | F1-F4 | 4 |
| F1-F4 | ALL | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **4** — T1-T4 → `quick`
- **Wave 2**: **4** — T5 → `deep`, T6 → `deep`, T7 → `unspecified-high`, T8 → `quick`
- **Wave 3**: **5** — T9 → `unspecified-high`, T10-T13 → `quick`
- **Wave 4**: **3** — T14 → `writing`, T15 → `quick`, T16 → `deep`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

### Wave 1 — Foundation (all start immediately)

- [x] 1. 项目配置 + 测试依赖声明

  **What to do**:
  - 在 repo 根目录 `pyproject.toml` 中添加 `[tool.pytest.ini_options]` 配置段：
    - `testpaths = ["tests"]`
    - `python_files = "test_*.py"`
    - `python_classes = "Test*"`
    - `python_functions = "test_*"`
    - `markers` 列表（unit, integration, system, slow, destructive, network, storage, disk, vm_lifecycle, os_ops, kvmagent, zstacklib, virtualrouter, apibinding, sftpbackupstorage, ceph, bm_instance, appliancevm）
    - `addopts = "-ra -q --strict-markers"`
  - **不添加 `[project]` 段** — 这是 monorepo，根目录没有 package；pyproject.toml 仅用于 pytest 工具配置
  - 测试依赖通过直接 pip 安装：`pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0`
  - **不使用 `pip install -e ".[test]"`** — 根目录无 `[project]` 定义，该命令会失败
  - 如果 pyproject.toml 不存在则创建；如果存在则在现有内容后追加

  **Must NOT do**:
  - 不修改已有的 setup.py / setup.cfg 文件
  - 不添加 CI 相关配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 单文件配置修改，逻辑简单

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 2, 3, 4, 5, 6, 7, 8
  - **Blocked By**: None

  **References**:
  - `pyproject.toml`（如存在）— 现有项目配置
  - `zstacklib/setup.py` — 了解现有依赖声明模式
  - `.coveragerc` — 已有覆盖率配置
  - https://docs.pytest.org/en/latest/reference/customize.html — pytest 配置参考

  **Acceptance Criteria**:
  - [ ] pyproject.toml 包含 `[tool.pytest.ini_options]` section
  - [ ] `pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0` → 成功安装，exit code 0
  - [ ] `python -c "import pytest; print(pytest.__version__)"` → 版本 >= 7.0
  - [ ] `python -c "import paramiko; print(paramiko.__version__)"` → 版本 >= 2.0

  **QA Scenarios:**
  ```
  Scenario: 安装测试依赖成功
    Tool: Bash
    Preconditions: clean virtualenv
    Steps:
      1. pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0 2>&1
      2. python -c "import pytest; print(pytest.__version__)"
      3. pytest --version
    Expected Result: 所有命令 exit code 0, pytest 版本 >= 7.0
    Failure Indicators: pip install 失败, import 报 ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-1-install-deps.txt

  Scenario: pyproject.toml 配置正确
    Tool: Bash
    Preconditions: Task 1 完成
    Steps:
      1. grep 'testpaths' pyproject.toml  # 验证配置存在
      2. pytest --co -q 2>&1 | head -1 (应显示 'no tests ran' 或收集信息)
    Expected Result: testpaths=["tests"], pytest 命令可执行
    Failure Indicators: grep 无匹配, pyproject.toml 不存在
    Evidence: .sisyphus/evidence/task-1-config-check.txt
  ```

  **Commit**: YES (group with Wave 1)
  - Message: `feat(tests): add pytest framework foundation`
  - Files: `pyproject.toml`

---

- [x] 2. tests/ 目录结构 + conftest.py 层级

  **What to do**:
  - 创建目录结构：
    ```
    tests/
    ├── __init__.py
    ├── conftest.py              # 根 conftest: 注册 plugins, 共享 fixtures
    ├── plugins/
    │   ├── __init__.py
    │   ├── ssh_plugin.py         # (Wave 2 填充)
    │   ├── vm_deploy_plugin.py   # (Wave 2 填充)
    │   └── markers.py            # (Task 3 填充)
    ├── fixtures/
    │   ├── __init__.py
    │   └── common.py             # (Wave 2 填充)
    ├── unit/
    │   ├── __init__.py
    │   ├── conftest.py           # unit 级 conftest: 自动添加 @pytest.mark.unit
    │   ├── kvmagent/
    │   │   └── __init__.py
    │   ├── zstacklib/
    │   │   └── __init__.py
    │   ├── virtualrouter/
    │   │   └── __init__.py
    │   ├── apibinding/
    │   │   └── __init__.py
    │   ├── sftpbackupstorage/
    │   │   └── __init__.py
    │   ├── ceph/
    │   │   └── __init__.py
    │   ├── bm_instance_agent/
    │   │   └── __init__.py
    │   └── appliancevm/
    │       └── __init__.py
    ├── integration/
    │   ├── __init__.py
    │   ├── conftest.py           # integration 级 conftest: 自动添加 @pytest.mark.integration, SSH fixture
    │   └── kvmagent/
    │       └── __init__.py
    └── system/
        ├── __init__.py
        ├── conftest.py           # system 级 conftest: 自动添加 @pytest.mark.system, VM deploy fixture
        └── kvmagent/
            └── __init__.py
    ```
  - 根 `tests/conftest.py` 内容：
    - 注册自定义 plugins（`pytest_plugins = ['tests.plugins.ssh_plugin', ...]`）
    - 提供基础 fixtures：`tmp_test_dir`, `project_root`
  - `tests/unit/conftest.py`：自动为该目录下所有测试标记 `@pytest.mark.unit`（通过 `pytest_collection_modifyitems` hook）
  - `tests/integration/conftest.py`：同上但标记 `integration`，要求 `--ssh-host` 参数
  - `tests/system/conftest.py`：同上但标记 `system`，要求 `--vm-deploy`

  **Must NOT do**:
  - 不实现 plugin 具体逻辑（留给 Task 5, 6）
  - 不写测试用例（留给 Wave 3）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 创建目录和脚手架文件，无复杂逻辑

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 6, 7, 9-13
  - **Blocked By**: None

  **References**:
  - `kvmagent/kvmagent/test/` — 现有测试目录结构参考（反面教材，不要模仿其扁平结构）
  - `zstacklib/conftest.py` — 现有 conftest 参考
  - https://docs.pytest.org/en/latest/how-to/fixtures.html#conftest-py-sharing-fixtures-across-files — conftest 层级最佳实践

  **Acceptance Criteria**:
  - [ ] `find tests/ -name '*.py' | wc -l` >= 20（所有 __init__.py + conftest.py）
  - [ ] `pytest tests/ --collect-only` 不报错（即使 0 tests collected）
  - [ ] `python -c "from tests.conftest import *"` 不报 import error

  **QA Scenarios:**
  ```
  Scenario: 目录结构完整
    Tool: Bash
    Preconditions: Task 2 完成
    Steps:
      1. ls tests/unit/conftest.py tests/integration/conftest.py tests/system/conftest.py
      2. ls tests/plugins/__init__.py tests/fixtures/__init__.py
      3. ls tests/unit/kvmagent/__init__.py tests/unit/zstacklib/__init__.py
    Expected Result: 所有文件存在, exit code 0
    Failure Indicators: ls 报 No such file or directory
    Evidence: .sisyphus/evidence/task-2-dir-structure.txt

  Scenario: pytest 能从 tests/ 根目录收集（即使 0 测试）
    Tool: Bash
    Preconditions: Task 1 + Task 2 完成
    Steps:
      1. pytest tests/ --collect-only 2>&1
    Expected Result: exit code 0 或 5 (no tests collected), 不报 conftest 错误
    Failure Indicators: ImportError, SyntaxError, conftest 加载失败
    Evidence: .sisyphus/evidence/task-2-collect.txt
  ```

  **Commit**: YES (group with Wave 1)
  - Message: `feat(tests): add pytest framework foundation`
  - Files: `tests/**/__init__.py`, `tests/**/conftest.py`

---

- [x] 3. Markers 定义 + 注册

  **What to do**:
  - 创建 `tests/plugins/markers.py`：
    - 定义 pytest plugin hook `pytest_configure(config)` 注册所有 markers
    - 标准 markers：`unit`, `integration`, `system`, `slow`
    - 破坏性 markers：`destructive`（父级）+ 资源子类 `network`（含防火墙）, `storage`, `disk`, `vm_lifecycle`, `os_ops`（zstacklib 提供的系统操作）
    - 模块 markers：`kvmagent`, `zstacklib`, `virtualrouter`, `apibinding`, `sftpbackupstorage`, `ceph`, `bm_instance`, `appliancevm`
    - 每个 marker 有清晰的 description 字符串
  - 在 `tests/conftest.py` 的 `pytest_plugins` 列表中注册此 plugin
  - 在 `tests/plugins/markers.py` 中实现 `pytest_collection_modifyitems` hook：
    - 本机模式（无 `--ssh-host` 且无 `--vm-deploy`）时：
      - 所有标记了 `destructive` 或其子类 marker 的测试自动 **skip**，原因提示“破坏性测试不允许在本机跑，使用 --allow-destructive 或 --ssh-host / --vm-deploy”
      - 除非传入 `--allow-destructive` 参数
    - SSH / VM 模式时：destructive 测试正常运行（远程环境不怕損坏）
  - 注册 `--allow-destructive` CLI 选项（在此 plugin 的 `pytest_addoption` 中）

  **Must NOT do**:
  - 不实现自动按目录标记逻辑（那是各级 conftest 的职责）
  - destructive 子类 marker 不需要继承关系 — 通过 `pytest_collection_modifyitems` 统一检查所有资源类 marker
  - **Hook 优先级说明**: `markers.py` 中的 `pytest_collection_modifyitems` 处理 destructive skip 逻辑；各级 conftest（unit/integration/system）中的同名 hook 只做自动标记。pytest 会按 conftest 层级从内到外执行这些 hooks，plugin 中的最后执行。在 `markers.py` 的 hook 中使用 `@pytest.hookimpl(trylast=True)` 装饰器确保它在自动标记之后运行。

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 单文件，简单的 marker 注册

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 8, 9-13
  - **Blocked By**: None

  **References**:
  - https://docs.pytest.org/en/latest/how-to/mark.html — marker 注册机制
  - 已有 marker 用法：项目中发现 `@pytest.mark.skip`, `@pytest.mark.run(order=N)`, `@pytest.mark.flaky(reruns=3)`

  **Acceptance Criteria**:
  - [ ] `pytest --markers | grep -E 'unit|integration|system|destructive|network|storage|kvmagent'` 显示已注册的 markers
  - [ ] `pytest --strict-markers -m 'destructive' tests/ --collect-only` 不报 'Unknown marker' 错误
  - [ ] `pytest --help | grep allow-destructive` 显示 `--allow-destructive` 选项

  **QA Scenarios:**
  ```
  Scenario: 所有 markers 已注册
    Tool: Bash
    Preconditions: Task 1 + Task 3 完成
    Steps:
      1. pytest --markers 2>&1 | grep '@pytest.mark.unit'
      2. pytest --markers 2>&1 | grep '@pytest.mark.integration'
      3. pytest --markers 2>&1 | grep '@pytest.mark.system'
      4. pytest --markers 2>&1 | grep '@pytest.mark.destructive'
      5. pytest --markers 2>&1 | grep '@pytest.mark.network'
      6. pytest --markers 2>&1 | grep '@pytest.mark.storage'
      7. pytest --markers 2>&1 | grep '@pytest.mark.kvmagent'
    Expected Result: 每行输出包含 marker 名称和 description
    Failure Indicators: grep 无匹配, exit code 1
    Evidence: .sisyphus/evidence/task-3-markers.txt
  ```

  **Commit**: YES (group with Wave 1)
  - Message: `feat(tests): add pytest framework foundation`
  - Files: `tests/plugins/markers.py`

---

- [x] 4. Py2 兼容 mock 层

  **What to do**:
  - 在 `tests/conftest.py` 中实现 **sys.path 自动发现机制**（CRITICAL — monorepo 无根级 package）：
    - 找到 repo 根目录（`tests/` 的父目录）
    - 扫描根目录下所有包含 `setup.py` 或 `setup.cfg` 的一级子目录
    - 将这些子目录加入 `sys.path`（如果尚未存在）
    - 这使得 `import kvmagent`, `import zstacklib` 等无需 `pip install` 即可工作
    - 实现为模块级代码（非 fixture），在 conftest 加载时立即执行
  - 然后添加 Py2 兼容 mock（从 `zstacklib/conftest.py` 中提炼并改进）：
    - mock `zstacklib.utils.log` — 提供 `get_logger` 返回 MagicMock
    - mock `zstacklib.utils.bash` — 提供 `bash_roe`, `bash_ro`, `bash_r` dummy 实现
    - mock 系统级模块：`libvirt`, `zstacklib.utils.shell`, `zstacklib.utils.linux`, `zstacklib.utils.daemon` 等
  - 与现有 `zstacklib/conftest.py` 的区别：
    - 用 fixture 方式提供而非模块级 side-effect（mock 注入部分）
    - 可通过 fixture scope 控制 mock 生命周期
    - 添加 `autouse=True` 对 unit 测试自动应用
  - 提供 `@pytest.fixture` 级别的 `mock_zstacklib_imports` fixture
  - **sys.path 代码示例**（供实现参考）：
    ```python
    # tests/conftest.py — top of file, before any imports from sub-packages
    import sys
    from pathlib import Path
    
    _repo_root = Path(__file__).resolve().parent.parent
    for child in sorted(_repo_root.iterdir()):
        if child.is_dir() and ((child / 'setup.py').exists() or (child / 'setup.cfg').exists()):
            child_str = str(child)
            if child_str not in sys.path:
                sys.path.insert(0, child_str)
    ```

  **Must NOT do**:
  - 不修改 `zstacklib/conftest.py` 原文件
  - 不 mock 太多模块 — 只 mock 必须的 Py2-only 模块

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 从已有 conftest 提炼 mock，逻辑清晰

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Tasks 7, 9-13
  - **Blocked By**: None

  **References**:
  - `zstacklib/conftest.py:1-47` — 现有 Py2 mock 实现，需要提炼的内容
  - `kvmagent/kvmagent/test/utils/pytest_utils.py:33-45` — PytestExtension.setup_modules_mock() 参考

  **Acceptance Criteria**:
  - [ ] `pytest tests/ --collect-only` 不因 Py2 模块导入失败
  - [ ] `python -c "import tests.conftest"` 不报错
  - [ ] sys.path 包含所有子包目录：`python -c "import sys; sys.path.insert(0,'.'); import tests.conftest; assert any('kvmagent' in p for p in sys.path)"`

  **QA Scenarios:**
  ```
  Scenario: Py2 mock 层工作正常
    Tool: Bash
    Preconditions: Task 1 + Task 2 + Task 4 完成
    Steps:
      1. python -c "import sys; sys.path.insert(0,'.'); import tests.conftest; print('OK')"
      2. pytest tests/ --collect-only 2>&1 | tail -5
    Expected Result: 无 ImportError, mock 模块可导入
    Failure Indicators: ImportError: No module named 'libvirt'
    Evidence: .sisyphus/evidence/task-4-py2-mock.txt
  ```

  **Commit**: YES (group with Wave 1)
  - Message: `feat(tests): add pytest framework foundation`
  - Files: `tests/conftest.py`（更新）
---

### Wave 2 — Core Plugins (depends on Wave 1)

- [ ] 5. SSH Runner Plugin

  **What to do**:
  - 创建 `tests/plugins/ssh_plugin.py`，实现 pytest plugin：
    - `pytest_addoption(parser)`: 注册 `--ssh-host`, `--ssh-password`, `--ssh-key` 选项
    - `--ssh-host` 格式：`root:password@ip[:port]` 或 `root@ip[:port]`（解析 user、password、host、port）
    - `--ssh-key` 接受 SSH private key 文件路径
    - `--ssh-password` 作为 `--ssh-host` 中密码的备选方式
  - 提供辅助函数 `parse_ssh_host(host_string)` → `(user, password, host, port)` 元组
  - 提供 `@pytest.fixture(scope='session')` 的 `ssh_client` fixture：
    - 返回已连接的 `paramiko.SSHClient` 实例
    - 支持密码认证和 SSH key 认证
    - fixture finalizer 中调用 `client.close()`
    - 如果 `--ssh-host` 未提供，返回 `None`（integration tests 的 conftest 会 skip）
  - 提供 `@pytest.fixture(scope='session')` 的 `ssh_run` fixture：
    - 接受命令字符串，通过 `ssh_client` 执行，返回 `(exit_code, stdout, stderr)` 元组
    - 带 timeout 支持（默认 60s）
  - 提供 `@pytest.fixture(scope='session')` 的 `scp_file` fixture：
    - 封装 `paramiko.SFTPClient` 的 put/get 操作
    - `scp_put(local_path, remote_path)`, `scp_get(remote_path, local_path)`
  - 在 `tests/integration/conftest.py` 中：
    - 自动 skip 所有 integration 测试（如果 `--ssh-host` 未提供）
    - `pytestmark = [pytest.mark.integration]` 自动标记

  **Must NOT do**:
  - 不使用 `subprocess` 调用系统 `ssh` 命令 — 纯 paramiko
  - 不实现连接池或连接复用逻辑 — 保持简单
  - 不 mock SSH 连接 — 这是真实 runner，不需要 mock

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 需要正确处理 paramiko SSH 认证、会话管理、错误处理、fixture 生命周期

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8)
  - **Blocks**: Tasks 8, 9, 16
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `zstacklib/zstacklib/utils/ssh.py` — 现有 paramiko SSH 封装（Sftp 类、execute 函数），参考其认证逻辑和 SFTP 用法
  - `zstacklib/zstacklib/test/utils/remote.py:SetupRemoteMachine` — 现有 SSH 测试工具，参考其 ssh_run() 实现
  - `zstackctl/zstackctl/ctl.py` — host 格式解析（`root:password@host` pattern），参考解析逻辑
  - https://docs.paramiko.org/en/latest/api/client.html — paramiko SSHClient API

  **Acceptance Criteria**:
  - [ ] `pytest --help | grep ssh-host` 显示 `--ssh-host` 选项
  - [ ] `pytest --help | grep ssh-password` 显示 `--ssh-password` 选项
  - [ ] `pytest --help | grep ssh-key` 显示 `--ssh-key` 选项
  - [ ] `pytest tests/integration/ --collect-only` 无 `--ssh-host` 时 → 所有 integration 测试被 skip
  - [ ] `python -c "from tests.plugins.ssh_plugin import *"` 不报 import error

  **QA Scenarios:**
  ```
  Scenario: SSH CLI 选项注册成功
    Tool: Bash
    Preconditions: Task 1 + Task 2 + Task 5 完成
    Steps:
      1. pytest --help 2>&1 | grep -A1 'ssh-host'
      2. pytest --help 2>&1 | grep -A1 'ssh-password'
      3. pytest --help 2>&1 | grep -A1 'ssh-key'
    Expected Result: 三个选项均出现在帮助输出中，带描述信息
    Failure Indicators: grep 无匹配, exit code 1
    Evidence: .sisyphus/evidence/task-5-ssh-cli.txt

  Scenario: 无 --ssh-host 时 integration 测试自动 skip
    Tool: Bash
    Preconditions: Task 5 + 至少一个 integration 测试存在
    Steps:
      1. pytest tests/integration/ -v 2>&1 (不传 --ssh-host)
    Expected Result: 所有测试显示 SKIPPED，原因包含 'ssh-host' 字样
    Failure Indicators: 测试 FAILED 或 ERROR
    Evidence: .sisyphus/evidence/task-5-ssh-skip.txt

  Scenario: SSH host 格式解析正确
    Tool: Bash
    Preconditions: Task 5 完成
    Steps:
      1. python -c "from tests.plugins.ssh_plugin import parse_ssh_host; print(parse_ssh_host('root:pass123@192.168.1.100'))"
      2. python -c "from tests.plugins.ssh_plugin import parse_ssh_host; print(parse_ssh_host('root@192.168.1.100:2222'))"
      3. python -c "from tests.plugins.ssh_plugin import parse_ssh_host; print(parse_ssh_host('admin:pass@10.0.0.1:22'))"
    Expected Result: 正确解析出 (user, password, host, port) 元组，password 缺失时为 None，port 缺失时为 22
    Failure Indicators: ValueError, 解析结果不正确
    Evidence: .sisyphus/evidence/task-5-ssh-parse.txt
  ```

  **Commit**: YES (group with Wave 2)
  - Message: `feat(tests): add SSH and VM deploy runner plugins + shared fixtures`
  - Files: `tests/plugins/ssh_plugin.py`, `tests/integration/conftest.py`

---

- [ ] 6. VM Deploy Runner Plugin

  **What to do**:
  - 创建 `tests/plugins/vm_deploy_plugin.py`，实现 pytest plugin：
    - `pytest_addoption(parser)`: 注册 `--vm-deploy` (bool flag) 和 `--target` (IP[:port]) 选项
    - `--vm-deploy` 启用 VM 部署模式
    - `--target` 指定目标 VM 地址
  - 实现两种 VM 部署子模式（通过 fixture 暴露）：
    - **Sync 模式** (`vm_sync` fixture)：
      - 通过 SSH + SCP 将本地代码同步到 VM
      - 同步策略：将 monorepo 中指定包目录同步到 VM 的 `/tmp/zstack-test/`
      - 在 VM 上执行 `pip install -e .` 安装
    - **Full Deploy 模式** (`vm_deploy` fixture)：
      - 调用已有的 `install_kvm.sh` 脚本（通过 SSH 在 VM 上执行）
      - 或直接 SCP 包文件 + pip install
  - 提供 `@pytest.fixture(scope='session')` 的 `vm_connection` fixture：
    - 内部复用 `ssh_client` fixture（依赖 Task 5 的 SSH plugin）
    - 如果 `--vm-deploy` 未提供，fixture 返回 `None`
  - 提供 `vm_run` fixture：在 VM 上执行命令并返回结果
  - 在 `tests/system/conftest.py` 中：
    - 自动 skip 所有 system 测试（如果 `--vm-deploy` 未提供）
    - `pytestmark = [pytest.mark.system]` 自动标记

  **Must NOT do**:
  - 不构建 VM provisioner（不创建/销毁 VM）
  - 不使用 ansible — 直接 SSH + SCP
  - 不做完整的包构建流程 — 只同步源码或已构建的包

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 需要处理 SSH 上的文件同步、远程安装、fixture 依赖链、错误处理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 1, 2, 5（依赖 SSH plugin 的 ssh_client fixture）

  **References**:
  - `tests/plugins/ssh_plugin.py` (Task 5) — 复用 ssh_client / scp_file fixture
  - `kvmagent/kvmagent/test/unittest_tools/install_kvm.sh` — 现有 VM 部署脚本，理解部署步骤和依赖
  - `kvmagent/kvmagent/test/unittest_tools/prepare_env.sh` — 环境准备脚本，了解 virtualenv 创建和包安装流程
  - `zstacklib/zstacklib/test/utils/remote.py:SetupRemoteMachine.put_file()` — SCP 文件上传模式

  **Acceptance Criteria**:
  - [ ] `pytest --help | grep vm-deploy` 显示 `--vm-deploy` 选项
  - [ ] `pytest --help | grep target` 显示 `--target` 选项
  - [ ] `pytest tests/system/ --collect-only` 无 `--vm-deploy` 时 → 所有 system 测试被 skip
  - [ ] `python -c "from tests.plugins.vm_deploy_plugin import *"` 不报 import error

  **QA Scenarios:**
  ```
  Scenario: VM Deploy CLI 选项注册成功
    Tool: Bash
    Preconditions: Task 1 + Task 2 + Task 6 完成
    Steps:
      1. pytest --help 2>&1 | grep -A1 'vm-deploy'
      2. pytest --help 2>&1 | grep -A1 '\-\-target'
    Expected Result: 两个选项均出现在帮助输出中，带描述信息
    Failure Indicators: grep 无匹配
    Evidence: .sisyphus/evidence/task-6-vm-cli.txt

  Scenario: 无 --vm-deploy 时 system 测试自动 skip
    Tool: Bash
    Preconditions: Task 6 + 至少一个 system 测试存在
    Steps:
      1. pytest tests/system/ -v 2>&1 (不传 --vm-deploy)
    Expected Result: 所有测试显示 SKIPPED，原因包含 'vm-deploy' 字样
    Failure Indicators: 测试 FAILED 或 ERROR
    Evidence: .sisyphus/evidence/task-6-vm-skip.txt
  ```

  **Commit**: YES (group with Wave 2)
  - Message: `feat(tests): add SSH and VM deploy runner plugins + shared fixtures`
  - Files: `tests/plugins/vm_deploy_plugin.py`, `tests/system/conftest.py`

---

- [ ] 7. 共享 Fixtures 库

  **What to do**:
  - 创建 `tests/fixtures/common.py`，提供跨模块复用的 fixtures：
    - `project_root` (scope=session): 返回 monorepo 根目录 Path
    - `tmp_test_dir` (scope=function): 为每个测试创建临时目录，yield 后自动清理
    - `sample_vm_xml` (scope=session): 提供标准 libvirt VM XML 模板字符串
    - `fake_zstack_config` (scope=function): 返回模拟的 ZStack 配置 dict
    - `isolated_env` (scope=function): 设置/还原环境变量的 context manager fixture
    - **不包含 `mock_http_server`** — 当前无示例测试使用它，YAGNI 原则；需要时再添加
  - 在 `tests/conftest.py` 中 import 这些 fixtures 使其全局可用

  **Must NOT do**:
  - 不做 pytest-httpx 或 responses 等第三方 mock 库集成 — 用标准库
  - 不过度抽象 — 每个 fixture 独立，不互相依赖

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 需要设计合理的 fixture API，考虑 scope 和 cleanup

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8)
  - **Blocks**: Tasks 9-13
  - **Blocked By**: Tasks 1, 2, 4

  **References**:
  - `zstacklib/conftest.py` — 现有 mock 模式，提炼出通用部分
  - `kvmagent/kvmagent/test/utils/pytest_utils.py:PytestExtension` — 现有 setup helpers 参考
  - `kvmagent/kvmagent/test/` — 测试中常用的 mock 模式（libvirt XML, agent config 等）
  - https://docs.pytest.org/en/latest/how-to/fixtures.html — fixture scope 和 teardown 最佳实践

  **Acceptance Criteria**:
  - [ ] `python -c "from tests.fixtures.common import *"` 不报 import error
  - [ ] 每个 fixture 有 docstring 说明用途和 scope
  - [ ] `tmp_test_dir` fixture 在测试结束后自动清理临时文件

  **QA Scenarios:**
  ```
  Scenario: 共享 fixtures 可导入且类型正确
    Tool: Bash
    Preconditions: Task 7 完成
    Steps:
      1. python -c "from tests.fixtures.common import project_root, tmp_test_dir, sample_vm_xml; print('OK')"
      2. pytest --fixtures tests/ 2>&1 | grep 'project_root'
      3. pytest --fixtures tests/ 2>&1 | grep 'tmp_test_dir'
    Expected Result: 导入成功, pytest --fixtures 列出所有自定义 fixtures
    Failure Indicators: ImportError, fixture 未注册
    Evidence: .sisyphus/evidence/task-7-fixtures.txt
  ```

  **Commit**: YES (group with Wave 2)
  - Message: `feat(tests): add SSH and VM deploy runner plugins + shared fixtures`
  - Files: `tests/fixtures/common.py`, `tests/conftest.py`

---

- [ ] 8. pytest CLI 扩展（命令行参数统一注册）

  **What to do**:
  - 确保 `tests/conftest.py` 的 `pytest_plugins` 列表正确注册所有 plugins：
    - `tests.plugins.markers`
    - `tests.plugins.ssh_plugin`
    - `tests.plugins.vm_deploy_plugin`
  - 验证所有 CLI 选项在 `pytest --help` 中正确显示
  - 添加互斥校验逻辑（在根 conftest 的 `pytest_configure` hook 中）：
    - `--ssh-host` 和 `--vm-deploy` 不应同时使用
    - `--vm-deploy` 必须配合 `--target`
    - `--ssh-key` 和 `--ssh-password` 不应同时使用
  - 添加 `pytest_report_header(config)` hook：在测试输出开头显示当前运行模式：
    - `Mode: local (unit tests)`
    - `Mode: SSH → root@192.168.1.100:22`
    - `Mode: VM Deploy → 192.168.1.100`

  **Must NOT do**:
  - 不添加自定义 pytest wrapper 脚本 — 直接用 `pytest` 命令
  - 不重复注册已在各 plugin 中注册的选项

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 整合已有 plugin 注册，添加轻量校验逻辑

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 Task 5, 6 的 plugin 实现）
  - **Parallel Group**: Wave 2 (但在 Task 5, 6 完成后)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 1, 3, 5, 6

  **References**:
  - `tests/plugins/ssh_plugin.py` (Task 5) — SSH CLI 选项
  - `tests/plugins/vm_deploy_plugin.py` (Task 6) — VM CLI 选项
  - `tests/plugins/markers.py` (Task 3) — markers 注册
  - https://docs.pytest.org/en/latest/reference/reference.html#hook-reference — pytest hook 参考

  **Acceptance Criteria**:
  - [ ] `pytest --help` 同时显示 `--ssh-host`, `--ssh-password`, `--ssh-key`, `--vm-deploy`, `--target`
  - [ ] `pytest tests/ --ssh-host=x --vm-deploy` → 报错提示互斥
  - [ ] `pytest tests/ --vm-deploy` (无 --target) → 报错提示缺少 target
  - [ ] `pytest tests/unit/ -v` 输出开头显示 `Mode: local`

  **QA Scenarios:**
  ```
  Scenario: 互斥参数校验
    Tool: Bash
    Preconditions: Task 8 完成
    Steps:
      1. pytest tests/ --ssh-host=root:pass@1.2.3.4 --vm-deploy --target=1.2.3.4 2>&1
      2. pytest tests/ --vm-deploy 2>&1 (无 --target)
    Expected Result: Step 1 报错含 'mutually exclusive' 或类似信息; Step 2 报错含 '--target required'
    Failure Indicators: 命令成功执行而非报错
    Evidence: .sisyphus/evidence/task-8-mutex.txt

  Scenario: 运行模式 header 显示
    Tool: Bash
    Preconditions: Task 8 完成
    Steps:
      1. pytest tests/unit/ --collect-only 2>&1 | head -5
    Expected Result: 输出包含 'Mode: local' 字样
    Failure Indicators: 无 Mode 显示
    Evidence: .sisyphus/evidence/task-8-header.txt
  ```

  **Commit**: YES (group with Wave 2)
  - Message: `feat(tests): add SSH and VM deploy runner plugins + shared fixtures`
  - Files: `tests/conftest.py`

---

### Wave 3 — Example Tests (depends on Wave 2)

- [ ] 9. kvmagent 示例测试（unit + integration）

  **What to do**:
  - 创建 `tests/unit/kvmagent/test_vm_plugin.py`：
    - 测试 kvmagent 的 VM 操作相关函数（mock libvirt）
    - 至少 3 个测试：创建 VM XML、解析 VM 状态、转换磁盘格式
    - 使用 `sample_vm_xml` fixture 和 `mock_zstacklib_imports` fixture
    - 标记: `@pytest.mark.kvmagent`
  - 创建 `tests/unit/kvmagent/test_network_plugin.py`：
    - 测试网络相关工具函数（mock 系统调用）
    - 至少 2 个测试：bridge 配置解析、IP 地址验证
    - 标记: `@pytest.mark.kvmagent`，如涉及真实网卡操作加 `@pytest.mark.network`
  - 创建 `tests/integration/kvmagent/test_remote_agent.py`：
    - 通过 SSH 连接到远程机器，验证 kvmagent 服务状态
    - 使用 `ssh_run` fixture
    - 至少 1 个测试：检查 kvmagent 进程是否运行
    - 标记: `@pytest.mark.kvmagent`, `@pytest.mark.integration`

  **Must NOT do**:
  - 不修改 kvmagent 生产代码
  - unit 测试不依赖真实 libvirt/qemu

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 需要理解 kvmagent 模块结构，正确 mock 依赖

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 13)
  - **Blocks**: Tasks 14, 16
  - **Blocked By**: Tasks 2, 3, 4, 5, 7

  **References**:
  - `kvmagent/kvmagent/plugins/vm_plugin.py` — VM 操作主要逻辑，找可测试的纯函数
  - `kvmagent/kvmagent/plugins/network_plugin.py` — 网络插件，找工具函数
  - `kvmagent/kvmagent/test/` — 现有测试参考，了解测试模式和 mock 策略
  - `tests/fixtures/common.py` (Task 7) — 复用 sample_vm_xml, mock_http_server 等 fixture

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/kvmagent/ -v` → 至少 5 个测试 PASSED
  - [ ] `pytest tests/unit/kvmagent/ -m kvmagent --collect-only` → 正确收集
  - [ ] `pytest tests/integration/kvmagent/ --collect-only` (无 --ssh-host) → SKIPPED

  **QA Scenarios:**
  ```
  Scenario: kvmagent 单元测试本地跑通
    Tool: Bash
    Preconditions: Wave 1 + Wave 2 完成
    Steps:
      1. pytest tests/unit/kvmagent/ -v 2>&1
      2. pytest tests/unit/kvmagent/ -v 2>&1 | grep -c 'PASSED'
    Expected Result: 所有测试 PASSED，PASSED 数量 >= 5
    Failure Indicators: FAILED, ERROR, ImportError
    Evidence: .sisyphus/evidence/task-9-kvmagent-unit.txt

  Scenario: kvmagent 网络测试标记为 destructive 的本机自动 skip
    Tool: Bash
    Preconditions: 存在标记了 @pytest.mark.network 的测试
    Steps:
      1. pytest tests/unit/kvmagent/ -m network -v 2>&1
    Expected Result: 包含 network marker 的测试显示 SKIPPED，原因含 'destructive'
    Failure Indicators: 测试实际执行而非 skip
    Evidence: .sisyphus/evidence/task-9-kvmagent-destructive-skip.txt
  ```

  **Commit**: YES (group with Wave 3)
  - Message: `feat(tests): add example tests for all major modules`
  - Files: `tests/unit/kvmagent/test_vm_plugin.py`, `tests/unit/kvmagent/test_network_plugin.py`, `tests/integration/kvmagent/test_remote_agent.py`

---

- [ ] 10. zstacklib 示例测试（unit）

  **What to do**:
  - 创建 `tests/unit/zstacklib/test_linux_utils.py`：
    - 测试 zstacklib 的 Linux 工具函数（mock 系统调用）
    - 至少 3 个测试：磁盘大小解析、进程检查、网卡信息解析
    - 测试纯工具函数，mock 外部系统调用
    - 标记: `@pytest.mark.zstacklib`
  - 创建 `tests/unit/zstacklib/test_bash_utils.py`：
    - 测试 bash 工具函数（命令拼接、输出解析）
    - 至少 2 个测试
    - 标记: `@pytest.mark.zstacklib`，如涉及真实 shell 执行加 `@pytest.mark.os_ops`

  **Must NOT do**:
  - 不修改 zstacklib 生产代码
  - 不测试需要真实系统资源的函数（那些标记 destructive）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: zstacklib 工具函数简单，mock 直接

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 11, 12, 13)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 2, 3, 4, 7

  **References**:
  - `zstacklib/zstacklib/utils/linux.py` — Linux 工具函数，找可单测的纯函数（如 get_disk_capacity, get_nic_info）
  - `zstacklib/zstacklib/utils/bash.py` — bash 工具函数
  - `zstacklib/zstacklib/test/` — 现有测试参考

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/zstacklib/ -v` → 至少 5 个测试 PASSED
  - [ ] `pytest tests/unit/zstacklib/ -m zstacklib --collect-only` → 正确收集

  **QA Scenarios:**
  ```
  Scenario: zstacklib 单元测试本地跑通
    Tool: Bash
    Preconditions: Wave 1 + Wave 2 完成
    Steps:
      1. pytest tests/unit/zstacklib/ -v 2>&1
      2. pytest tests/unit/zstacklib/ -v 2>&1 | grep -c 'PASSED'
    Expected Result: 所有测试 PASSED，PASSED 数量 >= 5
    Failure Indicators: FAILED, ERROR, ImportError
    Evidence: .sisyphus/evidence/task-10-zstacklib-unit.txt
  ```

  **Commit**: YES (group with Wave 3)
  - Message: `feat(tests): add example tests for all major modules`
  - Files: `tests/unit/zstacklib/test_linux_utils.py`, `tests/unit/zstacklib/test_bash_utils.py`

---

- [ ] 11. virtualrouter + apibinding 示例测试

  **What to do**:
  - 创建 `tests/unit/virtualrouter/test_vr_commands.py`：
    - 测试 virtualrouter 的命令处理函数
    - 至少 2 个测试：DHCP 配置生成、路由规则解析
    - 标记: `@pytest.mark.virtualrouter`
  - 创建 `tests/unit/apibinding/test_api_models.py`：
    - 测试 apibinding 的模型序列化/反序列化
    - 至少 2 个测试：API 请求构建、响应解析
    - 标记: `@pytest.mark.apibinding`

  **Must NOT do**:
  - 不修改生产代码
  - 不连接真实 API 端点

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 简单的函数级单测

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 12, 13)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 2, 3, 4, 7

  **References**:
  - `virtualrouter/virtualrouter/` — virtualrouter 主要逻辑，找可测试的纯函数
  - `apibinding/apibinding/` — API binding 模型和序列化逻辑
  - `virtualrouter/virtualrouter/test/` — 现有测试参考

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/virtualrouter/ tests/unit/apibinding/ -v` → 至少 4 个测试 PASSED
  - [ ] marker 过滤: `pytest tests/ -m virtualrouter --collect-only` → 只收集 virtualrouter 测试

  **QA Scenarios:**
  ```
  Scenario: virtualrouter + apibinding 单元测试本地跑通
    Tool: Bash
    Preconditions: Wave 1 + Wave 2 完成
    Steps:
      1. pytest tests/unit/virtualrouter/ tests/unit/apibinding/ -v 2>&1
      2. pytest tests/unit/virtualrouter/ tests/unit/apibinding/ -v 2>&1 | grep -c 'PASSED'
    Expected Result: 所有测试 PASSED，PASSED 数量 >= 4
    Failure Indicators: FAILED, ERROR
    Evidence: .sisyphus/evidence/task-11-vr-apibinding-unit.txt
  ```

  **Commit**: YES (group with Wave 3)
  - Message: `feat(tests): add example tests for all major modules`
  - Files: `tests/unit/virtualrouter/test_vr_commands.py`, `tests/unit/apibinding/test_api_models.py`

---

- [ ] 12. storage 模块示例测试（sftp, ceph-primary, ceph-backup）

  **What to do**:
  - 创建 `tests/unit/sftpbackupstorage/test_sftp_operations.py`：
    - 测试 SFTP 备份存储的文件操作逻辑（mock SFTP 连接）
    - 至少 2 个测试：文件上传路径生成、备份清理逻辑
    - 标记: `@pytest.mark.sftpbackupstorage`, `@pytest.mark.storage`
  - 创建 `tests/unit/ceph/test_ceph_operations.py`：
    - 测试 Ceph 存储的配置解析和命令构建逻辑（mock ceph CLI）
    - 涵盖 cephprimarystorage 和 cephbackupstorage 的共享逻辑
    - 至少 3 个测试：RBD 命令拼接、pool 配置解析、快照名称生成
    - 标记: `@pytest.mark.ceph`, `@pytest.mark.storage`

  **Must NOT do**:
  - 不连接真实 Ceph 集群或 SFTP 服务器
  - 不测试真实 IO 操作（那些标记 `@pytest.mark.storage` + `@pytest.mark.destructive`）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 存储模块工具函数单测，mock 直接

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 11, 13)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 2, 3, 4, 7

  **References**:
  - `sftpbackupstorage/sftpbackupstorage/` — SFTP 备份存储主要逻辑
  - `cephprimarystorage/cephprimarystorage/` — Ceph primary storage 插件
  - `cephbackupstorage/cephbackupstorage/` — Ceph backup storage 插件
  - 各存储模块现有 test/ 目录 — 了解现有测试模式

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/sftpbackupstorage/ tests/unit/ceph/ -v` → 至少 5 个测试 PASSED
  - [ ] marker 过滤: `pytest tests/ -m storage --collect-only` → 只收集存储相关测试

  **QA Scenarios:**
  ```
  Scenario: 存储模块单元测试本地跑通
    Tool: Bash
    Preconditions: Wave 1 + Wave 2 完成
    Steps:
      1. pytest tests/unit/sftpbackupstorage/ tests/unit/ceph/ -v 2>&1
      2. pytest tests/unit/sftpbackupstorage/ tests/unit/ceph/ -v 2>&1 | grep -c 'PASSED'
    Expected Result: 所有测试 PASSED，PASSED 数量 >= 5
    Failure Indicators: FAILED, ERROR
    Evidence: .sisyphus/evidence/task-12-storage-unit.txt
  ```

  **Commit**: YES (group with Wave 3)
  - Message: `feat(tests): add example tests for all major modules`
  - Files: `tests/unit/sftpbackupstorage/test_sftp_operations.py`, `tests/unit/ceph/test_ceph_operations.py`

---

- [ ] 13. bm-instance-agent + appliancevm 示例测试

  **What to do**:
  - 创建 `tests/unit/bm_instance_agent/test_bm_commands.py`：
    - 测试裸金属实例 agent 的命令处理函数
    - 至少 2 个测试：PXE 配置生成、硬件信息解析
    - 标记: `@pytest.mark.bm_instance`
  - 创建 `tests/unit/appliancevm/test_appliancevm_agent.py`：
    - 测试 appliancevm agent 的初始化和配置逻辑
    - 至少 2 个测试：配置加载、服务注册
    - 标记: `@pytest.mark.appliancevm`

  **Must NOT do**:
  - 不修改生产代码
  - 不连接真实硬件或 IPMI

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 简单工具函数单测

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 11, 12)
  - **Blocks**: Tasks 16
  - **Blocked By**: Tasks 2, 3, 4, 7

  **References**:
  - `bm-instance-agent/bm_instance_agent/` — 裸金属 agent 主要逻辑（注意：目录名用下划线 `bm_instance_agent` 而非连字符）
  - `appliancevm/appliancevm/` — appliancevm agent 逻辑
  - `baremetalpxeserver/` — PXE 服务器相关逻辑（如 bm-instance-agent 涉及 PXE）

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/bm_instance_agent/ tests/unit/appliancevm/ -v` → 至少 4 个测试 PASSED
  - [ ] marker 过滤正常: `pytest tests/ -m bm_instance --collect-only` → 只收集 bm 测试

  **QA Scenarios:**
  ```
  Scenario: bm-instance-agent + appliancevm 单元测试本地跑通
    Tool: Bash
    Preconditions: Wave 1 + Wave 2 完成
    Steps:
      1. pytest tests/unit/bm_instance_agent/ tests/unit/appliancevm/ -v 2>&1
      2. pytest tests/unit/bm_instance_agent/ tests/unit/appliancevm/ -v 2>&1 | grep -c 'PASSED'
    Expected Result: 所有测试 PASSED，PASSED 数量 >= 4
    Failure Indicators: FAILED, ERROR
    Evidence: .sisyphus/evidence/task-13-bm-appliancevm-unit.txt
  ```

  **Commit**: YES (group with Wave 3)
  - Message: `feat(tests): add example tests for all major modules`
  - Files: `tests/unit/bm_instance_agent/test_bm_commands.py`, `tests/unit/appliancevm/test_appliancevm_agent.py`

---

### Wave 4 — Polish (depends on Wave 3)

- [ ] 14. 使用文档 tests/README.md

  **What to do**:
  - 创建 `tests/README.md`，包含：
    - **快速开始**: `pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0` + `pytest tests/unit/` 一行跑通
    - **三种模式说明**：
      - Local (unit): `pytest tests/unit/ -v`
      - SSH (integration): `pytest tests/integration/ --ssh-host=root:pass@ip -v`
      - VM Deploy (system): `pytest tests/system/ --vm-deploy --target=ip --ssh-password=pass -v`
    - **破坏性测试说明**：
      - 什么是 destructive marker，为什么本机默认 skip
      - 如何放行: `--allow-destructive`
      - 资源子类: network, storage, disk, vm_lifecycle, os_ops
    - **Markers 说明**: 所有可用 markers 及其含义
    - **写新测试指南**: 如何添加新模块测试，fixture 用法
    - **CLI 参数参考**: 所有自定义参数说明
    - **目录结构参考**: tests/ 目录树

  **Must NOT do**:
  - 不写完整的 API 文档 — 只写使用指南
  - 不写中文版本 — 用英文（保持与开源项目一致）

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []
  - Reason: 技术写作任务

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 15, 16)
  - **Blocks**: None
  - **Blocked By**: Tasks 8, 9（需要了解完整 CLI 和示例测试）

  **References**:
  - `docs/modules/guide/pages/pytest.adoc` — 现有 pytest 文档，参考风格（但我们用 Markdown）
  - `kvmagent/kvmagent/test/unittest_tools/README.md` — 现有测试文档参考
  - 所有 Task 1-13 的实现结果 — 文档需反映实际实现

  **Acceptance Criteria**:
  - [ ] `tests/README.md` 存在且非空
  - [ ] 文档包含三种模式的完整命令示例
  - [ ] 文档包含 destructive 测试说明和 --allow-destructive 用法
  - [ ] 文档包含目录结构图

  **QA Scenarios:**
  ```
  Scenario: README 内容完整
    Tool: Bash
    Preconditions: Task 14 完成
    Steps:
      1. cat tests/README.md | grep -c 'ssh-host'
      2. cat tests/README.md | grep -c 'vm-deploy'
      3. cat tests/README.md | grep -c 'destructive'
      4. cat tests/README.md | grep -c 'allow-destructive'
      5. wc -l tests/README.md
    Expected Result: 每个 grep 至少匹配 1 次，文件至少 100 行
    Failure Indicators: grep 无匹配，文件过短
    Evidence: .sisyphus/evidence/task-14-readme.txt
  ```

  **Commit**: YES (group with Wave 4)
  - Message: `docs(tests): add README + cleanup notes`
  - Files: `tests/README.md`

---

- [ ] 15. 旧 ztest 残留代码清理标记

  **What to do**:
  - 扫描 monorepo 中与 ztest 相关的文件，记录到 `tests/CLEANUP_TODO.md`：
    - `zstacklib/zstacklib/test/utils/env.py` — envconfig.yaml reader, test_for 装饰器
    - `zstacklib/zstacklib/test/utils/remote.py` — SetupRemoteMachine（已被新框架替代）
    - `kvmagent/kvmagent/test/unittest_tools/prepare_env.sh` — 3-virtualenv 起动脚本
    - 其他引用 envconfig / test_for / DRY_RUN 的文件
  - 标记格式：文件路径 + 简短说明 + 建议操作（删除/替换/保留）
  - **不实际删除任何文件** — 只生成清理清单

  **Must NOT do**:
  - 不删除任何现有文件
  - 不修改任何现有代码

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 扫描 + 记录，无代码修改

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 14, 16)
  - **Blocks**: None
  - **Blocked By**: None（可以独立执行，但放在 Wave 4 因为优先级低）

  **References**:
  - `zstacklib/zstacklib/test/utils/env.py` — test_for / envconfig / DRY_RUN 主要实现
  - `zstacklib/zstacklib/test/utils/remote.py` — 旧 SSH 工具
  - `kvmagent/kvmagent/test/unittest_tools/` — ztest 相关脚本目录

  **Acceptance Criteria**:
  - [ ] `tests/CLEANUP_TODO.md` 存在且包含至少 5 个待清理条目
  - [ ] 每个条目包含文件路径 + 建议操作

  **QA Scenarios:**
  ```
  Scenario: 清理清单完整
    Tool: Bash
    Preconditions: Task 15 完成
    Steps:
      1. wc -l tests/CLEANUP_TODO.md
      2. grep -c 'envconfig\|test_for\|DRY_RUN\|prepare_env' tests/CLEANUP_TODO.md
    Expected Result: 文件至少 20 行，grep 至少匹配 3 次
    Failure Indicators: 文件不存在或内容过少
    Evidence: .sisyphus/evidence/task-15-cleanup.txt
  ```

  **Commit**: YES (group with Wave 4)
  - Message: `docs(tests): add README + cleanup notes`
  - Files: `tests/CLEANUP_TODO.md`

---

- [ ] 16. 端到端验证（三种模式全流程）

  **What to do**:
  - 综合验证所有三种模式的完整流程：
    - **Local 模式**:
      1. `pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0`
      2. `pytest tests/unit/ -v` — 所有单元测试通过
      3. `pytest tests/ -m "not destructive" -v` — 非破坏性测试全通
      4. `pytest tests/ -m destructive -v` — 本机自动 skip
      5. `pytest tests/ -m destructive --allow-destructive -v` — 显式放行
      6. `pytest tests/ -m unit --collect-only` — marker 过滤正确
    - **SSH 模式** (需要真实远程机器):
      7. `pytest tests/integration/ --ssh-host=root:pass@ip -v` — 远程执行成功
      8. `pytest tests/integration/ -v` (无 --ssh-host) — 全部 skip
    - **VM Deploy 模式** (需要真实 VM):
      9. `pytest tests/system/ --vm-deploy --target=ip --ssh-password=pass -v` — 部署 + 执行
      10. `pytest tests/system/ -v` (无 --vm-deploy) — 全部 skip
  - 收集所有验证结果到 `.sisyphus/evidence/task-16-e2e/`

  **Must NOT do**:
  - 不修改任何代码 — 纯验证

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 需要连接真实环境验证 SSH/VM 模式

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖所有前置任务）
  - **Parallel Group**: Wave 4 (但在 Task 9-13 完成后)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 5, 6, 8, 9-13

  **References**:
  - 所有 Task 1-15 的实现结果
  - `tests/README.md` (Task 14) — 按文档步骤验证

  **Acceptance Criteria**:
  - [ ] Local 模式: `pytest tests/unit/ -v` → 0 failures
  - [ ] Local destructive skip: `pytest tests/ -m destructive -v` → 全部 SKIPPED
  - [ ] Local destructive allow: `pytest tests/ -m destructive --allow-destructive -v` → 运行（不 skip）
  - [ ] SSH 模式: 远程执行成功（需要真实主机）
  - [ ] VM 模式: 部署 + 执行成功（需要真实 VM）
  - [ ] Marker 过滤: `pytest tests/ -m "kvmagent and unit" --collect-only` → 只收集 kvmagent 单测

  **QA Scenarios:**
  ```
  Scenario: Local 模式全流程
    Tool: Bash
    Preconditions: 所有 Task 1-15 完成
    Steps:
      1. pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0 2>&1 | tail -3
      2. pytest tests/unit/ -v 2>&1
      3. pytest tests/ -m destructive -v 2>&1
      4. pytest tests/ -m destructive --allow-destructive --collect-only 2>&1
      5. pytest tests/ -m "kvmagent and unit" --collect-only 2>&1
    Expected Result: Step 2 全 PASSED; Step 3 destructive 全 SKIPPED; Step 4 destructive 被收集（不 skip）; Step 5 只收集 kvmagent 单测
    Failure Indicators: 任何 FAILED 或 ERROR
    Evidence: .sisyphus/evidence/task-16-e2e-local.txt

  Scenario: SSH 模式 skip 验证（无需真实主机）
    Tool: Bash
    Preconditions: 所有 Task 1-15 完成
    Steps:
      1. pytest tests/integration/ -v 2>&1
    Expected Result: 所有 integration 测试 SKIPPED，原因含 'ssh-host'
    Failure Indicators: 测试实际执行
    Evidence: .sisyphus/evidence/task-16-e2e-ssh-skip.txt

  Scenario: VM Deploy 模式 skip 验证（无需真实 VM）
    Tool: Bash
    Preconditions: 所有 Task 1-15 完成
    Steps:
      1. pytest tests/system/ -v 2>&1
    Expected Result: 所有 system 测试 SKIPPED，原因含 'vm-deploy'
    Failure Indicators: 测试实际执行
    Evidence: .sisyphus/evidence/task-16-e2e-vm-skip.txt
  ```

  **Commit**: NO (纯验证，无代码变更)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run linter + `pytest tests/ --collect-only`. Review all new files for: unused imports, empty catches, hardcoded credentials, commented-out code. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Tests [N collected] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration. Test edge cases: missing SSH host, wrong password, unreachable VM. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Group | Message | Files |
|-------|---------|-------|
| Wave 1 | `feat(tests): add pytest framework foundation — config, directory structure, markers, py2 compat` | pyproject.toml, tests/conftest.py, tests/unit/, tests/integration/, tests/system/, tests/plugins/markers.py |
| Wave 2 | `feat(tests): add SSH and VM deploy runner plugins + shared fixtures` | tests/plugins/ssh_plugin.py, tests/plugins/vm_deploy_plugin.py, tests/plugins/conftest.py, tests/fixtures/ |
| Wave 3 | `feat(tests): add example tests for all major modules` | tests/unit/*, tests/integration/* |
| Wave 4 | `docs(tests): add README + cleanup notes` | tests/README.md |

---

## Success Criteria

### Verification Commands
```bash
# Install test deps (no pip install -e — monorepo has no root [project])
pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0  # Expected: success

# Collect all tests
pytest tests/ --collect-only -q  # Expected: N tests collected from all modules

# Run unit tests
pytest tests/unit/ -v  # Expected: all pass

# Filter by marker
pytest tests/ -m "unit" --collect-only  # Expected: only unit tests
pytest tests/ -m "integration" --collect-only  # Expected: only integration tests

# SSH mode (requires live host)
pytest tests/integration/ --ssh-host=root:password@192.168.x.x -v  # Expected: remote execution

# VM deploy mode (requires live host)
pytest tests/system/ --vm-deploy --target=192.168.x.x --ssh-password=password -v  # Expected: sync + run

# Help shows custom options
pytest --help | grep ssh-host  # Expected: "--ssh-host" in output
pytest --help | grep vm-deploy  # Expected: "--vm-deploy" in output
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] `pytest tests/unit/` passes with 0 failures
- [ ] SSH plugin correctly adds CLI options
- [ ] VM deploy plugin correctly adds CLI options
- [ ] All major modules have at least 1 example test
- [ ] README.md documents all 3 execution modes
