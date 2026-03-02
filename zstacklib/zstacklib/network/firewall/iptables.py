"""IPTables rule management.

Provides classes for parsing, modifying, and restoring iptables rules.
"""

import os
from functools import cmp_to_key
from typing import Optional, List, Callable, Any

from pyparsing import Literal, Word, alphas, printables, restOfLine

from zstacklib.utils import shell, linux, log, ordered_set
from zstacklib.network.firewall.node import Node
from zstacklib.network.firewall.exceptions import IPTablesError

logger = log.get_logger(__name__)

_iptablesUseLock: Optional[bool] = None


def get_iptables_cmd(command: Optional[str] = None) -> str:
    """Get the appropriate iptables command with lock flag if supported."""
    global _iptablesUseLock
    
    if _iptablesUseLock is None:
        _iptablesUseLock = shell.run("iptables -w -nL > /dev/null") == 0

    if command is None:
        return "iptables -w" if _iptablesUseLock else "iptables"
    elif command == "restore":
        return "iptables-restore -w" if _iptablesUseLock else "iptables-restore"
    return "iptables"


class IPTableTable(Node):
    """Represents an iptables table (filter, nat, mangle, etc.)."""
    
    def __str__(self) -> str:
        lst = ['%s' % self.identity]
        for chain in self.children:
            lst.append(chain.counter_str)
        for chain in self.children:
            cstr = str(chain)
            if cstr == '':
                continue
            lst.append(cstr)
        lst.append('COMMIT')
        return '\n'.join(lst)


class IPTableChain(Node):
    """Represents an iptables chain (INPUT, OUTPUT, FORWARD, etc.)."""
    
    def __init__(self):
        super().__init__()
        self.counter_str: Optional[str] = None

    def delete_all_rules(self) -> None:
        self.children = []

    def __str__(self) -> str:
        if not self.children:
            return ''

        rules = sorted(self.children, key=lambda r: r.order, reverse=True)
        lst = ordered_set.OrderedSet()
        for r in rules:
            lst.add(str(r))
        return '\n'.join(lst)


class IPTableRule(Node):
    """Represents a single iptables rule."""
    
    def __init__(self):
        super().__init__()
        self.order: int = 0

    def __str__(self) -> str:
        return self.identity or ''


