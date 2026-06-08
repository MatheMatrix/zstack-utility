"""Network firewall module for iptables, ip6tables, ebtables, and ipset management.

This module provides clean interfaces for Linux firewall rule management:
- iptables: IPv4 firewall rules
- ip6tables: IPv6 firewall rules
- ebtables: Ethernet bridge filtering
- ipset: IP set management for efficient rule matching
"""

from zstacklib.network.firewall.exceptions import IPTablesError, IPSetError

from zstacklib.network.firewall.node import Node

from zstacklib.network.firewall.iptables import (
    IPTables,
    IPTableTable,
    IPTableChain,
    IPTableRule,
    get_iptables_cmd,
    from_iptables_save,
    insert_single_rule_to_filter_table,
)

from zstacklib.network.firewall.ip6tables import (
    IP6Tables,
    get_ip6tables_cmd,
    from_ip6tables_save,
)

from zstacklib.network.firewall.ebtables import get_ebtables_cmd

from zstacklib.network.firewall.ipset import (
    IPSet,
    IPSetManager,
    from_ipset_save,
)

__all__ = [
    # Exceptions
    'IPTablesError',
    'IPSetError',
    # Base
    'Node',
    # IPTables
    'IPTables',
    'IPTableTable',
    'IPTableChain',
    'IPTableRule',
    'get_iptables_cmd',
    'from_iptables_save',
    'insert_single_rule_to_filter_table',
    # IP6Tables
    'IP6Tables',
    'get_ip6tables_cmd',
    'from_ip6tables_save',
    # Ebtables
    'get_ebtables_cmd',
    # IPSet
    'IPSet',
    'IPSetManager',
    'from_ipset_save',
]
