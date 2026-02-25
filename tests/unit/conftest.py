# -*- coding: utf-8 -*-
"""
Unit test conftest - Auto-add unit marker to all tests in this directory.

This conftest implements pytest_collection_modifyitems hook to automatically
apply @pytest.mark.unit to all test functions collected from this directory.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """
    Automatically add 'unit' marker to all tests in unit/ directory.
    
    Args:
        config: pytest config object
        items: list of collected test items
    """
    for item in items:
        # Only mark tests in the unit/ directory
        if 'unit' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
