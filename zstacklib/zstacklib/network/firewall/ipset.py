"""IPSet management for iptables integration."""

import os
import tempfile
from typing import Optional, List, Dict

from pyparsing import Literal, Word, alphas, alphanums, nums, printables, restOfLine

from zstacklib.utils import shell, linux, log
from zstacklib.network.firewall.exceptions import IPSetError

logger = log.get_logger(__name__)


class IPSet:
    """Represents an ipset with match and nomatch IP entries.
    
    Supports hash:net type by default.
    """
    
    def __init__(self, name: str, set_type: str, ip_version: str):
        self.name = name
        self.ip_version = ip_version
        self.type = set_type
        self.match_ip: List[str] = []
        self.nomatch_ip: List[str] = []

    def set_match_ip(self, ips: Optional[List[str]]) -> None:
        if ips:
            self.match_ip = ips

    def set_nomatch_ip(self, ips: Optional[List[str]]) -> None:
        if ips:
            self.nomatch_ip = ips

    def add_match_ip(self, ip: str) -> None:
        if ip not in self.match_ip:
            self.match_ip.append(ip)

    def add_nomatch_ip(self, ip: str) -> None:
        if ip not in self.nomatch_ip:
            self.nomatch_ip.append(ip)

    def del_match_ip(self, ip: str) -> None:
        if ip in self.match_ip:
            self.match_ip.remove(ip)

    def del_nomatch_ip(self, ip: str) -> None:
        if ip in self.nomatch_ip:
            self.nomatch_ip.remove(ip)

    def clear_match_ip(self) -> None:
        self.match_ip = []

    def clear_nomatch_ip(self) -> None:
        self.nomatch_ip = []

    def transform_cmd(self, is_exist: bool = True) -> str:
        create_cmd = self._create_set_cmd(is_exist)
        flush_cmd = 'flush %s' % self.name
        ip_cmds = '\n'.join(self._add_ip_cmd_list(is_exist))
        return '%s\n%s\n%s\n' % (create_cmd, flush_cmd, ip_cmds)

    def _create_set_cmd(self, is_exist: bool = True) -> str:
        option = '--exist' if is_exist else ''
        return 'create %s %s family %s %s' % (self.name, self.type, self.ip_version, option)

    def _add_ip_cmd_list(self, is_exist: bool = True) -> List[str]:
        option = '--exist' if is_exist else ''
        match_cmds = ['add %s %s %s' % (self.name, ip, option) for ip in self.match_ip]
        nomatch_cmds = ['add %s %s %s nomatch' % (self.name, ip, option) for ip in self.nomatch_ip]
        return match_cmds + nomatch_cmds


class IPSetManager:
    """Manager for multiple ipsets with save/restore capabilities."""
    
    # Set types
    LIST_SET = 'list:set'
    HASH_NET_IFACE = 'hash:net,iface'
    HASH_NET_PORT = 'hash:net,port'
    HASH_NET = 'hash:net'
    HASH_IP_PORT_NET = 'hash:ip,port,net'
    HASH_IP_PORT_IP = 'hash:ip,port,ip'
    HASH_IP_PORT = 'hash:ip,port'
    HASH_IP = 'hash:ip'
    BITMAP_PORT = 'bitmap:port'
    BITMAP_IP_MAC = 'bitmap:ip,mac'
    BITMAP_IP = 'bitmap:ip'

    DEFAULT_NAME = 'default-sg'
    DEFAULT_TYPE = HASH_NET
    DEFAULT_IP_VERSION = 'inet'

    def __init__(self, namespace: Optional[str] = None):
        self.namespace = namespace
        self.sets: Dict[str, IPSet] = {}
        self._parser = None

    def create_set(
        self,
        match_ips: Optional[List[str]] = None,
        nomatch_ips: Optional[List[str]] = None,
        name: str = DEFAULT_NAME,
        set_type: str = DEFAULT_TYPE,
        ip_version: str = DEFAULT_IP_VERSION
    ) -> None:
        self.sets[name] = IPSet(name, set_type, ip_version)
        self.sets[name].set_match_ip(match_ips)
        self.sets[name].set_nomatch_ip(nomatch_ips)

    def destroy_set(self, name: str) -> None:
        del self.sets[name]

    def flush_sets(self, name: str) -> None:
        self.sets[name].clear_match_ip()
        self.sets[name].clear_nomatch_ip()

    def reset(self) -> None:
        self.sets.clear()
        self.namespace = None

    def ipset_save(self) -> None:
        o = shell.call('ipset save')
        self._from_ipset_save(o)

    def cleanup_other_ipset(self, validate, used_ipset: Optional[List[str]] = None) -> None:
        if used_ipset:
            used_sets = used_ipset
        else:
            used_sets = list(self.sets.keys())

        logger.debug('start cleanup other ipsets')
        set_list = shell.call("ipset list -n").splitlines()
        to_del_set_list = [x for x in set_list if validate(x) and x not in used_sets]
        self.clean_ipsets(to_del_set_list)

    @staticmethod
    def clean_ipsets(ipset_names: List[str]) -> None:
        destroy_cmds = ['destroy %s' % set_name for set_name in ipset_names]
        tmp = linux.write_to_temp_file('\n'.join(destroy_cmds))
        o = shell.ShellCmd('ipset restore -f %s' % tmp)
        o(False)
        if o.return_code != 0:
            logger.warn('fail to cleanup ipsets, %s' % o.stderr)
        else:
            logger.debug('success cleanup ipsets')
        os.remove(tmp)

    def refresh_my_ipsets(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp()
        with os.fdopen(tmp_fd, 'w') as f:
            for name, ipset in self.sets.items():
                f.write(ipset.transform_cmd())

        execns = ''
        if self.namespace:
            import re as _re
            if not _re.match(r'^[A-Za-z0-9_.-]+$', self.namespace):
                raise IPSetError('invalid namespace: %s' % self.namespace)
            execns = 'ip netns exec %s ' % self.namespace

        o = shell.ShellCmd(execns + 'ipset restore -f %s' % tmp_path)
        o(False)
        os.remove(tmp_path)
        if o.return_code != 0:
            raise IPSetError('ipset restore failed, because %s' % o.stderr)
        logger.debug('success restore ipset')

    def _parse_set_action(self, tokens) -> None:
        set_name = tokens[1]
        set_type = '%s:%s' % (tokens[2], tokens[4])
        ip_version = tokens[6]
        self.create_set(name=set_name, set_type=set_type, ip_version=ip_version)

    def _parse_entry_action(self, tokens) -> None:
        set_name = tokens[1]
        ip = tokens[2]
        if set_name not in self.sets:
            self.create_set(name=set_name)
        self.sets[set_name].add_match_ip(ip)

    def _construct_pyparsing(self) -> None:
        if self._parser:
            return

        set_name = Word(printables)
        set_type = Word(alphas) + Word(':') + Word(alphas + ',')

        sets = Literal('create') + set_name + set_type + Literal('family') + Word(alphanums) + restOfLine
        sets.setParseAction(self._parse_set_action)

        entry = Literal('add') + set_name + Word(nums + './')
        entry.setParseAction(self._parse_entry_action)

        self._parser = sets | entry

    def _from_ipset_save(self, txt: str) -> None:
        self.reset()
        self._construct_pyparsing()
        for l in txt.splitlines():
            l = l.strip()
            if not l:
                continue
            self._parser.parseString(l)


def from_ipset_save() -> IPSetManager:
    """Create IPSetManager from current ipset save output."""
    logger.debug('start load ipset ...')
    ipset = IPSetManager()
    ipset.ipset_save()
    logger.debug('success load ipset ...')
    return ipset
