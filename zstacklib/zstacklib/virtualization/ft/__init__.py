"""COLO (COntinuous LOcal) fault tolerance for QEMU VMs.

Provides QMP-based control for COLO replication setup and cleanup.
"""

from zstacklib.virtualization.ft.qmp import execute_qmp_command

from zstacklib.virtualization.ft.colo import (
    stop_nbd_server,
    colo_lost_heartbeat,
    cleanup_primary_vm_qom,
    cleanup_secondary_vm_qom,
    cleanup_before_colo_primary,
    update_quorum_children,
)

__all__ = [
    'execute_qmp_command',
    'stop_nbd_server',
    'colo_lost_heartbeat',
    'cleanup_primary_vm_qom',
    'cleanup_secondary_vm_qom',
    'cleanup_before_colo_primary',
    'update_quorum_children',
]
