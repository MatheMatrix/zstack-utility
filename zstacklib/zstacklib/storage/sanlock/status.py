# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from string import whitespace

from zstacklib.storage.sanlock.exceptions import SanlockParseError

LOG = logging.getLogger(__name__)


@dataclass
class HostStatus:
    """Hoststatus."""
    host_id: int
    timestamp: int
    io_timeout: int
    last_check: int
    last_live: int

    @classmethod
    def from_record(cls, record: str) -> 'HostStatus':
        """From record."""
        lines = record.strip().splitlines()
        parts = lines[0].split()
        if len(parts) < 3 or parts[1] != 'timestamp':
            raise SanlockParseError(f"Unexpected sanlock host status: {record}")

        host_id = int(parts[0])
        timestamp = int(parts[2])

        io_timeout: int | None = None
        last_check: int | None = None
        last_live: int | None = None

        for line in lines[1:]:
            try:
                key, value = line.strip().split('=', 1)
                if key == 'io_timeout':
                    io_timeout = int(value)
                elif key == 'last_check':
                    last_check = int(value)
                elif key == 'last_live':
                    last_live = int(value)
            except ValueError:
                LOG.warning(f"Unexpected sanlock status line: {line}")

        if io_timeout is None or last_check is None or last_live is None:
            raise SanlockParseError(f"Incomplete sanlock host status: {record}")

        return cls(
            host_id=host_id,
            timestamp=timestamp,
            io_timeout=io_timeout,
            last_check=last_check,
            last_live=last_live,
        )

    def is_timed_out(self) -> bool:
        """Check is timed out."""
        return (
            self.timestamp == 0 or
            self.last_check - self.last_live > 10 * self.io_timeout
        )

    def is_alive(self) -> bool:
        """Check is alive."""
        return (
            self.timestamp != 0 and
            self.last_check - self.last_live < 2 * self.io_timeout
        )


class HostStatusParser:
    """Hoststatusparser."""
    def __init__(self, status: str) -> None:
        """Init."""
        self._status = status

    def get_host_status(self, host_id: int) -> HostStatus | None:
        """Get host status."""
        pattern = rf"^{host_id}\b"
        match = re.search(pattern, self._status, re.M)
        if not match:
            return None

        substr = self._status[match.end():]
        next_match = re.search(r"^\d+\b", substr, re.M)
        remainder = substr if not next_match else substr[:next_match.start()]
        return HostStatus.from_record(str(host_id) + remainder)

    def is_timed_out(self, host_id: int) -> bool | None:
        """Check is timed out."""
        status = self.get_host_status(host_id)
        if status is None:
            return None
        return status.is_timed_out()

    def is_alive(self, host_id: int) -> bool | None:
        """Check is alive."""
        status = self.get_host_status(host_id)
        if status is None:
            return None
        return status.is_alive()


@dataclass
class ClientStatus:
    """Clientstatus."""
    lockspace: str
    is_adding: bool
    renewal_last_result: int
    renewal_last_attempt: int
    renewal_last_success: int

    @classmethod
    def from_lines(cls, lines: list[str]) -> 'ClientStatus':
        """From lines."""
        lockspace = lines[0].split()[1]
        is_adding = ':0 ADD' in lines[0]

        renewal_last_result = 0
        renewal_last_attempt = 0
        renewal_last_success = 0

        for line in lines[1:]:
            try:
                key, value = line.strip().split('=', 1)
                if key == 'renewal_last_result':
                    renewal_last_result = int(value)
                elif key == 'renewal_last_attempt':
                    renewal_last_attempt = int(value)
                elif key == 'renewal_last_success':
                    renewal_last_success = int(value)
            except ValueError:
                LOG.warning(f"Unexpected sanlock client status: {line}")

        return cls(
            lockspace=lockspace,
            is_adding=is_adding,
            renewal_last_result=renewal_last_result,
            renewal_last_attempt=renewal_last_attempt,
            renewal_last_success=renewal_last_success,
        )


class ClientStatusParser:
    """Clientstatusparser."""
    def __init__(self, status: str) -> None:
        """Init."""
        self._status = status
        self._records: list[ClientStatus] | None = None

    def get_all_lockspaces(self) -> list[ClientStatus]:
        """Get all lockspaces."""
        if self._records is None:
            self._records = self._parse_records()
        return self._records

    def get_lockspace(self, needle: str) -> ClientStatus | None:
        """Get lockspace."""
        for record in self.get_all_lockspaces():
            if needle in record.lockspace:
                return record
        return None

    def _parse_records(self) -> list[ClientStatus]:
        """Parse records."""
        records: list[ClientStatus] = []
        current_lines: list[str] = []

        for line in self._status.splitlines():
            if not line:
                continue

            if line[0] in whitespace and current_lines:
                current_lines.append(line)
                continue

            if current_lines:
                records.append(ClientStatus.from_lines(current_lines))
                current_lines = []

            if line.startswith("s "):
                current_lines.append(line)

        if current_lines:
            records.append(ClientStatus.from_lines(current_lines))

        return records
