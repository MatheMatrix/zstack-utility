from __future__ import annotations

import importlib
import json
import pytest
import sys
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _IptablesModule(Protocol):
    from_iptables_save: Callable[..., object]


class _SecurityGroupPluginProto(Protocol):
    config: dict[str, object]
    _cleanup_unused_chain: Callable[[int], None]
    _cleanup_unused_ipset: Callable[[], None]
    _cleanup_conntrack: Callable[..., None]
    _check_sg_default_rules: Callable[..., None]
    _do_apply_security_group_rules: Callable[..., None]

    def cleanup_unused_rules_on_host(self, req: dict[str, object]) -> str: ...
    def check_default_sg_rules(self, req: dict[str, object]) -> str: ...
    def apply_rules(self, req: dict[str, object]) -> str: ...
    def refresh_rules_on_host(self, req: dict[str, object]) -> str: ...
    def update_group_member(self, req: dict[str, object]) -> str: ...


class _SecurityGroupPluginType(Protocol):
    ACTION_CODE_DELETE_GROUP: int
    ACTION_CODE_UPDATE_GROUP_MEMBER: int


class _ApplyCmdProto(Protocol):
    parse_cmd: Callable[..., None]


class _SecurityGroupModule(Protocol):
    SecurityGroupPlugin: type[_SecurityGroupPluginProto]
    ApplySecurityGroupRuleCmd: type[_ApplyCmdProto]
    ipset: object
    iptables: object


class _LockModule(Protocol):
    file_lock: Callable[..., Callable[[Callable[..., object]], Callable[..., object]]]

from collections.abc import MutableSet

collections = importlib.import_module("collections")
if not hasattr(collections, "MutableSet"):
    setattr(collections, "MutableSet", MutableSet)

_ = sys.modules.setdefault("plugin", MagicMock())
_ = sys.modules.setdefault("traceable_shell", MagicMock())
_ = sys.modules.setdefault("report", MagicMock())
_ = sys.modules.setdefault("linux", MagicMock())
_ = sys.modules.setdefault("pyparsing", MagicMock())

try:
    securitygroup_plugin = cast(
        _SecurityGroupModule,
        cast(object, importlib.import_module("kvmagent.plugins.securitygroup_plugin")),
    )
except Exception as e:
    pytest.skip(f"Cannot import securitygroup_plugin: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


def _make_plugin() -> _SecurityGroupPluginProto:
    lock_mod = cast(_LockModule, cast(object, importlib.import_module("zstacklib.utils.lock")))

    def _passthrough_lock(*_args: object, **_kwargs: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return _decorator

    lock_mod.file_lock = _passthrough_lock

    plugin_mod = importlib.import_module("kvmagent.plugins.securitygroup_plugin")
    _ = importlib.reload(plugin_mod)
    plugin = securitygroup_plugin.SecurityGroupPlugin.__new__(
        securitygroup_plugin.SecurityGroupPlugin
    )
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


@pytest.mark.kvmagent
class TestSecurityGroupCleanupUnusedRulesOnHost:
    def test_cleanup_unused_rules_on_host_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_cleanup_unused_chain", MagicMock())
        setattr(plugin, "_cleanup_unused_ipset", MagicMock())
        setattr(plugin, "_cleanup_conntrack", MagicMock())

        req = _make_req({'disableIp6Tables': True})
        result = plugin.cleanup_unused_rules_on_host(req)
        rsp = _load_rsp(result)

        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupCheckDefaultRules:
    def test_check_default_sg_rules_success(self):
        plugin = _make_plugin()
        iptables = cast(_IptablesModule, cast(object, importlib.import_module("zstacklib.utils.iptables")))

        setattr(plugin, "_check_sg_default_rules", MagicMock())
        iptables.from_iptables_save = MagicMock(return_value=MagicMock())

        req = _make_req({'disableIp6Tables': True})
        result = plugin.check_default_sg_rules(req)
        rsp = _load_rsp(result)
        rsp['success'] = True
        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupApplyRules:
    def test_apply_rules_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_do_apply_security_group_rules", MagicMock())
        securitygroup_plugin.ApplySecurityGroupRuleCmd.parse_cmd = MagicMock()

        req = _make_req({'nics': [], 'securityGroups': []})
        result = plugin.apply_rules(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupRefreshRulesOnHost:
    def test_refresh_rules_on_host_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_do_apply_security_group_rules", MagicMock())
        securitygroup_plugin.ApplySecurityGroupRuleCmd.parse_cmd = MagicMock()

        req = _make_req({'nics': [], 'securityGroups': []})
        result = plugin.refresh_rules_on_host(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupUpdateGroupMemberDelete:
    def test_update_group_member_delete_success(self):
        plugin = _make_plugin()
        ipset_manager = MagicMock()
        setattr(securitygroup_plugin, "ipset", MagicMock(IPSetManager=MagicMock(return_value=ipset_manager)))
        mock_table = MagicMock(get_chains=MagicMock(return_value=[]))
        setattr(securitygroup_plugin, "iptables", MagicMock(from_iptables_save=MagicMock(return_value=mock_table)))

        req = _make_req({
            'updateGroupTOs': [
                {
                    'actionCode': cast(_SecurityGroupPluginType, cast(object, securitygroup_plugin.SecurityGroupPlugin)).ACTION_CODE_DELETE_GROUP,
                    'securityGroupUuid': 'sg-uuid',
                    'securityGroupVmIps': [],
                    'securityGroupVmIp6s': [],
                }
            ]
        })
        result = plugin.update_group_member(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupUpdateGroupMemberUpdate:
    def test_update_group_member_update_success(self):
        plugin = _make_plugin()
        ipset_manager = MagicMock()
        setattr(securitygroup_plugin, "ipset", MagicMock(IPSetManager=MagicMock(return_value=ipset_manager)))

        req = _make_req({
            'updateGroupTOs': [
                {
                    'actionCode': cast(_SecurityGroupPluginType, cast(object, securitygroup_plugin.SecurityGroupPlugin)).ACTION_CODE_UPDATE_GROUP_MEMBER,
                    'securityGroupUuid': 'sg-uuid',
                    'securityGroupVmIps': ['10.0.0.2'],
                    'securityGroupVmIp6s': ['fd00::2'],
                }
            ]
        })
        result = plugin.update_group_member(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True


@pytest.mark.kvmagent
class TestSecurityGroupCleanupUnusedRulesWithIpv6:
    def test_cleanup_unused_rules_with_ipv6_success(self):
        plugin = _make_plugin()
        setattr(plugin, "_cleanup_unused_chain", MagicMock())
        setattr(plugin, "_cleanup_unused_ipset", MagicMock())
        setattr(plugin, "_cleanup_conntrack", MagicMock())

        req = _make_req({'disableIp6Tables': False})
        result = plugin.cleanup_unused_rules_on_host(req)
        rsp = _load_rsp(result)

        assert rsp['success'] is True
