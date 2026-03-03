from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BridgeInfo:
    """Bridgeinfo."""
    name: str
    interfaces: list[str] = field(default_factory=list)
    stp_enabled: bool = False
    forward_delay: int = 0
    mac_address: str = ""
    mtu: int = 1500
    up: bool = False


@dataclass
class BridgePort:
    """Bridgeport."""
    name: str
    bridge: str
    state: str = ""
    priority: int = 0
    path_cost: int = 0
