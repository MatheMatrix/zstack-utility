from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from zstacklib.storage.ceph import pool as modular_ceph_pool
from zstacklib.utils.jsonobject import NoneSupportedTypeError


ORDINARY_TREE = {
    "nodes": [
        {"id": -1, "name": "default", "type": "root", "children": [-3]},
        {"id": -3, "name": "dc-a", "type": "datacenter", "children": [-5]},
        {"id": -5, "name": "host-a", "type": "host", "children": [0, 1]},
        {"id": 0, "name": "osd.0", "type": "osd", "children": []},
        {"id": 1, "name": "osd.1", "type": "osd", "children": []},
    ],
    "stray": [],
}

SHADOW_TREE = {
    "nodes": ORDINARY_TREE["nodes"] + [
        {"id": -101, "name": "default~ssd", "type": "root", "children": [-103]},
        {"id": -103, "name": "dc-a~ssd", "type": "datacenter", "children": [-105]},
        {"id": -105, "name": "host-a~ssd", "type": "host", "children": [1]},
        {"id": -201, "name": "default~hdd", "type": "root", "children": [-203]},
        {"id": -203, "name": "dc-a~hdd", "type": "datacenter", "children": [-205]},
        {"id": -205, "name": "host-a~hdd", "type": "host", "children": [0]},
    ],
    "stray": [],
}

OSD_DF = {
    "nodes": [
        {"name": "osd.0", "kb": 200, "kb_avail": 160, "kb_used": 40},
        {"name": "osd.1", "kb": 300, "kb_avail": 180, "kb_used": 120},
    ]
}


