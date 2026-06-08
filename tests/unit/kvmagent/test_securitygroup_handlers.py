from __future__ import annotations

import importlib
import json
import pytest
import sys
from typing import Callable, Protocol, cast
from unittest.mock import MagicMock, patch


class _HttpModule(Protocol):
    REQUEST_BODY: str
    REQUEST_HEADER: str


class _BashModule(Protocol):
    bash_o: Callable[[str], str]


class _ShellModule(Protocol):
    run: Callable[[str], object]


class _IpModule(Protocol):
    is_ipv4: Callable[[str], bool]


class _IpsetModule(Protocol):
    IPSetManager: Callable[..., object]


class _IptablesModule(Protocol):
    FORWARD_CHAIN_NAME: str
    from_iptables_save: Callable[..., object]
    get_iptables_cmd: Callable[..., str]
    get_ip6tables_cmd: Callable[..., str]


class _SecurityGroupPluginProto(Protocol):
    config: dict[str, object]
    ZSTACK_DEFAULT_CHAIN: str

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
    bash: _BashModule
    shell: _ShellModule
    ip: _IpModule
    ipset: _IpsetModule
    iptables: _IptablesModule


class _LockModule(Protocol):
    file_lock: Callable[..., Callable[[Callable[..., object]], Callable[..., object]]]


class _LinuxModule(Protocol):
    get_all_ethernet_device_names: Callable[[], list[str]]


class _MiscModule(Protocol):
    ignoreerror: Callable[[Callable[..., object]], Callable[..., object]]

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
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Cannot import securitygroup_plugin: {e}", allow_module_level=True)


def _make_req(body_dict: dict[str, object] | None = None) -> dict[str, object]:
    http = cast(_HttpModule, cast(object, importlib.import_module("zstacklib.utils.http")))
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}


class _FakeRule:
    def __init__(self, name: str, ipset_name: str | None = None) -> None:
        self.name: str = name
        self._ipset_name: str | None = ipset_name

    def get_ipset_name(self) -> str | None:
        return self._ipset_name


class _FakeChain:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.rules: list[str] = []
        self.default_rules: list[str] = []
        self.deleted_targets: list[str] = []
        self.deleted_rules: list[str] = []
        self.user_defined_rules: list[_FakeRule] = []

    def add_rule(self, rule: str) -> None:
        self.rules.append(rule)

    def add_default_rule(self, rule: str) -> None:
        self.default_rules.append(rule)

    def flush_chain(self) -> None:
        self.rules = []
        self.default_rules = []

    def delete_rule_by_target(self, target: str) -> None:
        self.deleted_targets.append(target)

    def delete_rule(self, rule_name: str) -> None:
        self.deleted_rules.append(rule_name)
        self.user_defined_rules = [rule for rule in self.user_defined_rules if rule.name != rule_name]


class _FakeTable:
    def __init__(self, chains: list[_FakeChain] | None = None) -> None:
        self._chains: dict[str, _FakeChain] = {chain.name: chain for chain in (chains or [])}
        self.deleted_chains: list[str] = []
        self.added_chains: list[str] = []
        self.restore_called: bool = False

    def add_chain_if_not_exist(self, name: str) -> _FakeChain:
        chain = self._chains.get(name)
        if chain is None:
            chain = _FakeChain(name)
            self._chains[name] = chain
        return chain

    def add_chain(self, name: str) -> _FakeChain:
        chain = self._chains.setdefault(name, _FakeChain(name))
        self.added_chains.append(name)
        return chain

    def delete_chain(self, name: str) -> None:
        self.deleted_chains.append(name)
        _ = self._chains.pop(name, None)

    def get_chain_by_name(self, name: str) -> _FakeChain | None:
        return self._chains.get(name)

    def get_chains(self) -> list[_FakeChain]:
        return list(self._chains.values())

    def iptables_restore(self) -> None:
        self.restore_called = True


class _FakeIpSetManager:
    def __init__(self) -> None:
        self.created_sets: list[tuple[str, list[str] | str, str]] = []
        self.refresh_called: int = 0
        self.cleaned_ipsets: list[list[str]] = []

    def create_set(self, name: str, match_ips: list[str] | str, ip_version: str) -> None:
        self.created_sets.append((name, match_ips, ip_version))

    def refresh_my_ipsets(self) -> None:
        self.refresh_called += 1

    def clean_ipsets(self, ipset_names: list[str]) -> None:
        self.cleaned_ipsets.append(ipset_names)


