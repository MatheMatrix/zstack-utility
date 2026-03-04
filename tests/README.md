# ZStack Utility Test Framework

This framework provides a modern, pytest-based testing environment for the zstack-utility monorepo. It replaces the legacy ztest system with a faster, more flexible, and highly modular architecture designed for Python 3 while maintaining compatibility with Python 2 subpackages.

## Directory Structure

```text
tests/
├── conftest.py              # Root configuration and Py2 mock layer
├── fixtures/
│   └── common.py            # Shared fixtures (project_root, tmp_test_dir, etc.)
├── plugins/
│   ├── markers.py           # Custom markers and destructive safety plugin
│   ├── ssh_plugin.py        # SSH runner and client fixtures
│   └── vm_deploy_plugin.py  # VM deployment and synchronization plugin
├── unit/                    # Unit tests (isolated, local execution)
│   ├── conftest.py          # Auto-marks tests with @pytest.mark.unit
│   └── ...
├── integration/             # Integration tests (requires SSH access)
│   ├── conftest.py          # Auto-marks tests with @pytest.mark.integration
│   └── ...
└── system/                  # System tests (requires VM deployment)
    ├── conftest.py          # Auto-marks tests with @pytest.mark.system
    └── ...
```

## Quick Start

### Prerequisites

Install the required dependencies using pip:

```bash
pip install pytest>=7.0 pytest-timeout>=2.0 pytest-mock>=3.0 paramiko>=2.0 coverage>=7.0
```

### Running Tests

To run all unit tests locally:

```bash
pytest tests/unit/ -v
```

## Three Execution Modes

The framework supports three distinct execution modes tailored for different testing needs.

### 1. Local Mode (Unit Tests)
This is the default mode. It runs tests locally without requiring external infrastructure. It's intended for fast feedback during development.

```bash
pytest tests/unit/ -v
```

### 2. SSH Mode (Integration Tests)
This mode connects to a remote host via SSH to execute tests that interact with real system resources.

```bash
pytest tests/integration/ --ssh-host=root:password@192.168.1.100 -v
```

### 3. VM Deploy Mode (System Tests)
This mode automatically synchronizes the local repository to a target VM, installs dependencies, and runs system-level tests.

```bash
pytest tests/system/ --vm-deploy --target=192.168.1.101 --ssh-password=password -v
```

### 4. HTTP Agent Mode (Integration Tests)
This mode uses SSH tunneling to directly test agent HTTP handlers on a remote host. It bypasses the ZStack management node and communicates with agents (kvmagent, virtualrouter, etc.) via their respective ports (e.g., 7070, 7272).

#### SSH Tunnel Architecture
The framework uses `paramiko` to establish a direct-tcpip tunnel from your local machine to the remote agent ports. This allows tests running on macOS or other development environments to reach agents restricted to the remote host's loopback or internal network.
- **Local 7070** -> **Remote 7070** (kvmagent)
- **Local 7272** -> **Remote 7272** (virtualrouter)
- **Local 7759** -> **Remote 7759** (appliancevm)
- **Local 7761** -> **Remote 7761** (ceph-backup)
- **Local 7762** -> **Remote 7762** (ceph-primary)

#### Running HTTP Tests
To run HTTP integration tests, provide the remote host details via `--ssh-host`:

```bash
pytest tests/http/ --ssh-host=root:password@192.168.1.100 -v
```

#### Coverage Details
The HTTP test suite covers the following agents and handlers:

| Agent | Tests | Handlers Covered | Examples |
| :--- | :--- | :--- | :--- |
| `kvmagent` | 14 | 11 | host, VM, network, storage plugins |
| `virtualrouter` | 3 | 3 | `/init`, `/ping`, `/echo` |
| `appliancevm` | 1 | 1 | `/appliancevm/echo` |
| `ceph backup` | 2 | 2 | `/ceph/backupstorage/echo`, `/ping` |
| `ceph primary` | 2 | 2 | `/ceph/primarystorage/echo`, `/ping` |

