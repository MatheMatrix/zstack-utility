from __future__ import annotations

import importlib
import sys
import pytest
from typing import cast
from unittest.mock import MagicMock

try:
    import tests.conftest  # noqa: F401

    module = importlib.import_module("cephprimarystorage.cephagent")
    module = importlib.reload(module)
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import cephprimarystorage: {e}", allow_module_level=True)


CephAgent = module.CephAgent

# rule 0 takes crush root "default"
RULE_DUMP = (
    '[{"rule_id":0,"rule_name":"replicated_rule","steps":['
    '{"op":"take","item":-1,"item_name":"default"},'
    '{"op":"chooseleaf_firstn","num":0,"type":"host"},'
    '{"op":"emit"}]}]'
)

# "default" root carries a weighted OSD -> usable
TREE_HEALTHY = (
    '{"nodes":['
    '{"id":-1,"name":"default","type":"root","children":[-3]},'
    '{"id":-3,"name":"host01","type":"host","children":[0]},'
    '{"id":0,"name":"osd.0","type":"osd","crush_weight":0.292}'
    '],"stray":[]}'
)

# the ZSTAC-85651 topology: "default" root is empty, OSDs live under a custom root
TREE_EMPTY_DEFAULT = (
    '{"nodes":['
    '{"id":-1,"name":"default","type":"root","children":[]},'
    '{"id":-9,"name":"custom","type":"root","children":[-3]},'
    '{"id":-3,"name":"host01","type":"host","children":[0]},'
    '{"id":0,"name":"osd.0","type":"osd","crush_weight":0.292}'
    '],"stray":[]}'
)


def _shell_returning(config, rule_dump, tree):
    def _call(command):
        if 'osd_pool_default_crush_rule' in command:
            return config
        if 'crush rule dump' in command:
            return rule_dump
        if 'crush tree' in command:
            return tree
        raise AssertionError('unexpected command: %s' % command)
    return _call


class TestDefaultPoolCrushRuleId:
    def test_negative_falls_back_to_zero(self):
        assert CephAgent._default_pool_crush_rule_id("-1") == 0

    def test_explicit_rule_id(self):
        assert CephAgent._default_pool_crush_rule_id(" 3 ") == 3

    def test_garbage_falls_back_to_zero(self):
        assert CephAgent._default_pool_crush_rule_id("not-a-number") == 0
        assert CephAgent._default_pool_crush_rule_id(None) == 0


class TestCrushRuleTakeRoots:
    def test_resolves_take_root(self):
        assert CephAgent._crush_rule_take_roots(RULE_DUMP, 0) == ["default"]

    def test_missing_rule_returns_empty(self):
        assert CephAgent._crush_rule_take_roots(RULE_DUMP, 7) == []


class TestCrushRootsHaveWeightedOsd:
    def test_healthy_root_is_usable(self):
        assert CephAgent._crush_roots_have_weighted_osd(TREE_HEALTHY, ["default"]) is True

    def test_empty_default_root_is_unusable(self):
        assert CephAgent._crush_roots_have_weighted_osd(TREE_EMPTY_DEFAULT, ["default"]) is False

    def test_custom_root_with_osd_is_usable(self):
        assert CephAgent._crush_roots_have_weighted_osd(TREE_EMPTY_DEFAULT, ["custom"]) is True


@pytest.mark.ceph
class TestEnsureDefaultPoolCrushRuleUsable:
    def _agent(self):
        return CephAgent.__new__(CephAgent)

    def test_passes_when_default_root_has_weighted_osd(self):
        module.shell.call = MagicMock(side_effect=_shell_returning("-1", RULE_DUMP, TREE_HEALTHY))
        # must not raise
        self._agent()._ensure_default_pool_crush_rule_usable("p1")

    def test_rejects_when_default_root_has_no_weighted_osd(self):
        module.shell.call = MagicMock(side_effect=_shell_returning("-1", RULE_DUMP, TREE_EMPTY_DEFAULT))
        with pytest.raises(Exception) as ei:
            self._agent()._ensure_default_pool_crush_rule_usable("p1")
        assert "0 capacity" in str(ei.value)

    def test_fail_open_when_ceph_query_errors(self):
        def _boom(command):
            raise RuntimeError("ceph unreachable")
        module.shell.call = MagicMock(side_effect=_boom)
        # query failure must not block pool creation
        self._agent()._ensure_default_pool_crush_rule_usable("p1")
