from __future__ import annotations

import json
import logging

from zstacklib.virtualization.ft.qmp import execute_qmp_command, QMPError

logger = logging.getLogger(__name__)


def stop_nbd_server(vm_uuid: str) -> None:
    execute_qmp_command(vm_uuid, '{"execute": "nbd-server-stop"}')


def colo_lost_heartbeat(vm_uuid: str) -> None:
    execute_qmp_command(vm_uuid, '{"execute": "x-colo-lost-heartbeat"}')


def _cleanup_qom_by_prefix(
    vm_uuid: str,
    prefixes: list[str],
    is_object: bool = True
) -> None:
    qom_path = "/objects" if is_object else "/chardevs"
    cmd = f'{{"execute": "qom-list", "arguments": {{ "path": "{qom_path}" }}}}'
    
    _, output, err = execute_qmp_command(vm_uuid, cmd)
    if err:
        raise QMPError(f"Failed to query QOM at {qom_path}")
    
    qom_list = json.loads(output).get('return', [])
    
    for entry in qom_list:
        name = entry.get('name', '')
        if any(prefix in name for prefix in prefixes):
            if is_object:
                del_cmd = f'{{"execute": "object-del", "arguments": {{"id": "{name}"}}}}'
            else:
                del_cmd = f'{{"execute": "chardev-remove", "arguments": {{"id": "{name}"}}}}'
            execute_qmp_command(vm_uuid, del_cmd)


def cleanup_primary_vm_qom(vm_uuid: str) -> None:
    prefixes = ['comp-', 'fm-', 'primary-out-redirect-', 'primary-in-redirect-']
    _cleanup_qom_by_prefix(vm_uuid, prefixes)


def cleanup_secondary_vm_qom(vm_uuid: str) -> None:
    _cleanup_qom_by_prefix(vm_uuid, ['fr-secondary-', 'fr-secondary-'])
    _cleanup_qom_by_prefix(vm_uuid, ['red-secondary-', 'red-mirror-'], is_object=False)


def update_quorum_children(vm_uuid: str) -> None:
    _, output, err = execute_qmp_command(vm_uuid, '{"execute": "query-block"}')
    if err:
        raise QMPError("Failed to query QEMU block devices")
    
    blocks = json.loads(output).get('return', [])
    
    for blk in blocks:
        inserted = blk.get('inserted')
        if not inserted:
            continue
        
        blk_file = inserted.get('file', '')
        if not blk_file.startswith('json:'):
            continue
        
        blk_file_obj = json.loads(blk_file[5:])
        children = blk_file_obj.get('children', [])
        if len(children) <= 1:
            continue
        
        device_name = blk['device']
        execute_qmp_command(
            vm_uuid,
            f'{{"execute": "x-blockdev-change", "arguments": {{"parent": "{device_name}", "child": "children.1"}}}}'
        )
        execute_qmp_command(
            vm_uuid,
            f'{{"execute": "human-monitor-command", "arguments": {{"command-line": "drive_del replication{device_name[-1]}"}}}}'
        )


def cleanup_before_colo_primary(vm_uuid: str) -> None:
    update_quorum_children(vm_uuid)
    stop_nbd_server(vm_uuid)
    cleanup_primary_vm_qom(vm_uuid)
    colo_lost_heartbeat(vm_uuid)
    cleanup_secondary_vm_qom(vm_uuid)
