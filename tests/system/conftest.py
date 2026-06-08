# -*- coding: utf-8 -*-
"""
System test conftest - Auto-add system marker and skip logic.

This conftest implements pytest_collection_modifyitems hook to automatically
apply @pytest.mark.system to all test functions collected from this directory.

Skip logic will be added in Wave 2 when vm_deploy_plugin is implemented.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """
    Automatically add 'system' marker to all tests in system/ directory.
    
    Note: Skip logic for missing --vm-deploy will be implemented in Wave 2 when
    the vm_deploy_plugin is created.
    
    Args:
        config: pytest config object
        items: list of collected test items
    """
    vm_deploy_enabled = config.getoption("--vm-deploy", default=False)
    skip_marker = None
    if not vm_deploy_enabled:
        skip_marker = pytest.mark.skip(reason="系统测试需要 --vm-deploy 参数")

    for item in items:
        if 'system' in str(item.fspath):
            item.add_marker(pytest.mark.system)
            if skip_marker is not None:
                item.add_marker(skip_marker)
