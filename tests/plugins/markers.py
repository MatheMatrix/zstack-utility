# -*- coding: utf-8 -*-
"""
Markers Plugin - Define and register all pytest markers.

This plugin provides:
1. Central registry of all pytest markers (unit, integration, system, destructive, etc.)
2. Marker registration via pytest_configure hook
3. CLI option registration (--allow-destructive flag)
4. Destructive test safety mechanism via pytest_collection_modifyitems hook:
   - Auto-skips destructive tests in local mode (no --ssh-host, no --vm-deploy)
   - Allows destructive tests with --allow-destructive flag
   - Allows destructive tests in SSH/VM modes
"""

import pytest


# ============================================================================
# MARKER REGISTRY - All markers with descriptions
# ============================================================================
MARKERS = {
    # Standard test classification markers
    "unit": "Unit tests - isolated components, no external dependencies",
    "integration": "Integration tests - multiple components working together",
    "system": "System tests - end-to-end functionality tests",
    "slow": "Slow-running tests that may take significant time",
    
    # Destructive tests parent marker
    "destructive": "Destructive tests - may modify system state (parent marker for all resource types)",
    
    # Destructive test subtypes (resource categories)
    "network": "Destructive tests affecting network resources",
    "storage": "Destructive tests affecting storage resources",
    "disk": "Destructive tests affecting disk/filesystem resources",
    "vm_lifecycle": "Destructive tests affecting VM lifecycle (create/delete/etc)",
    "os_ops": "Destructive tests affecting OS-level operations",
    
    # Module-specific markers
    "kvmagent": "Tests related to KVM agent functionality",
    "zstacklib": "Tests related to zstacklib module",
    "virtualrouter": "Tests related to virtual router",
    "apibinding": "Tests related to API binding",
    "sftpbackupstorage": "Tests related to SFTP backup storage",
    "ceph": "Tests related to Ceph storage",
    "bm_instance": "Tests related to bare metal instances",
    "appliancevm": "Tests related to appliance VMs",
}


def pytest_configure(config):
    """Register all markers with pytest."""
    for marker_name, description in MARKERS.items():
        config.addinivalue_line(
            "markers",
            f"{marker_name}: {description}"
        )


def pytest_addoption(parser):
    """Register custom CLI options."""
    parser.addoption(
        "--allow-destructive",
        action="store_true",
        default=False,
        help="Allow destructive tests to run in local mode (default: False). "
             "Destructive tests are automatically allowed in SSH/VM deployment modes."
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    """
    Auto-skip destructive tests in local mode (safety mechanism).
    
    Destructive test safety logic:
    1. Check if test has ANY destructive-related marker (destructive, network, storage, disk, vm_lifecycle, os_ops)
    2. Check if we're in local mode (no --ssh-host AND no --vm-deploy)
    3. Check if --allow-destructive flag is NOT set
    4. If all conditions met: auto-skip the test with descriptive reason
    
    Hook runs AFTER conftest auto-marking hooks due to @pytest.hookimpl(trylast=True),
    so we can safely check all markers that have been applied.
    """
    
    # Destructive-related marker names
    destructive_markers = {
        "destructive", "network", "storage", "disk", "vm_lifecycle", "os_ops"
    }
    
    # Check if we're in local mode (no SSH/VM deployment)
    is_local_mode = (
        not config.getoption("--ssh-host", default=None) and
        not config.getoption("--vm-deploy", default=None)
    )
    
    # Check if --allow-destructive flag is set
    allow_destructive = config.getoption("--allow-destructive")
    
    # Skip destructive tests if in local mode and flag not set
    if is_local_mode and not allow_destructive:
        for item in items:
            # Check if this test has ANY destructive marker
            has_destructive_marker = any(
                marker.name in destructive_markers
                for marker in item.iter_markers()
            )
            
            if has_destructive_marker:
                reason = (
                    "破坏性测试不允许在本机跑，使用 --allow-destructive 或 --ssh-host / --vm-deploy"
                )
                item.add_marker(pytest.mark.skip(reason=reason))
