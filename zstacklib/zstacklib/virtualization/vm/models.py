from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VmState(Enum):
    NOSTATE = 0
    RUNNING = 1
    BLOCKED = 2
    PAUSED = 3
    SHUTDOWN = 4
    SHUTOFF = 5
    CRASHED = 6
    PMSUSPENDED = 7
    
    @classmethod
    def from_libvirt(cls, state: int) -> "VmState":
        try:
            return cls(state)
        except ValueError:
            return cls.NOSTATE
    
    def is_running(self) -> bool:
        return self in (VmState.RUNNING, VmState.BLOCKED)
    
    def is_stopped(self) -> bool:
        return self in (VmState.SHUTDOWN, VmState.SHUTOFF, VmState.CRASHED)


@dataclass
class VmDisk:
    device: str
    source_path: str
    target_dev: str
    bus: str = "virtio"
    driver_type: str = "qcow2"
    cache: str = "none"
    readonly: bool = False
    boot_order: int | None = None


@dataclass
class VmNic:
    mac_address: str
    source_bridge: str = ""
    source_network: str = ""
    model: str = "virtio"
    target_dev: str = ""
    vlan_id: int | None = None


@dataclass
class VmInfo:
    uuid: str
    name: str
    state: VmState
    vcpus: int = 0
    memory_kb: int = 0
    max_memory_kb: int = 0
    cpu_time_ns: int = 0
    autostart: bool = False
    persistent: bool = False
    disks: list[VmDisk] = field(default_factory=list)
    nics: list[VmNic] = field(default_factory=list)
    xml: str = ""
    pid: int | None = None
    
    @property
    def memory_mb(self) -> int:
        return self.memory_kb // 1024
    
    @property
    def is_running(self) -> bool:
        return self.state.is_running()


@dataclass
class VmCreateSpec:
    name: str
    uuid: str
    vcpus: int
    memory_mb: int
    disks: list[VmDisk] = field(default_factory=list)
    nics: list[VmNic] = field(default_factory=list)
    boot_order: list[str] = field(default_factory=lambda: ["hd"])
    machine_type: str = "pc"
    arch: str = "x86_64"
    emulator: str = "/usr/libexec/qemu-kvm"
