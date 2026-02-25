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
    for item in items:
        # Only mark tests in the system/ directory
        if 'system' in str(item.fspath):
            item.add_marker(pytest.mark.system)
