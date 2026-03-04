from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NamespaceInfo:
    """Network namespace metadata."""
    name: str
    id: int = 0
    interfaces: list[str] = field(default_factory=list)


@dataclass
class VethPair:
    """Virtual Ethernet pair connecting host and namespace."""
    host_end: str
    ns_end: str
    namespace: str
    host_ip: str = ""
    ns_ip: str = ""
