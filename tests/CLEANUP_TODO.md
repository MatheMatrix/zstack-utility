# ztest Migration and Cleanup Checklist

This document tracks legacy `ztest` infrastructure and test files that should be cleaned up or migrated to the new `pytest` framework. 

## Overview

The legacy `ztest` framework relied on `envconfig.yaml`, the `@test_for` decorator, and a complex 3-virtualenv setup. The new `pytest` infrastructure in `/tests` replaces these with standard `pytest` patterns, CLI arguments, and the `ssh_plugin.py` for remote execution.

### Migration Goals
- Replace `@test_for` with standard `pytest` functions.
- Replace `envconfig.yaml` dependency with CLI arguments (e.g., `--ssh-host`).
- Abandon `DRY_RUN` mechanism in favor of `pytest` native logic.
- Replace `SetupRemoteMachine` with `tests/plugins/ssh_plugin.py`.

---

## Core Infrastructure (Delete after migration)

These files constitute the old `ztest` core. Once all tests using them are migrated, these should be removed.

| File Path | Description | Action |
|-----------|-------------|--------|
| `zstacklib/zstacklib/test/utils/env.py` | Heart of `ztest`: `envconfig.yaml` reader, `test_for` decorator, `DRY_RUN` logic. | **Delete** |
| `zstacklib/zstacklib/test/utils/remote.py` | `SetupRemoteMachine` class for SSH execution. Replaced by `ssh_plugin.py`. | **Delete** |
| `kvmagent/kvmagent/test/unittest_tools/prepare_env.sh` | Heavy 3-virtualenv bootstrapper. | **Keep** (Still used for VM environment preparation) |

---

## Legacy Test Files (Require Migration)

The following files use legacy `ztest` patterns (`test_for`, `envconfig`, `DRY_RUN`) and should be converted to `pytest` style.

### kvmagent libvirt & plugin testsuites
- `kvmagent/kvmagent/test/libvirt_testsuite/test_memory_ballooning.py`
- `kvmagent/kvmagent/test/libvirt_testsuite/test_edk2_ovmf.py`
- `kvmagent/kvmagent/test/libvirt_testsuite/test_hyperv_params.py`
- `kvmagent/kvmagent/test/mevoco_plugin_testsuite/test_flatdhcp_delete.py`
- `kvmagent/kvmagent/test/mevoco_plugin_testsuite/test_network.py`
- `kvmagent/kvmagent/test/test_snapshots.py`
- `kvmagent/kvmagent/test/test_host.py`

### kvmagent vm_plugin_testsuite
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_vm_sync.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_vm_cpu_vendor.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_cpu_topology.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_start_vm_stop_vm_destroy_vm.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_apply_memory_balloon.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_get_cpu_model_and_compare.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_get_console_port.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_vm_dump.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_check_vm_xml_defaultvalue.py`
- `kvmagent/kvmagent/test/vm_plugin_testsuite/test_online_change_cpumem.py`

### Other Legacy Tests
- `zstacklib/zstacklib/test/lvm/test_force_release_lv_lock.py` (Uses `envconfig` pattern)
- `zstacklib/zstacklib/test/test_form.py` (Uses `envconfig` pattern)

---

## Manual Investigation Required

| File Path | Note |
|-----------|------|
| `zstackctl/zstackctl/ctl.py` | Potential reference to `envconfig`. Check if it is test-related or production code before any action. |

---

## Migration Guidance

To migrate a legacy test to the new framework:

1. **Remove Imports**: Delete `from zstacklib.test.utils import env`.
2. **Remove Decorators**: Delete `@env.test_for(...)`.
3. **Handle Config**: Replace any `env.get_config()` or `envconfig.yaml` lookups with `pytest` fixtures or command-line parameters.
4. **Update Remote Logic**: If using `SetupRemoteMachine`, switch to the `ssh_client` fixture provided by the new plugin.
5. **Standardize Naming**: Ensure test files start with `test_` and functions start with `test_` so `pytest` picks them up automatically.
6. **Cleanup**: Once the new test is verified, mark the old file for deletion in this checklist.
