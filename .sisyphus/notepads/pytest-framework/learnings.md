# Learnings — pytest-framework

> Conventions, patterns, gotchas discovered during implementation

<!-- Subagents: APPEND findings here with timestamp + task ID -->

## [2026-02-25 18:35] Task 1: pyproject.toml configuration

### Findings:
- **Configuration Status**: pyproject.toml was already present with complete pytest configuration
- **Configuration Contents**:
  - `testpaths = ["tests"]` ✓
  - `python_files = "test_*.py"` ✓
  - `python_classes = "Test*"` ✓
  - `python_functions = "test_*"` ✓
  - `addopts = "-ra -q --strict-markers"` ✓
  - All 13 markers defined (unit, integration, system, slow, destructive, network, storage, disk, vm_lifecycle, os_ops, kvmagent, zstacklib, virtualrouter, apibinding, sftpbackupstorage, ceph, bm_instance, appliancevm) ✓

### Test Dependencies Status:
- All required packages already installed:
  - pytest 9.0.2 (requirement: >=7.0) ✓
  - pytest-timeout 2.4.0 (requirement: >=2.0) ✓
  - pytest-mock 3.15.1 (requirement: >=3.0) ✓
  - paramiko 4.0.0 (requirement: >=2.0) ✓
  - coverage 7.13.4 (requirement: >=7.0) ✓

### QA Verification Results:
- **Scenario 1 (Dependencies)**: All pip installs successful, pytest version check passed (9.0.2 >= 7.0)
- **Scenario 2 (Configuration)**: testpaths configuration verified in pyproject.toml

### Lessons Learned:
1. macOS Homebrew Python requires `--break-system-packages` flag for pip installs
2. pyproject.toml for pytest configuration was already correctly set up from previous work
3. All test infrastructure dependencies are properly installed and available
4. No configuration changes were needed — the file was already in the correct state

### Blocked Tasks Unblocked:
- Tasks 2, 3, 4, 5, 6, 7, 8 can now proceed with proper pytest infrastructure

## Task 2: tests/ Directory Structure + conftest.py Hierarchy

**Timestamp:** 2026-02-25 | **Status:** ✓ COMPLETED

### Key Findings

1. **Three-Layer Hierarchy Successfully Implemented**
   - `tests/unit/conftest.py` → Auto-adds `@pytest.mark.unit` via `pytest_collection_modifyitems`
   - `tests/integration/conftest.py` → Auto-adds `@pytest.mark.integration` 
   - `tests/system/conftest.py` → Auto-adds `@pytest.mark.system`
   - Root `tests/conftest.py` → Registers plugins and provides shared fixtures

2. **Plugin Architecture Pattern**
   - `pytest_plugins = [...]` list in root conftest auto-discovers and loads plugins
   - Plugins can be empty placeholders initially (tested with markers.py, ssh_plugin.py, vm_deploy_plugin.py)
   - Pattern allows Wave 2 implementation without breaking existing structure

3. **Hook Implementation Details**
   - `pytest_collection_modifyitems(config, items)` signature must match exactly
   - Marker detection via `'unit' in str(item.fspath)` works reliably for layer isolation
   - Each layer conftest.py calls only its own marker (no cross-contamination)

4. **Directory Structure Verification**
   - 24 Python files total (including __init__.py and placeholders)
   - All subdirectories include __init__.py (kvmagent, zstacklib, apibinding, etc.)
   - Fixture and plugins directories properly isolated

5. **pytest Collection Behavior**
   - `pytest tests/ --collect-only` exit code 0 (success) when no tests exist
   - Exit code 5 reserved for cases with syntax/import errors
   - Root conftest imports successfully via `from tests.conftest import *`

### QA Results
- **Scenario 1 (Directory Structure):** ✓ PASS
  - All conftest.py files exist
  - All plugin files exist  
  - File count: 24 (requirement: >= 20)
  - Exit code: 0

