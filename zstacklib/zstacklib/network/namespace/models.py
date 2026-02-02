from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NamespaceInfo:
    name: str
    id: int = 0
    interfaces: list[str] = field(default_factory=list)


@dataclass
class VethPair:
    host_end: str
    ns_end: str
    namespace: str
    host_ip: str = ""
    ns_ip: str = ""
