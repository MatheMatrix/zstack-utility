from __future__ import annotations

import logging

from zstacklib.utils import shell

logger = logging.getLogger(__name__)


class QMPError(Exception):
    pass


def execute_qmp_command(
    domain_id: str,
    command: str,
    error_out: bool = False
) -> tuple[int, str, str]:
    cmd = f"virsh qemu-monitor-command {domain_id} '{command}' --pretty"
    result = shell.run(cmd)
    
    if result.stderr and "cannot acquire state change lock" in result.stderr:
        logger.debug(f"failed to execute qmp command {command}")
        if error_out:
            raise QMPError("command not executed: state change lock timeout")
    
    return result.return_code, result.stdout, result.stderr
