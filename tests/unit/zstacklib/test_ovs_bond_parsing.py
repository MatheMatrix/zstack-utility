# -*- coding: utf-8 -*-
"""
Test OvsDpdkCtl._getBondInfoList handles multiple bonds correctly.

Regression test for py3 upgrade commit b812be995 which moved
`itemDict = {}` outside the for loop, causing all bonds to share
the same dict reference.
"""
from unittest.mock import MagicMock, patch

import pytest

from zstacklib.utils.ovs import OvsDpdkCtl


@pytest.mark.unit
class TestGetBondInfoList:

    def _call(self, bond_list_org, bridge_returns, shell_returns):
        mock_self = MagicMock()
        mock_self._getBridgeFromPort = MagicMock(side_effect=bridge_returns)
        method = OvsDpdkCtl.__dict__['_getBondInfoList']
        with patch("zstacklib.utils.ovs.shell") as mock_shell:
            mock_shell.call.side_effect = shell_returns
            return method(mock_self, bond_list_org, {})

    def test_single_bond(self):
        result = self._call(
            ["---- bond0", "bond_mode: active-backup", "slave p0:enabled"],
            ["br-bond0"],
            ['"0000:65:00.0"'],
        )
        assert len(result) == 1
        assert result[0]["name"] == "bond0"
        assert result[0]["bond_mode"] == "active-backup"

    def test_multiple_bonds_independent(self):
        """Two bonds must be independent dicts, not shared references."""
        result = self._call(
            [
                "---- bond0", "bond_mode: active-backup", "slave p0:enabled",
                "---- bond1", "bond_mode: balance-slb", "slave p2:enabled",
            ],
            ["br-bond0", "br-bond1"],
            ['"0000:65:00.0"', '"0000:66:00.0"'],
        )
        assert len(result) == 2, "expected 2 bonds, got %d" % len(result)
        assert result[0]["name"] == "bond0"
        assert result[1]["name"] == "bond1"
        assert result[0]["bond_mode"] == "active-backup"
        assert result[1]["bond_mode"] == "balance-slb"
        assert result[0] is not result[1], "bond dicts must be independent objects"
