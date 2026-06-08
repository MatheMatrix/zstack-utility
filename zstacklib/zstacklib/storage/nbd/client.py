# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0
# Based on code from Cloudbase Solutions SRL (Apache-2.0)

from __future__ import annotations

import logging
import socket
import struct
from ipaddress import ip_address

from zstacklib.storage.nbd.constants import (
    DEFAULT_NBD_PORT,
    NBD_CLISERV_MAGIC,
    NBD_CMD_DISC,
    NBD_CMD_READ,
    NBD_FLAG_C_FIXED_NEWSTYLE,
    NBD_FLAG_NO_ZEROES,
    NBD_INIT_PASSWD,
    NBD_OPT_EXPORT_NAME,
    NBD_OPTS_MAGIC,
    NBD_REPLY_MAGIC,
    NBD_REQUEST_MAGIC,
)
from zstacklib.storage.nbd.exceptions import (
    NbdConnectionError,
    NbdExportError,
    NbdNegotiationError,
    NbdProtocolError,
    NbdReadError,
)

LOG = logging.getLogger(__name__)


class NbdClient:
    """
    READ-ONLY NBD client. Does NOT support parallel reads.

    Warning: Sequential reads only - parallel reads will cause data corruption.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int = DEFAULT_NBD_PORT,
        unix_socket: str | None = None,
        export_name: str | None = None,
    ) -> None:
        """Init."""
        if host is None and unix_socket is None:
            raise ValueError("Either host or unix_socket must be specified")

        self.host = host
        self.port = port
        self.unix_socket = unix_socket
        self.export_name = export_name
        self.export_size: int | None = None
        self._sock: socket.socket | None = None
        self._client_flags = NBD_FLAG_C_FIXED_NEWSTYLE
        self._handle = b'1'

    def connect(
        self,
        host: str | None = None,
        port: int | None = None,
        unix_socket: str | None = None,
        export_name: str | None = None,
    ) -> None:
        """Connect."""
        _host = host or self.host
        _port = port or self.port
        _unix_socket = unix_socket or self.unix_socket
        _export_name = export_name or self.export_name

        if self._sock is not None:
            self.close()

        sock = self._create_socket(_host, _port, _unix_socket)
        addr = self._get_address(_host, _port, _unix_socket)

        try:
            sock.connect(addr)
        except socket.error as err:
            if err.errno == 106:
                LOG.debug("Socket already connected")
                self._sock = sock
                return
            raise NbdConnectionError(f"Failed to connect to NBD server: {err}") from err

        self._negotiate(sock, name=_export_name)
        self._sock = sock
        self.host = _host
        self.port = _port or DEFAULT_NBD_PORT
        self.unix_socket = _unix_socket
        self.export_name = _export_name

    def _create_socket(
        self,
        host: str | None,
        port: int | None,
        unix_socket: str | None,
    ) -> socket.socket:
        """Create socket."""
        if unix_socket is not None:
            return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        if host is not None:
            try:
                ip_version = ip_address(host).version
            except ValueError:
                ip_version = 4

            inet = socket.AF_INET6 if ip_version == 6 else socket.AF_INET
            return socket.socket(inet, socket.SOCK_STREAM)

        raise ValueError("Either host/port or unix_socket must be specified")

    def _get_address(
        self,
        host: str | None,
        port: int | None,
        unix_socket: str | None,
    ) -> str | tuple[str, int]:
        """Get address."""
        if unix_socket is not None:
            return unix_socket
        if host is not None:
            return (host, port or DEFAULT_NBD_PORT)
        raise ValueError("Either host/port or unix_socket must be specified")

    def _negotiate(self, sock: socket.socket, name: str | None = None) -> None:
        """Negotiate."""
        passwd_size = struct.calcsize('>8s')
        passwd_data = sock.recv(passwd_size)
        if len(passwd_data) < passwd_size:
            raise NbdNegotiationError("Incomplete password received from server")

        passwd = struct.unpack('>8s', passwd_data)
        if passwd[0] != NBD_INIT_PASSWD:
            raise NbdNegotiationError(
                f"Bad NBD password: {passwd[0]!r}. Expected: {NBD_INIT_PASSWD!r}"
            )

        magic_size = struct.calcsize('>Q')
        magic_data = sock.recv(magic_size)
        if len(magic_data) < magic_size:
            raise NbdNegotiationError("Incomplete magic received from server")

        magic = struct.unpack('>Q', magic_data)[0]

        if magic == NBD_CLISERV_MAGIC:
            self._negotiate_old_style(sock)
        else:
            self._negotiate_new_style(sock, name)

    def _negotiate_old_style(self, sock: socket.socket) -> None:
        """Negotiate old style."""
        LOG.info(f"Using old-style negotiation for {self.export_name}")
        info_size = struct.calcsize('>Q128s')
        info_data = sock.recv(info_size)
        if len(info_data) < info_size:
            raise NbdNegotiationError("Incomplete export info received")
        info = struct.unpack('>Q128s', info_data)
        self.export_size = info[0]

    def _negotiate_new_style(self, sock: socket.socket, name: str | None) -> None:
        """Negotiate new style."""
        if name is None:
            raise NbdNegotiationError(
                "Export name is required for new-style negotiation"
            )

        flags_size = struct.calcsize('>H')
        flags_data = sock.recv(flags_size)
        if len(flags_data) < flags_size:
            raise NbdNegotiationError("Incomplete flags received from server")

        flags = struct.unpack('>H', flags_data)[0]
        if not (flags & NBD_FLAG_C_FIXED_NEWSTYLE):
            raise NbdNegotiationError("Server does not support FIXED_NEWSTYLE")

        if flags & NBD_FLAG_NO_ZEROES:
            self._client_flags |= NBD_FLAG_NO_ZEROES

        client_flags = struct.pack('>L', self._client_flags)
        sock.send(client_flags)

        self.export_size = self._select_export(sock, name)

    def _select_export(self, sock: socket.socket, name: str) -> int:
        """Select export."""
        name_bytes = name.encode('ascii') if isinstance(name, str) else name

        magic = struct.pack('>Q', NBD_OPTS_MAGIC)
        opt = struct.pack('>L', NBD_OPT_EXPORT_NAME)
        name_size = struct.pack('>L', len(name_bytes))

        payload = magic + opt + name_size + name_bytes
        sock.sendall(payload)

        response = sock.recv(64)
        if len(response) == 0:
            raise NbdExportError(
                f"Export selection failed. Export name '{name}' may be incorrect"
            )

        decoded = struct.unpack('>QH', response)
        return decoded[0]

    def get_block_size(self) -> int | None:
        """Get block size."""
        return self.export_size

    def close(self) -> None:
        """Close."""
        if self._sock is None:
            return

        try:
            request = struct.pack(
                '>LL8sQL',
                NBD_REQUEST_MAGIC,
                NBD_CMD_DISC,
                self._handle,
                0,
                0,
            )
            self._sock.send(request)
        except socket.error:
            pass

        try:
            self._sock.close()
        except socket.error:
            pass

        self._sock = None
        self.export_size = None

    def read(self, offset: int, length: int) -> bytes:
        """Warning: NOT safe for concurrent reads."""
        if self._sock is None:
            raise NbdReadError("Socket is not connected")

        if self.export_size is None:
            raise NbdReadError("Export size unknown, connection may have failed")

        if offset > self.export_size:
            raise NbdReadError(
                f"Offset {offset} exceeds export size {self.export_size}"
            )

        read_end = offset + length
        if read_end > self.export_size:
            length = self.export_size - offset

        request = struct.pack(
            '>LL8sQL',
            NBD_REQUEST_MAGIC,
            NBD_CMD_READ,
            self._handle,
            offset,
            length,
        )
        self._sock.send(request)

        response_size = struct.calcsize('>LL8s')
        response = self._sock.recv(response_size)
        if len(response) < response_size:
            raise NbdReadError("Incomplete response header received")

        magic, error, handle = struct.unpack('>LL8s', response)

        if magic != NBD_REPLY_MAGIC:
            raise NbdProtocolError(f"Invalid reply magic: {magic:#x}")

        if error != 0:
            raise NbdReadError(f"Server returned error code: {error}")

        data = b''
        while len(data) < length:
            more = self._sock.recv(length - len(data))
            if not more:
                raise NbdReadError(
                    f"Connection closed, required {length} bytes, received {len(data)}"
                )
            data += more

        return data

    def __enter__(self) -> 'NbdClient':
        """Enter."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit."""
        self.close()

    def __repr__(self) -> str:
        """Repr."""
        if self.unix_socket:
            return f"NbdClient(unix_socket={self.unix_socket!r}, export_name={self.export_name!r})"
        return f"NbdClient(host={self.host!r}, port={self.port}, export_name={self.export_name!r})"