- **Scenario 2 (pytest Collection):** ✓ PASS
  - `pytest tests/ --collect-only` → exit code 0
  - No ImportError/SyntaxError
  - Import verification: `from tests.conftest import *` → OK

### Blockers for Wave 2
- ssh_plugin.py needs --ssh-host CLI option binding
- vm_deploy_plugin.py needs --vm-deploy CLI option binding
- Skip logic should go in these plugins, not in unit/integration/system conftest files

### Conventions Established
- Layer-specific conftest.py files are shallow: only marker hook
- Root conftest.py is plugin registry + shared fixtures
- Placeholder files should have docstring explaining Wave 2/Task X implementation


## Task 4: Py2 Compatibility Mock Layer + sys.path Auto-discovery

### Key Implementation Details

1. **sys.path Auto-discovery (MUST be at module-level, not in fixture)**
   - Runs during conftest.py module load, BEFORE pytest test collection
   - Scans repo root for subdirs with setup.py or setup.cfg
   - Adds all 19 subpackages to sys.path (kvmagent, zstacklib, virtualrouter, etc.)
   - Uses sorted iteration for consistent ordering
   - Checks `if child_str not in sys.path` to avoid duplicates

2. **Py2 Compatibility Mock Architecture**
   - Three-tier approach:
     a) Log mock: `types.ModuleType('zstacklib.utils.log')` with `get_logger()` returning MagicMock
     b) Bash mock: Full module with `bash_roe`, `bash_ro`, `bash_r` dummy functions
     c) Simple mocks: 11 other modules as plain MagicMock() objects
   - All mocks installed to sys.modules at conftest load time
   - No dynamic patching needed during tests

3. **Fixture Pattern for Mock Verification**
   - `@pytest.fixture(autouse=True, scope='session')` on `mock_zstacklib_imports()`
   - Fixture asserts mocks are present (defensive check)
   - Autouse ensures runs for every test session
   - Session scope keeps mocks active throughout test run
   - NOTE: Actual mocking happens at module level, fixture just verifies

4. **Why Module-Level Over Fixture-Level**
   - pytest loads conftest.py BEFORE fixtures execute
   - If conftest or test_*.py files import from subpackages, sys.path must be ready
   - Fixtures run AFTER test collection, too late for import-time side effects
   - Module-level code executes during pytest bootstrap phase

### Testing Evidence
- conftest.py imports without errors (✓)
- All 19 subpackages added to sys.path (✓)
- Mock modules: log, bash, libvirt, shell, linux, daemon all present (✓)
- bash_roe/bash_ro/bash_r return correct dummy values (✓)
- get_logger returns MagicMock (✓)
- fixture mock_zstacklib_imports present and autouse=True (✓)

### Patterns from Reference Files
- zstacklib/conftest.py: Showed the original Py2 mock pattern we adapted
- kvmagent/test/utils/pytest_utils.py: PytestExtension.setup_modules_mock() showed module-level patching pattern
- Both confirmed module-level setup is the right approach for mocking

### Compatibility Notes
- Works with Python 3.6+ (uses pathlib.Path, unittest.mock.MagicMock)
- Py2-only modules (libvirt, shell, daemon, etc.) become importable mocks
- Subpackage imports now work without pip install -e
- pytest --collect-only succeeds (no import failures)


## Task 3: Markers Definition + Registration (2026-02-25)

### Implementation Summary
Created `tests/plugins/markers.py` with complete marker registry and destructive test safety mechanism.

### Key Implementation Details

#### 1. Marker Registry
- **Standard test classification**: unit, integration, system, slow
- **Destructive parent marker**: destructive (with clear description)
- **Destructive resource subtypes**: network, storage, disk, vm_lifecycle, os_ops
- **Module-specific markers**: kvmagent, zstacklib, virtualrouter, apibinding, sftpbackupstorage, ceph, bm_instance, appliancevm
- All markers registered via `pytest_configure(config)` hook with clear, descriptive strings

