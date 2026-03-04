# ZStackLib Functional Domain Refactoring Summary

## Overview

This refactoring reorganizes zstacklib code by hardware management functional domains, improving maintainability and code discoverability.

**Branch:** `feature/functional-domain-refactor`  
**Commits:** 46  
**Files:** 288 Python files  
**Lines:** ~43,000  
**Tests:** 127 passed ✅

## Module Structure

```text
zstacklib/
├── hardware/           # Hardware device management
│   ├── pci/            # PCI device operations
│   ├── gpu/            # GPU passthrough
│   ├── sriov/          # SR-IOV networking
│   └── usb/            # USB device attach/detach
│
├── storage/            # Storage management
│   ├── lvm/            # LVM operations
│   ├── iscsi/          # iSCSI target/initiator
│   ├── multipath/      # Multipath I/O
│   ├── drbd/           # DRBD replication
│   ├── ceph/           # Ceph RBD
│   ├── qcow2/          # QCOW2 image operations
│   ├── nfs/            # NFS mounts
│   ├── nbd/            # Network Block Device
│   ├── sanlock/        # SANLock distributed locks
│   └── lock/           # Storage locking primitives
│
├── network/            # Network management
│   ├── firewall/       # iptables/nftables
│   ├── ip/             # IP address management
│   ├── ovs/            # Open vSwitch
│   ├── bridge/         # Linux bridges
│   ├── namespace/      # Network namespaces
│   └── remote/         # SSH/SCP operations
│
├── virtualization/     # VM management
│   ├── qemu/           # QEMU operations
│   ├── qga/            # QEMU Guest Agent
│   ├── ft/             # COLO fault tolerance
│   ├── libvirt/        # Libvirt connection
│   └── vm/             # VM lifecycle operations
│
├── system/             # System utilities
│   ├── lock/           # File/process locking
│   ├── thread/         # Threading utilities
│   ├── defer/          # Go-style defer
│   ├── shell/          # Shell command execution
│   ├── logging/        # Logging configuration
│   ├── process/        # Process management
│   ├── filesystem/     # File operations
│   └── linux/          # Linux distro/arch detection
│
├── config/             # Configuration management
│   └── loader.py       # YAML/JSON config loading
│
└── utils/              # Legacy utilities (to migrate)
```

## Module Design Pattern

Each module follows a consistent structure:

```text
module/
├── __init__.py       # Public exports
├── exceptions.py     # Module-specific exceptions
├── models.py         # Dataclass models
└── operations.py     # Core operations
```

### Design Rules

1. **Python 3.10+ syntax**: `@dataclass`, `str | None`, `list[str]`
2. **No redundant comments**: Code is self-documenting
3. **Exception hierarchy**: All exceptions inherit from module base
4. **Lazy imports**: `__init__.py` uses lazy loading for performance

## Key Modules

### hardware/usb
```python
from zstacklib.hardware.usb import list_usb_devices, attach_usb, detach_usb
devices = list_usb_devices()
attach_usb(vm_name, vendor_id="1234", product_id="5678")
```

### storage/lock
```python
from zstacklib.storage.lock import StorageLock, acquire_lock, release_lock
with StorageLock("/path/to/resource"):
    # exclusive access
```

### virtualization/vm
```python
from zstacklib.virtualization.vm import get_vm_info, start_vm, stop_vm
info = get_vm_info("vm-uuid")
start_vm("vm-uuid")
stop_vm("vm-uuid", force=True)
```

### config
```python
from zstacklib.config import load_config, ConfigError
config = load_config("/etc/zstack/agent.yaml")
```

### system/linux
```python
from zstacklib.system.linux import get_distro, get_arch, retry
distro = get_distro()  # DistroInfo(name='centos', version='7.9')
arch = get_arch()      # 'x86_64'

@retry(times=3, delay=1.0)
def flaky_operation():
    pass
```

## Next Steps

### Phase 2: Migration
1. Update existing code to import from new modules
2. Add deprecation warnings to old locations
3. Create migration guide for downstream users

### Phase 3: Cleanup
1. Remove `utils/` after full migration
2. Add comprehensive type hints
3. Increase test coverage to 80%+

## Commit History

Latest commits:
- `feat[virtualization]: add vm lifecycle operations`
- `feat[virtualization]: add libvirt connection module`
- `feat[hardware]: add usb management module`
- `feat[storage]: add storage lock module`
- `feat[config]: add config loading module`
- `feat[system]: add shell, logging, process, filesystem, linux modules`
- `feat[network]: add bridge, namespace, remote modules`