def _make_plugin() -> _SecurityGroupPluginProto:
    lock_mod = cast(_LockModule, cast(object, importlib.import_module("zstacklib.utils.lock")))
    misc_mod = cast(_MiscModule, cast(object, importlib.import_module("zstacklib.utils.misc")))

    from tests.conftest import passthrough_lock

    def _passthrough_ignoreerror(func: Callable[..., object]) -> Callable[..., object]:
        return func

    _orig_file_lock = getattr(lock_mod, "file_lock", None)
    _orig_ignoreerror = getattr(misc_mod, "ignoreerror", None)

    lock_mod.file_lock = passthrough_lock
    misc_mod.ignoreerror = _passthrough_ignoreerror

    plugin_mod = importlib.import_module("kvmagent.plugins.securitygroup_plugin")
    _ = importlib.reload(plugin_mod)

    # Restore originals so module-level attrs don't leak across tests
    if _orig_file_lock is not None:
        lock_mod.file_lock = _orig_file_lock
    if _orig_ignoreerror is not None:
        misc_mod.ignoreerror = _orig_ignoreerror

    plugin = securitygroup_plugin.SecurityGroupPlugin.__new__(
        securitygroup_plugin.SecurityGroupPlugin
    )
    plugin.config = {}
    return plugin


def _load_rsp(result: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result))


def _setup_bash_for_cleanup() -> None:
    def _bash_o(cmd: str) -> str:
        if cmd.startswith("ipset list"):
            return "zstack-sg-dead\n0\nother\n1\nsg-unused\n0"
        return "sg-vnic0-in 0\nsg-vnic0-out 0\nsg-keep-in 1"

    securitygroup_plugin.bash.bash_o = MagicMock(side_effect=_bash_o)


@pytest.mark.kvmagent
class TestSecurityGroupCleanupUnusedRulesOnHost:
    def test_cleanup_unused_rules_on_host_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.get_all_ethernet_device_names = MagicMock(return_value=[])
        securitygroup_plugin.shell.run = MagicMock()
        _setup_bash_for_cleanup()
        ipset_manager = _FakeIpSetManager()
        securitygroup_plugin.ipset.IPSetManager = MagicMock(return_value=ipset_manager)

        default_chain = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        vnic_chain = _FakeChain("sg-vnic0-in")
        table4 = _FakeTable([default_chain, vnic_chain])
        securitygroup_plugin.iptables.FORWARD_CHAIN_NAME = "FORWARD"
        securitygroup_plugin.iptables.get_iptables_cmd = MagicMock(return_value="iptables")
        securitygroup_plugin.iptables.get_ip6tables_cmd = MagicMock(return_value="ip6tables")
        securitygroup_plugin.iptables.from_iptables_save = MagicMock(return_value=table4)

        req = _make_req({'disableIp6Tables': True})
        result = plugin.cleanup_unused_rules_on_host(req)
        rsp = _load_rsp(result)
        assert rsp['success'] is True
        assert "sg-vnic0-in" in table4.deleted_chains
        assert default_chain.deleted_targets
        assert securitygroup_plugin.shell.run.call_count >= 1