#### 2. CLI Option Registration
- `--allow-destructive` flag registered via `pytest_addoption(parser)` hook
- Boolean flag (store_true action)
- Helps users explicitly allow destructive tests in local mode
- Visible in `pytest --help` output

#### 3. Destructive Test Safety Mechanism
Key hook: `pytest_collection_modifyitems(session, config, items)` with `@pytest.hookimpl(trylast=True)`

**Logic Flow**:
1. Check if test has ANY of: destructive, network, storage, disk, vm_lifecycle, os_ops markers
2. Check if in local mode: no --ssh-host AND no --vm-deploy
3. Check if --allow-destructive flag NOT set
4. If all conditions met: auto-skip with reason: "破坏性测试不允许在本机跑，使用 --allow-destructive 或 --ssh-host / --vm-deploy"

**Why `@pytest.hookimpl(trylast=True)`**:
- Conftest files (unit/integration/system) run FIRST and auto-mark tests
- Plugin hooks (markers.py) run LAST to check all applied markers
- Guarantees we see all markers from earlier hooks

### Verification Results

**Scenario 1: All markers registered**
✓ pytest --markers shows:
  - @pytest.mark.unit: Unit tests - isolated components, no external dependencies
  - @pytest.mark.integration: Integration tests - multiple components working together
  - @pytest.mark.system: System tests - end-to-end functionality tests
  - @pytest.mark.destructive: Destructive tests - may modify system state (parent marker for all resource types)
  - @pytest.mark.network: Destructive tests affecting network resources
  - @pytest.mark.storage: Destructive tests affecting storage resources
  - @pytest.mark.kvmagent: Tests related to KVM agent functionality
  - (+ all other module-specific markers)

**Scenario 2: No unknown marker errors**
✓ pytest --strict-markers -m 'destructive' tests/ --collect-only → no error (0 tests collected, which is expected)
✓ pytest --strict-markers -m 'network or storage or disk' tests/ --collect-only → no error
✓ pytest --strict-markers -m 'kvmagent or zstacklib or virtualrouter' tests/ --collect-only → no error

**Scenario 3: --allow-destructive visible**
✓ pytest --help | grep allow-destructive → shows option with description

**Scenario 4: Destructive test safety mechanism works**
✓ Local mode (no flags): Destructive tests auto-skipped with proper message
✓ With --allow-destructive: Destructive tests run normally
✓ Skip message is in Chinese: "破坏性测试不允许在本机跑，使用 --allow-destructive 或 --ssh-host / --vm-deploy"

### Plugin Registration
- Already registered in tests/conftest.py pytest_plugins list (line 77: 'tests.plugins.markers')
- Loads BEFORE test modules due to conftest.py loading order
- Hooks executed in proper order thanks to @pytest.hookimpl(trylast=True)

### Gotchas & Patterns Discovered
1. **Hook execution order matters**: Use @pytest.hookimpl(trylast=True) in markers.py to ensure it runs AFTER conftest auto-marking hooks
2. **Marker checking**: Use `item.iter_markers()` to safely get all markers applied to a test
3. **Config option access**: Use config.getoption("option_name", default=None) to safely get CLI options
4. **Chinese messages**: Skip reason messages use Chinese characters for user-facing output
5. **Marker registration**: Use config.addinivalue_line() in pytest_configure hook, NOT config.addinivalue()

### Dependencies & Follow-ups
- This task UNBLOCKS:
  - Task 8 (Optional: Flaky test auto-retry via pytest-rerunfailures)
  - Tasks 9-13 (Test classification auto-marking in unit/integration/system conftest files)
- Ready for Tasks 5 & 6 (SSH and VM deploy plugins) to add their CLI options

### Code Quality
- ✓ All hooks documented with clear docstrings
- ✓ Marker registry is maintainable (easy to add new markers)
- ✓ Safety mechanism is explicit and easy to understand
- ✓ Chinese user messages for consistency with project
- ✓ No external dependencies required (uses pytest built-ins only)
