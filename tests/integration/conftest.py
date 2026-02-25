# -*- coding: utf-8 -*-
"""
Integration test conftest - Auto-add integration marker and skip logic.

This conftest implements pytest_collection_modifyitems hook to automatically
apply @pytest.mark.integration to all test functions collected from this directory.

Skip logic will be added in Wave 2 when ssh_plugin is implemented.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    ssh_host = config.getoption("--ssh-host", default=None)
    for item in items:
        # Only mark tests in the integration/ directory
        if 'integration' in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            if not ssh_host:
                item.add_marker(pytest.mark.skip(reason="集成测试需要 --ssh-host 参数"))
