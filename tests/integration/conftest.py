# -*- coding: utf-8 -*-
"""
Integration test conftest - Auto-add integration marker and skip logic.

This conftest implements pytest_collection_modifyitems hook to automatically
apply @pytest.mark.integration to all test functions collected from this directory.

Skip logic will be added in Wave 2 when ssh_plugin is implemented.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """
    Automatically add 'integration' marker to all tests in integration/ directory.
    
    Note: Skip logic for missing --ssh-host will be implemented in Wave 2 when
    the ssh_plugin is created.
    
    Args:
        config: pytest config object
        items: list of collected test items
    """
    for item in items:
        # Only mark tests in the integration/ directory
        if 'integration' in str(item.fspath):
            item.add_marker(pytest.mark.integration)
