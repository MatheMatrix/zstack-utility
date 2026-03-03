from __future__ import annotations

import os
import subprocess
from typing import Callable

from .exceptions import BridgeError, BridgeNotFoundError, InterfaceOccupiedError
from .models import BridgeInfo, BridgePort


def is_bridge(name: str) -> bool:
    """Check is bridge."""
    return os.path.exists(f"/sys/class/net/{name}/bridge")


def is_bridge_slave(interface: str) -> bool:
    """Check is bridge slave."""
    return os.path.exists(f"/sys/class/net/{interface}/brport")


def bridge_exists(name: str) -> bool:
    """Bridge exists."""
    return is_bridge(name)


def interface_exists(name: str) -> bool:
    """Interface exists."""
    return os.path.exists(f"/sys/class/net/{name}")


def get_bridge_interfaces(bridge: str) -> list[str]:
    """Get bridge interfaces."""
    result = subprocess.run(
        ["brctl", "show", bridge],
        capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return []
    
    interfaces = []
    lines = result.stdout.strip().split('\n')
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 4:
            interfaces.append(parts[3])
        elif len(parts) == 1 and parts[0]:
            interfaces.append(parts[0])
    return [i.strip() for i in interfaces if i.strip()]


def is_interface_on_bridge(bridge: str, interface: str) -> bool:
    """Check is interface on bridge."""
    return interface in get_bridge_interfaces(bridge)


def get_interface_master(interface: str) -> str | None:
    """Get interface master."""
    uevent_path = f"/sys/class/net/{interface}/master/uevent"
    if not os.path.exists(uevent_path):
        return None
    
    try:
        with open(uevent_path, 'r') as f:
            for line in f:
                if line.startswith('INTERFACE='):
                    return line.split('=')[1].strip()
    except (OSError, IOError):
        pass
    return None


def create_bridge(
    name: str,
    interface: str | None = None,
    stp: bool = False,
    forward_delay: int = 0,
    move_route: bool = True
) -> None:
    """Create bridge."""
    if interface and not interface_exists(interface):
        raise BridgeError(f"Interface '{interface}' does not exist")
    
    if interface and is_bridge(interface):
        raise BridgeError(f"Interface '{interface}' is already a bridge")
    
    if interface:
        master = get_interface_master(interface)
        if master and master != name:
            raise InterfaceOccupiedError(interface, master)
    
    if not is_bridge(name):
        result = subprocess.run(["brctl", "addbr", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise BridgeError(f"Failed to create bridge '{name}': {result.stderr}")
    
    stp_setting = "on" if stp else "off"
    subprocess.run(["brctl", "stp", name, stp_setting], check=False)
    subprocess.run(["brctl", "setfd", name, str(forward_delay)], check=False)
    subprocess.run(["ip", "link", "set", name, "up"], check=False)
    
    if interface and not is_interface_on_bridge(name, interface):
        result = subprocess.run(
            ["brctl", "addif", name, interface],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise BridgeError(f"Failed to add interface '{interface}' to bridge '{name}': {result.stderr}")


def delete_bridge(name: str) -> None:
    """Delete bridge."""
    if not is_bridge(name):
        return
    
    for interface in get_bridge_interfaces(name):
        if interface:
            subprocess.run(["brctl", "delif", name, interface], check=False)
    
    subprocess.run(["ip", "link", "set", name, "down"], check=False)
    subprocess.run(["brctl", "delbr", name], check=False)


def add_interface(bridge: str, interface: str) -> None:
    """Add interface."""
    if not is_bridge(bridge):
        raise BridgeNotFoundError(bridge)
    
    if not interface_exists(interface):
        raise BridgeError(f"Interface '{interface}' does not exist")
    
    master = get_interface_master(interface)
    if master and master != bridge:
        raise InterfaceOccupiedError(interface, master)
    
    if is_interface_on_bridge(bridge, interface):
        return
    
    result = subprocess.run(
        ["brctl", "addif", bridge, interface],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BridgeError(f"Failed to add interface: {result.stderr}")


def remove_interface(bridge: str, interface: str) -> None:
    """Remove interface."""
    if not is_bridge(bridge):
        raise BridgeNotFoundError(bridge)
    
    if not is_interface_on_bridge(bridge, interface):
        return
    
    result = subprocess.run(
        ["brctl", "delif", bridge, interface],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BridgeError(f"Failed to remove interface: {result.stderr}")


def get_bridge_info(name: str) -> BridgeInfo | None:
    """Get bridge info."""
    if not is_bridge(name):
        return None
    
    interfaces = get_bridge_interfaces(name)
    
    stp_enabled = False
    stp_path = f"/sys/class/net/{name}/bridge/stp_state"
    if os.path.exists(stp_path):
        try:
            with open(stp_path, 'r') as f:
                stp_enabled = f.read().strip() == '1'
        except (OSError, IOError):
            pass
    
    forward_delay = 0
    fd_path = f"/sys/class/net/{name}/bridge/forward_delay"
    if os.path.exists(fd_path):
        try:
            with open(fd_path, 'r') as f:
                forward_delay = int(f.read().strip()) // 100
        except (OSError, IOError, ValueError):
            pass
    
    mac_address = ""
    mac_path = f"/sys/class/net/{name}/address"
    if os.path.exists(mac_path):
        try:
            with open(mac_path, 'r') as f:
                mac_address = f.read().strip()
        except (OSError, IOError):
            pass
    
    mtu = 1500
    mtu_path = f"/sys/class/net/{name}/mtu"
    if os.path.exists(mtu_path):
        try:
            with open(mtu_path, 'r') as f:
                mtu = int(f.read().strip())
        except (OSError, IOError, ValueError):
            pass
    
    up = False
    operstate_path = f"/sys/class/net/{name}/operstate"
    if os.path.exists(operstate_path):
        try:
            with open(operstate_path, 'r') as f:
                up = f.read().strip() == 'up'
        except (OSError, IOError):
            pass
    
    return BridgeInfo(
        name=name,
        interfaces=interfaces,
        stp_enabled=stp_enabled,
        forward_delay=forward_delay,
        mac_address=mac_address,
        mtu=mtu,
        up=up
    )


def list_bridges() -> list[str]:
    """List bridges."""
    bridges = []
    net_dir = "/sys/class/net"
    if os.path.isdir(net_dir):
        for name in os.listdir(net_dir):
            if is_bridge(name):
                bridges.append(name)
    return bridges