def load_legacy_ceph_pool():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "zstacklib" / "zstacklib" / "utils" / "ceph.py"
    spec = importlib.util.spec_from_file_location(
        "zstacklib_utils_ceph_under_test", str(module_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["legacy", "modular"])
def ceph_pool_module(request):
    if request.param == "legacy":
        return load_legacy_ceph_pool()
    return modular_ceph_pool


def query_pool_capacity(
    monkeypatch,
    module,
    pools,
    rules,
    ordinary_tree=ORDINARY_TREE,
    shadow_tree=SHADOW_TREE,
    command_errors=None,
    raw_outputs=None,
    command_log=None,
):
    command_errors = command_errors or {}
    raw_outputs = raw_outputs or {}
    commands = command_log if command_log is not None else []
    outputs = {
        "ceph osd dump -f json": {"pools": pools},
        "ceph osd crush rule dump -f json": rules,
        "ceph osd tree -f json": ordinary_tree,
        "ceph osd crush tree --show-shadow -f json": shadow_tree,
        "ceph osd df -f json": OSD_DF,
        "ceph osd erasure-code-profile get ec-profile -f json": {
            "k": "2",
            "m": "1",
        },
    }

    def call(command):
        commands.append(command)
        if command in command_errors:
            raise command_errors[command]
        if command in raw_outputs:
            return raw_outputs[command]
        return json.dumps(outputs[command])

    monkeypatch.setattr(module.shell, "call", call)
    monkeypatch.setattr(module, "get_ceph_manufacturer", lambda: "open-source")
    return module.get_pools_capacity(), commands


def copy_pool(name, rule_id):
    return {
        "pool_name": name,
        "size": 2,
        "type": 1,
        "crush_ruleset": None,
        "crush_rule": rule_id,
    }


def ec_pool(name, rule_id):
    return {
        "pool_name": name,
        "size": 3,
        "type": 3,
        "crush_ruleset": None,
        "crush_rule": rule_id,
        "erasure_code_profile": "ec-profile",
    }


def rule(rule_id, take_name):
    return {
        "rule_id": rule_id,
        "steps": [
            {"op": "take", "item_name": take_name},
            {"op": "chooseleaf_firstn", "num": 0, "type": "datacenter"},
            {"op": "emit"},
        ],
    }


def capacities_by_pool(pools):
    return {
        pool.pool_name: (
            pool.pool_total_size,
            pool.available_capacity,
            pool.used_capacity,
            pool.crush_item_osds,
        )
        for pool in pools
    }


def test_ordinary_datacenter_rule_keeps_legacy_tree_command(
    monkeypatch, ceph_pool_module
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [copy_pool("regular", 0)],
        [rule(0, "default")],
    )

    assert capacities_by_pool(pools) == {
        "regular": (256000, 174080, 81920, ["osd.0", "osd.1"])
    }
    assert "ceph osd tree -f json" in commands
    assert "ceph osd crush tree --show-shadow -f json" not in commands


def test_shadow_datacenter_rule_uses_shadow_tree_and_restores_capacity(
    monkeypatch, ceph_pool_module
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [copy_pool("hdd", 1)],
        [rule(1, "default~hdd")],
    )

    assert capacities_by_pool(pools) == {
        "hdd": (102400, 81920, 20480, ["osd.0"])
    }
    assert "ceph osd crush tree --show-shadow -f json" in commands
    assert "ceph osd tree -f json" not in commands


@pytest.mark.parametrize("reverse_order", [False, True])
def test_mixed_pool_rules_share_all_root_tree_without_cross_counting(
    monkeypatch, ceph_pool_module, reverse_order
):
    pools = [
        copy_pool("regular", 0),
        ec_pool("ssd", 1),
        copy_pool("hdd", 2),
    ]
    rules = [
        rule(0, "default"),
        rule(1, "default~ssd"),
        rule(2, "default~hdd"),
    ]
    if reverse_order:
        pools.reverse()
        rules.reverse()

    result, commands = query_pool_capacity(
        monkeypatch, ceph_pool_module, pools, rules
    )

    assert capacities_by_pool(result) == {
        "regular": (256000, 174080, 81920, ["osd.0", "osd.1"]),
        "ssd": (204800, 122880, 81920, ["osd.1"]),
        "hdd": (102400, 81920, 20480, ["osd.0"]),
    }
    assert [pool.pool_name for pool in result] == [
        pool["pool_name"] for pool in pools
    ]
    assert commands.count("ceph osd crush tree --show-shadow -f json") == 1
    assert "ceph osd tree -f json" not in commands


@pytest.mark.parametrize("take_name", [None, ""])
def test_empty_take_name_preserves_empty_mapping(
    monkeypatch, ceph_pool_module, take_name
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [copy_pool("unmapped", 0)],
        [rule(0, take_name)],
    )

    assert capacities_by_pool(pools) == {
        "unmapped": (0, 0, 0, [])
    }
    assert "ceph osd tree -f json" in commands
    assert "ceph osd crush tree --show-shadow -f json" not in commands


def test_empty_pool_list_returns_without_querying_rules(
    monkeypatch, ceph_pool_module
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [],
        [],
    )

    assert pools == []
    assert commands == ["ceph osd dump -f json"]


def test_missing_rule_keeps_existing_empty_capacity_contract(
    monkeypatch, ceph_pool_module
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [copy_pool("unmapped", 0)],
        [],
    )

    assert capacities_by_pool(pools) == {
        "unmapped": (0, 0, 0, [])
    }
    assert "ceph osd crush tree --show-shadow -f json" not in commands


def test_empty_shadow_tree_keeps_existing_empty_capacity_contract(
    monkeypatch, ceph_pool_module
):
    pools, commands = query_pool_capacity(
        monkeypatch,
        ceph_pool_module,
        [copy_pool("hdd", 1)],
        [rule(1, "default~hdd")],
        shadow_tree={"nodes": []},
    )

    assert capacities_by_pool(pools) == {
        "hdd": (0, 0, 0, [])
    }
    assert "ceph osd crush tree --show-shadow -f json" in commands
    assert "ceph osd tree -f json" not in commands


@pytest.mark.parametrize(
    "take_name,tree_command",
    [
        ("default", "ceph osd tree -f json"),
        ("default~hdd", "ceph osd crush tree --show-shadow -f json"),
    ],
)
def test_tree_command_failure_is_not_hidden(
    monkeypatch, ceph_pool_module, take_name, tree_command
):
    error = RuntimeError("tree unavailable")
    commands = []

    with pytest.raises(RuntimeError, match="tree unavailable"):
        query_pool_capacity(
            monkeypatch,
            ceph_pool_module,
            [copy_pool("hdd", 1)],
            [rule(1, take_name)],
            command_errors={tree_command: error},
            command_log=commands,
        )

    assert commands == [
        "ceph osd dump -f json",
        "ceph osd crush rule dump -f json",
        tree_command,
    ]


@pytest.mark.parametrize(
    "take_name,tree_command",
    [
        ("default", "ceph osd tree -f json"),
        ("default~hdd", "ceph osd crush tree --show-shadow -f json"),
    ],
)
def test_malformed_tree_json_is_not_hidden(
    monkeypatch, ceph_pool_module, take_name, tree_command
):
    commands = []

    with pytest.raises(NoneSupportedTypeError):
        query_pool_capacity(
            monkeypatch,
            ceph_pool_module,
            [copy_pool("hdd", 1)],
            [rule(1, take_name)],
            raw_outputs={tree_command: "{"},
            command_log=commands,
        )

    assert commands == [
        "ceph osd dump -f json",
        "ceph osd crush rule dump -f json",
        tree_command,
    ]
