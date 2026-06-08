from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConnectionType(Enum):
    QEMU_SYSTEM = "qemu:///system"
    QEMU_SESSION = "qemu:///session"
    LXC = "lxc:///"
    XEN = "xen:///"
    TEST = "test:///default"


@dataclass
class LibvirtConfig:
    uri: str = "qemu:///system"
    readonly: bool = False
    auth_callback: object | None = None
    
    @classmethod
    def qemu_system(cls) -> "LibvirtConfig":
        return cls(uri=ConnectionType.QEMU_SYSTEM.value)
    
    @classmethod
    def qemu_session(cls) -> "LibvirtConfig":
        return cls(uri=ConnectionType.QEMU_SESSION.value)


@dataclass
class HostInfo:
    hostname: str
    max_vcpus: int
    memory_kb: int
    cpus: int
    mhz: int
    numa_nodes: int
    cpu_sockets: int
    cpu_cores: int
    cpu_threads: int
    cpu_model: str = ""
    libvirt_version: str = ""
    qemu_version: str = ""


@dataclass
class StoragePoolInfo:
    name: str
    uuid: str
    state: int
    capacity: int
    allocation: int
    available: int
    autostart: bool = False
    persistent: bool = False