class IPTables(Node):
    """Main class for managing iptables rules.
    
    Supports parsing from iptables-save output and restoring via iptables-restore.
    """
    
    NAT_TABLE_NAME = 'nat'
    FILTER_TABLE_NAME = 'filter'
    MANGLE_TABLE_NAME = 'mangle'
    SECURITY_TABLE_NAME = 'security'
    RAW_TABLE_NAME = 'raw'

    def __init__(self):
        super().__init__()
        self._parser = None
        self._current_table: Optional[IPTableTable] = None
        self._filter_table: Optional[IPTableTable] = None
        self._nat_table: Optional[IPTableTable] = None
        self._mangle_table: Optional[IPTableTable] = None
        self._raw_table: Optional[IPTableTable] = None
        self._security_table: Optional[IPTableTable] = None

    def get_table(self, table_name: str = FILTER_TABLE_NAME) -> Optional[Node]:
        return self.get_child_by_name(table_name)

    def get_chain(self, chain_name: str, table_name: str = FILTER_TABLE_NAME) -> Optional[Node]:
        tbl = self.get_child_by_name(table_name)
        if not tbl:
            return None
        return tbl.get_child_by_name(chain_name)

    def _create_table_if_not_exists(self, table_name: str) -> None:
        table_name = table_name.strip()
        table_identity = '*%s' % table_name
        table = self.get_child_by_identity(table_identity)
        if not table:
            table = IPTableTable()
            table.identity = table_identity
            table.name = table_name
            table.parent = self
            self.add_child(table)
        self._current_table = table

        if table_name == self.NAT_TABLE_NAME:
            self._nat_table = table
        elif table_name == self.FILTER_TABLE_NAME:
            self._filter_table = table
        elif table_name == self.MANGLE_TABLE_NAME:
            self._mangle_table = table
        elif table_name == self.SECURITY_TABLE_NAME:
            self._security_table = table
        elif table_name == self.RAW_TABLE_NAME:
            self._raw_table = table
        else:
            assert 0, 'unknown table name: %s' % table_name

    def _parse_table_action(self, tokens) -> None:
        table_name = tokens[1]
        self._create_table_if_not_exists(table_name)

    def _parse_commit_action(self, tokens) -> None:
        self._current_table = None

    def _create_chain_if_not_exists(self, chain_name: str, counter_str: Optional[str] = None) -> IPTableChain:
        chain = self._current_table.get_child_by_name(chain_name)
        if not chain:
            chain = IPTableChain()
            chain.parent = self._current_table
            chain.name = chain_name
            chain.identity = chain_name
            if not counter_str:
                counter_str = ':%s - [0:0]' % chain_name
            chain.counter_str = counter_str
            self._current_table.add_child(chain)
        return chain

    def _parse_counter_action(self, tokens) -> None:
        chain_name = tokens[1]
        prefix = ':%s' % chain_name
        lst = [prefix]
        lst.extend(tokens[2:])
        counter_str = ' '.join(lst)
        self._create_chain_if_not_exists(chain_name, counter_str)

    def _add_rule(self, chain_name: str, rule_identity: str, order: int = 0) -> None:
        chain = self._create_chain_if_not_exists(chain_name)
        rule = IPTableRule()
        rule_identity = self._normalize_rule(rule_identity)
        rule.name = rule_identity
        rule.identity = rule_identity
        rule.parent = chain
        rule.order = order
        chain.add_child(rule)

    def _parse_rule_action(self, tokens) -> None:
        chain_name = tokens[1]
        self._add_rule(chain_name, ' '.join(tokens))

    def _construct_pyparsing(self) -> None:
        if self._parser:
            return

        table = Literal('*') + Word(alphas)
        table.setParseAction(self._parse_table_action)

        chain_name = Word(printables + '.-_+=%$#')

        counter = Literal(':') + chain_name + restOfLine
        counter.setParseAction(self._parse_counter_action)

        comment = Literal('#') + restOfLine

        rule = Literal('-A') + chain_name + restOfLine
        rule.setParseAction(self._parse_rule_action)

        commit = Literal('COMMIT')
        commit.setParseAction(self._parse_commit_action)

        self._parser = table | counter | comment | rule | commit

    @staticmethod
    def find_target_in_rule(rule) -> Optional[str]:
        if isinstance(rule, IPTableRule):
            rs = str(rule).split()
        else:
            rs = rule.split()

        for i, r in enumerate(rs):
            if r == '-j' and i + 1 < len(rs):
                return rs[i + 1]
        return None

    @staticmethod
    def find_ipset_in_rule(rule) -> Optional[str]:
        if isinstance(rule, IPTableRule):
            rs = str(rule).split()
        else:
            rs = rule.split()

        for i, r in enumerate(rs):
            if r == '--match-set' and i + 1 < len(rs):
                return rs[i + 1]
        return None

    @staticmethod
    def is_target_in_rule(rule, target: str) -> bool:
        ret = IPTables.find_target_in_rule(rule)
        return target == ret

    @staticmethod
    def find_target_chain_name_in_rule(rule) -> Optional[str]:
        target = IPTables.find_target_in_rule(rule)
        if target and target.isupper():
            target = None
        return target

    def list_used_ipset_name(self) -> List[str]:
        sets_name = []
        rules = self.list_reference_ipset_rules(None)
        for r in rules:
            set_name = self.find_ipset_in_rule(r)
            if set_name and set_name not in sets_name:
                sets_name.append(set_name)
        return sets_name

    def list_reference_ipset_rules(self, ipsets: Optional[List[str]] = None) -> List[Node]:
        def walker(rule, data) -> bool:
            if not isinstance(rule, IPTableRule):
                return False
            ipset = self.find_ipset_in_rule(rule)
            if ipsets is not None:
                return ipset in ipsets
            return ipset is not None
        return self.walk_all(walker, None)

    def _reset(self) -> None:
        self.children = []
        self._current_table = None
        self._nat_table = None
        self._filter_table = None
        self._mangle_table = None

    def _from_iptables_save(self, txt: str) -> None:
        self._reset()
        self._construct_pyparsing()
        for l in txt.split('\n'):
            l = l.strip('\n').strip('\r').strip('\t').strip()
            if not l:
                continue
            self._parser.parseString(l)

    def iptables_save(self) -> None:
        out = shell.call('/sbin/iptables-save')
        self._from_iptables_save(out)

    def __str__(self) -> str:
        lst = []
        for table in self.children:
            lst.append(str(table))
        lst.append('')
        return '\n'.join(lst)

    def _cleanup_empty_chain(self) -> None:
        def _is_chain_not_targeted(chain, table) -> bool:
            for chain2 in table.children:
                if chain2.children:
                    for rule1 in chain2.children:
                        if IPTables.is_target_in_rule(rule1, chain.name):
                            return False
            return True

        def _clean_chain_having_no_rules() -> List[str]:
            chains_to_delete = []
            for t in self.children:
                for c in t.children:
                    if not c.children and _is_chain_not_targeted(c, t):
                        chains_to_delete.append(c)

            empty_chain_names = []
            for c in chains_to_delete:
                if c.name in ['INPUT', 'FORWARD', 'OUTPUT', 'PREROUTING', 'POSTROUTING']:
                    continue
                empty_chain_names.append(c.name)
                c.delete()
            return empty_chain_names

        def _clean_rule_having_stale_target_chain() -> List[Node]:
            alive_chain_names = []
            for t in self.children:
                for c in t.children:
                    alive_chain_names.append(c.name)

            def walker(rule, data) -> bool:
                if not isinstance(rule, IPTableRule):
                    return False
                chain_name = self.find_target_chain_name_in_rule(rule.identity)
                return chain_name and chain_name not in alive_chain_names
            return self.walk_all(walker, None)

        empty_chain_names = _clean_chain_having_no_rules()
        logger.debug('removed empty chains:%s' % empty_chain_names)
        rules_to_delete = _clean_rule_having_stale_target_chain()
        for r in rules_to_delete:
            logger.debug('delete rule[%s] which has defunct target' % str(r))
            r.delete()

    def _sort_chains(self, sys_chain_names: List[str], chains: List, sort_func: Callable) -> List:
        all_chains = []
        user_chains = []
        for chain in chains:
            if chain.name in sys_chain_names:
                all_chains.append(chain)
            else:
                user_chains.append(chain)
        user_chains = sorted(user_chains, key=cmp_to_key(sort_func))
        all_chains.extend(user_chains)
        return all_chains

    def _sort_chain_in_filter_table(self, sort_func: Callable) -> None:
        if self._filter_table is None:
            return
        self._filter_table.children = self._sort_chains(
            ['INPUT', 'FORWARD', 'OUTPUT'], self._filter_table.children, sort_func
        )

    def _sort_chain_in_nat_table(self, sort_func: Callable) -> None:
        if self._nat_table is None:
            return
        self._nat_table.children = self._sort_chains(
            ['PREROUTING', 'POSTROUTING', 'OUTPUT'], self._nat_table.children, sort_func
        )

    def _sort_chain_in_mangle_table(self, sort_func: Callable) -> None:
        if self._mangle_table is None:
            return
        self._mangle_table.children = self._sort_chains(
            ['PREROUTING', 'INPUT', 'FORWARD', 'OUTPUT', 'POSTROUTING'],
            self._mangle_table.children, sort_func
        )

    def cleanup_unused_chain(self, is_cleanup: Callable, table_name: str = FILTER_TABLE_NAME, data: Any = None) -> None:
        table = self.get_child_by_name(table_name)
        if not table:
            return

        sys_chain_names = ['INPUT', 'FORWARD', 'OUTPUT', 'PREROUTING', 'POSTROUTING']
        to_del = []
        for chain in table.children:
            if chain.name in sys_chain_names:
                continue
            if is_cleanup(chain, data):
                to_del.append(chain.name)

        for cname in to_del:
            table.delete_child_by_name(cname)

    def _to_iptables_string(
        self,
        marshall_func: Optional[Callable] = None,
        sort_nat_func: Optional[Callable] = None,
        sort_filter_func: Optional[Callable] = None,
        sort_mangle_func: Optional[Callable] = None
    ) -> str:
        self._cleanup_empty_chain()

        if sort_filter_func:
            self._sort_chain_in_filter_table(sort_filter_func)
        if sort_mangle_func:
            self._sort_chain_in_mangle_table(sort_mangle_func)
        if sort_nat_func:
            self._sort_chain_in_nat_table(sort_nat_func)

        def make_reject_rule_last(r1, r2) -> int:
            if self.is_target_in_rule(r1, 'REJECT'):
                return 1
            if self.is_target_in_rule(r2, 'REJECT'):
                return -1
            return 0

        if self._filter_table:
            for c in self._filter_table.children:
                c.children = sorted(c.children, key=cmp_to_key(make_reject_rule_last))

        content = str(self)
        if marshall_func:
            content = marshall_func(content)
        return content

    def iptable_restore(
        self,
        marshall_func: Optional[Callable] = None,
        sort_nat_func: Optional[Callable] = None,
        sort_filter_func: Optional[Callable] = None,
        sort_mangle_func: Optional[Callable] = None
    ) -> None:
        content = self._to_iptables_string(marshall_func, sort_nat_func, sort_filter_func, sort_mangle_func)
        f = linux.write_to_temp_file(content)
        try:
            shell.call("%s < %s" % (get_iptables_cmd("restore"), f))
        except Exception as e:
            res = shell.call('lsof /run/xtables.lock')
            err = '''Failed to apply iptables rules:
shell error description:
%s
result of lsof /run/xtables.lock
%s
iptable rules:
%s
''' % (str(e), str(res), content)
            raise IPTablesError(err)
        finally:
            os.remove(f)

    @staticmethod
    def from_iptables_save() -> 'IPTables':
        ipt = IPTables()
        ipt.iptables_save()
        return ipt

    def _normalize_rule(self, rule: str) -> str:
        return ' '.join(rule.strip().split())

    def add_rule(self, rule: str, table_name: str = FILTER_TABLE_NAME, order: int = 0) -> None:
        if table_name not in [self.FILTER_TABLE_NAME, self.NAT_TABLE_NAME, self.MANGLE_TABLE_NAME]:
            raise IPTablesError('unknown table name[%s]' % table_name)

        self._create_table_if_not_exists(table_name)
        chain_name = Word(printables + '-_+=%$#')
        rule_p = Literal('-A') + chain_name + restOfLine
        res = rule_p.parseString(rule)
        self._add_rule(res[1], rule, order)

    def remove_rule(self, rule_str: str) -> None:
        rule_str = self._normalize_rule(rule_str)
        self.delete_all_by_identity(rule_str)

    def search_all_rule(self, rule_str: str) -> List[Node]:
        rule_str = self._normalize_rule(rule_str)
        return self.search_all_by_identity(rule_str)

    def search_rule(self, rule_str: str) -> Optional[Node]:
        rule_str = self._normalize_rule(rule_str)
        return self.search_by_identity(rule_str)

    def delete_chain(self, chain_name: str, table_name: str = FILTER_TABLE_NAME) -> None:
        table = self.get_child_by_name(table_name)
        if not table:
            return
        table.delete_child_by_name(chain_name)


def from_iptables_save() -> IPTables:
    """Create IPTables instance from current iptables-save output."""
    return IPTables.from_iptables_save()


def insert_single_rule_to_filter_table(rule: str) -> None:
    """Insert a single rule to filter table if not exists."""
    if not rule.startswith('-A '):
        raise IPTablesError("rule must start with '-A '")
    if any(ch in rule for ch in ["'", '"', ';', '|', '&', '`', '$', '\n', '\r']):
        raise IPTablesError('unsafe characters in rule')
    insert_rule = rule.replace('-A ', '-I ', 1)
    shell.call("/sbin/iptables-save | grep -F -- '{0}' > /dev/null || iptables {1}".format(rule, insert_rule))
