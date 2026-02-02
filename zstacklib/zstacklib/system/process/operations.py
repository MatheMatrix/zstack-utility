from __future__ import annotations

import os
import signal
from pathlib import Path

from .exceptions import PidFileError, ProcessNotFoundError
from .models import ProcessInfo, ProcessState


class PidFile:

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __enter__(self) -> PidFile:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def write(self, pid: int | None = None) -> None:
        pid = pid or os.getpid()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(str(pid))

    def read(self) -> int | None:
        if not self.path.exists():
            return None
        try:
            return int(self.path.read_text().strip())
        except (ValueError, OSError):
            return None

    def remove(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def is_running(self) -> bool:
        pid = self.read()
        if pid is None:
            return False
        return is_process_running(pid)


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_process(pid: int, sig: int = signal.SIGTERM) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except OSError:
        return False


def get_process_info(pid: int) -> ProcessInfo | None:
    proc_path = Path(f"/proc/{pid}")
    if not proc_path.exists():
        return None

    try:
        comm = (proc_path / "comm").read_text().strip()
        cmdline = (proc_path / "cmdline").read_text().replace("\x00", " ").strip()

        status_content = (proc_path / "status").read_text()
        status_dict = {}
        for line in status_content.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                status_dict[key.strip()] = value.strip()

        state_char = status_dict.get("State", "?")[0]
        state_map = {
            "R": ProcessState.RUNNING,
            "S": ProcessState.SLEEPING,
            "T": ProcessState.STOPPED,
            "Z": ProcessState.ZOMBIE,
        }
        state = state_map.get(state_char, ProcessState.UNKNOWN)

        ppid = int(status_dict.get("PPid", "0"))
        uid = int(status_dict.get("Uid", "0").split()[0])
        memory_rss_kb = int(status_dict.get("VmRSS", "0 kB").split()[0])

        return ProcessInfo(
            pid=pid,
            name=comm,
            cmdline=cmdline,
            state=state,
            ppid=ppid,
            uid=uid,
            memory_rss_kb=memory_rss_kb,
        )
    except Exception:
        return None


def wait_for_process(pid: int, timeout: float = 30.0) -> bool:
    import time
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not is_process_running(pid):
            return True
        time.sleep(0.1)
    return False
