"""Firewall-related exceptions."""


class IPTablesError(Exception):
    """iptables operation error."""
    pass


class IPSetError(Exception):
    """ipset operation error."""
    pass