@pytest.mark.kvmagent
class TestSecurityGroupCheckDefaultRules:
    def test_check_default_sg_rules_success(self):
        plugin = _make_plugin()
        securitygroup_plugin.iptables.FORWARD_CHAIN_NAME = "FORWARD"
        table4 = _FakeTable([])
        securitygroup_plugin.iptables.from_iptables_save = MagicMock(return_value=table4)

        req = _make_req({'disableIp6Tables': True})
        result = plugin.check_default_sg_rules(req)
        rsp = _load_rsp(result)
        assert rsp['success'] is True
        sg_chain = table4.get_chain_by_name(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        assert sg_chain is not None
        assert any('RELATED,ESTABLISHED' in rule for rule in sg_chain.rules + sg_chain.default_rules)


@pytest.mark.kvmagent
class TestSecurityGroupApplyRules:
    def test_apply_rules_success(self):
        plugin = _make_plugin()
        def _is_ipv4(addr: str) -> bool:
            return ':' not in addr

        securitygroup_plugin.ip.is_ipv4 = MagicMock(side_effect=_is_ipv4)
        securitygroup_plugin.shell.run = MagicMock()
        _setup_bash_for_cleanup()

        default_chain4 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        default_chain6 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        table4 = _FakeTable([default_chain4])
        table6 = _FakeTable([default_chain6])
        securitygroup_plugin.iptables.FORWARD_CHAIN_NAME = "FORWARD"
        securitygroup_plugin.iptables.get_iptables_cmd = MagicMock(return_value="iptables")
        securitygroup_plugin.iptables.get_ip6tables_cmd = MagicMock(return_value="ip6tables")
        def _from_iptables_save(version: int | None = None) -> _FakeTable:
            return table6 if version == 6 else table4

        securitygroup_plugin.iptables.from_iptables_save = MagicMock(side_effect=_from_iptables_save)

        ipset_manager = _FakeIpSetManager()
        securitygroup_plugin.ipset.IPSetManager = MagicMock(return_value=ipset_manager)

        req = _make_req({
            'vmNicTOs': [
                {
                    'internalName': 'vnic0',
                    'vmNicUuid': 'nic-1',
                    'mac': '00:11:22:33:44:55',
                    'vmNicIps': ['10.0.0.10', 'fd00::10'],
                    'ingressPolicy': 'ALLOW',
                    'egressPolicy': 'DENY',
                    'actionCode': 'applyChain',
                    'securityGroupRefs': {'sg-uuid-1': 1, 'sg-uuid-2': 0},
                },
                {
                    'internalName': 'vnic1',
                    'vmNicUuid': 'nic-2',
                    'mac': '00:11:22:33:44:66',
                    'vmNicIps': ['10.0.0.11'],
                    'ingressPolicy': 'DENY',
                    'egressPolicy': 'ALLOW',
                    'actionCode': 'deleteChain',
                    'securityGroupRefs': {},
                },
            ],
            'ruleTOs': {
                'sg-uuid-1': [
                    {
                        'priority': 1,
                        'ruleType': 'Ingress',
                        'state': 'Enabled',
                        'ipVersion': 4,
                        'protocol': 'TCP',
                        'srcIpRange': '10.0.0.1,10.0.0.2',
                        'dstIpRange': '',
                        'dstPortRange': '22-23',
                        'action': 'ACCEPT',
                        'remoteGroupUuid': '',
                        'remoteGroupVmIps': [],
                    },
                    {
                        'priority': 2,
                        'ruleType': 'Egress',
                        'state': 'Enabled',
                        'ipVersion': 4,
                        'protocol': 'UDP',
                        'srcIpRange': '192.168.0.1-192.168.0.5',
                        'dstIpRange': '',
                        'dstPortRange': '53',
                        'action': 'DROP',
                        'remoteGroupUuid': 'remote-sg',
                        'remoteGroupVmIps': ['172.16.0.2'],
                    },
                ],
            },
            'ip6RuleTOs': {
                'sg-uuid-1': [
                    {
                        'priority': 1,
                        'ruleType': 'Ingress',
                        'state': 'Enabled',
                        'ipVersion': 6,
                        'protocol': 'ICMP',
                        'srcIpRange': 'fd00::1',
                        'dstIpRange': '',
                        'dstPortRange': '',
                        'action': 'ACCEPT',
                        'remoteGroupUuid': '',
                        'remoteGroupVmIps': [],
                    },
                ],
            },
        })
        result = plugin.apply_rules(req)
        rsp = _load_rsp(result)
        assert rsp['success'] is True
        assert table4.restore_called is True
        assert table6.restore_called is True
        assert ipset_manager.refresh_called == 1


@pytest.mark.kvmagent
class TestSecurityGroupRefreshRulesOnHost:
    def test_refresh_rules_on_host_success(self):
        plugin = _make_plugin()
        def _is_ipv4(addr: str) -> bool:
            return ':' not in addr

        securitygroup_plugin.ip.is_ipv4 = MagicMock(side_effect=_is_ipv4)
        securitygroup_plugin.shell.run = MagicMock()
        _setup_bash_for_cleanup()

        default_chain4 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        default_chain6 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        sg_chain = _FakeChain("sg-test-in")
        vnic_chain = _FakeChain("vnic-test")
        table4 = _FakeTable([default_chain4, sg_chain, vnic_chain])
        table6 = _FakeTable([default_chain6, _FakeChain("sg-test-out")])
        securitygroup_plugin.iptables.FORWARD_CHAIN_NAME = "FORWARD"
        securitygroup_plugin.iptables.get_iptables_cmd = MagicMock(return_value="iptables")
        securitygroup_plugin.iptables.get_ip6tables_cmd = MagicMock(return_value="ip6tables")
        def _from_iptables_save(version: int | None = None) -> _FakeTable:
            return table6 if version == 6 else table4

        securitygroup_plugin.iptables.from_iptables_save = MagicMock(side_effect=_from_iptables_save)

        ipset_manager = _FakeIpSetManager()
        securitygroup_plugin.ipset.IPSetManager = MagicMock(return_value=ipset_manager)

        req = _make_req({'vmNicTOs': [], 'ruleTOs': {}, 'ip6RuleTOs': {}})
        result = plugin.refresh_rules_on_host(req)
        rsp = _load_rsp(result)
        assert rsp['success'] is True
        assert table4.deleted_chains
        assert table6.deleted_chains


@pytest.mark.kvmagent
class TestSecurityGroupUpdateGroupMemberDelete:
    def test_update_group_member_delete_success(self):
        plugin = _make_plugin()
        ipset_manager = _FakeIpSetManager()
        chain4 = _FakeChain("sg-chain")
        chain4.user_defined_rules = [_FakeRule("r1", "zstack-sg-sg-uuid"), _FakeRule("r2", "other")]
        chain6 = _FakeChain("sg6-chain")
        chain6.user_defined_rules = [_FakeRule("r3", "zstack-sg6-sg-uuid")]
        table4 = _FakeTable([chain4])
        table6 = _FakeTable([chain6])
        def _from_iptables_save(version: int | None = None) -> _FakeTable:
            return table6 if version == 6 else table4

        securitygroup_plugin.iptables.from_iptables_save = MagicMock(side_effect=_from_iptables_save)

        with patch.object(securitygroup_plugin, "ipset", MagicMock(IPSetManager=MagicMock(return_value=ipset_manager))):
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
        assert chain4.deleted_rules == ["r1"]
        assert chain6.deleted_rules == ["r3"]
        assert ipset_manager.cleaned_ipsets


@pytest.mark.kvmagent
class TestSecurityGroupUpdateGroupMemberUpdate:
    def test_update_group_member_update_success(self):
        plugin = _make_plugin()
        ipset_manager = _FakeIpSetManager()

        with patch.object(securitygroup_plugin, "ipset", MagicMock(IPSetManager=MagicMock(return_value=ipset_manager))):
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
        assert len(ipset_manager.created_sets) == 2
        assert ipset_manager.refresh_called == 1


@pytest.mark.kvmagent
class TestSecurityGroupCleanupUnusedRulesWithIpv6:
    def test_cleanup_unused_rules_with_ipv6_success(self):
        plugin = _make_plugin()
        linux = cast(_LinuxModule, cast(object, importlib.import_module("zstacklib.utils.linux")))
        linux.get_all_ethernet_device_names = MagicMock(return_value=[])
        securitygroup_plugin.shell.run = MagicMock()
        _setup_bash_for_cleanup()
        ipset_manager = _FakeIpSetManager()
        securitygroup_plugin.ipset.IPSetManager = MagicMock(return_value=ipset_manager)

        default_chain4 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        default_chain6 = _FakeChain(securitygroup_plugin.SecurityGroupPlugin.ZSTACK_DEFAULT_CHAIN)
        table4 = _FakeTable([default_chain4, _FakeChain("sg-vnic0-in")])
        table6 = _FakeTable([default_chain6, _FakeChain("sg-vnic0-in")])
        securitygroup_plugin.iptables.FORWARD_CHAIN_NAME = "FORWARD"
        securitygroup_plugin.iptables.get_iptables_cmd = MagicMock(return_value="iptables")
        securitygroup_plugin.iptables.get_ip6tables_cmd = MagicMock(return_value="ip6tables")
        def _from_iptables_save(version: int | None = None) -> _FakeTable:
            return table6 if version == 6 else table4

        securitygroup_plugin.iptables.from_iptables_save = MagicMock(side_effect=_from_iptables_save)

        req = _make_req({'disableIp6Tables': False})
        result = plugin.cleanup_unused_rules_on_host(req)
        rsp = _load_rsp(result)
        assert rsp['success'] is True
        assert table4.deleted_chains
        assert table6.deleted_chains
        assert securitygroup_plugin.shell.run.call_count >= 1