These tests use the `requests` library directly and contain zero dependencies on `zstacklib`, ensuring they can run in isolated Python 3 environments.

## Destructive Test Safety System

To prevent accidental damage to the development environment, the framework includes a safety mechanism for destructive tests.

Tests marked with `destructive` (or any resource-specific destructive marker like `network`, `storage`, etc.) are **automatically skipped** when running in local mode.

To allow destructive tests in local mode, use the `--allow-destructive` flag:

```bash
pytest tests/unit/ --allow-destructive -v
```

Destructive tests are automatically permitted when running in SSH or VM Deploy modes, as these are assumed to target non-local, disposable environments.

## Markers Reference

The following markers are available for categorizing and filtering tests:

| Marker | Description |
| :--- | :--- |
| `unit` | Unit tests - isolated components, no external dependencies |
| `integration` | Integration tests - multiple components working together |
| `system` | System tests - end-to-end functionality tests |
| `slow` | Slow-running tests that may take significant time |
| `destructive` | Parent marker for tests that may modify system state |
| `network` | Destructive tests affecting network resources |
| `storage` | Destructive tests affecting storage resources |
| `disk` | Destructive tests affecting disk/filesystem resources |
| `vm_lifecycle` | Destructive tests affecting VM lifecycle |
| `os_ops` | Destructive tests affecting OS-level operations |
| `kvmagent` | Tests related to KVM agent functionality |
| `zstacklib` | Tests related to zstacklib module |
| `virtualrouter` | Tests related to virtual router |
| `apibinding` | Tests related to API binding |
| `sftpbackupstorage`| Tests related to SFTP backup storage |
| `ceph` | Tests related to Ceph storage |
| `bm_instance` | Tests related to bare metal instances |
| `appliancevm` | Tests related to appliance VMs |

## CLI Parameters Reference

The framework introduces several custom command-line options:

| Option | Description |
| :--- | :--- |
| `--ssh-host` | SSH connection info: `user:pass@host` or `user@host` |
| `--ssh-password` | SSH password override if not provided in `--ssh-host` |
| `--ssh-key` | Path to private key for key-based authentication |
| `--vm-deploy` | Enable VM deployment runner for system tests |
| `--target` | Target VM IP address (required for `--vm-deploy`) |
| `--allow-destructive` | Force allow destructive tests in local mode |

**Rules:**
- `--ssh-host` and `--vm-deploy` are mutually exclusive.
- `--vm-deploy` requires `--target` to be specified.

## Writing New Tests

Follow these steps to add a test for a new module:

1. **Location**: Create a new test file in the appropriate directory, e.g., `tests/unit/mymodule/test_feature.py`.
2. **Markers**: Apply module-specific markers to your test class or function:
   ```python
   @pytest.mark.kvmagent
   def test_my_feature():
       assert True
   ```
3. **Fixtures**: Use shared fixtures from `tests/fixtures/common.py`. They are automatically available.
   ```python
   def test_with_root(project_root):
       assert project_root.exists()
   ```
4. **Destructive Tests**: If your test modifies the system, mark it with an appropriate destructive marker:
   ```python
   @pytest.mark.os_ops
   def test_dangerous_operation():
       pass
   ```

## Py2 Compatibility Layer

The `tests/conftest.py` file contains a mock layer that facilitates running tests against subpackages written in Python 2. 

When the test session starts, the framework:
- Auto-discovers all subpackages in the monorepo and adds them to `sys.path`.
- Mocks core utility modules (like `zstacklib.utils.log`, `bash`, `http`) using `unittest.mock.MagicMock`.
- Injects these mocks into `sys.modules` before any subpackage imports occur.

This allows Python 3's `pytest` to collect and execute tests even if the underlying code uses Python 2-specific syntax or unavailable native libraries.
