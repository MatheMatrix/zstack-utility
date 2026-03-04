"""Tests for storage.nbd module."""

import pytest

from zstacklib.storage.nbd import (
    NbdError,
    NbdConnectionError,
    NbdNegotiationError,
    NbdReadError,
    NbdProtocolError,
    NBD_CMD_READ,
    NBD_CMD_WRITE,
    NBD_CMD_DISC,
    NBD_CMD_FLUSH,
    NBD_CMD_TRIM,
    NBD_FLAG_HAS_FLAGS,
    NBD_FLAG_READ_ONLY,
    NBD_FLAG_SEND_FLUSH,
    NBD_OPT_EXPORT_NAME,
    NBD_OPT_ABORT,
    NBD_OPT_LIST,
    NBD_OPT_GO,
    NbdClient,
)


class TestNbdConstants:
    def test_command_constants(self):
        assert NBD_CMD_READ == 0
        assert NBD_CMD_WRITE == 1
        assert NBD_CMD_DISC == 2
        assert NBD_CMD_FLUSH == 3
        assert NBD_CMD_TRIM == 4

    def test_flag_constants(self):
        assert NBD_FLAG_HAS_FLAGS == (1 << 0)
        assert NBD_FLAG_READ_ONLY == (1 << 1)
        assert NBD_FLAG_SEND_FLUSH == (1 << 2)

    def test_option_constants(self):
        assert NBD_OPT_EXPORT_NAME == 1
        assert NBD_OPT_ABORT == 2
        assert NBD_OPT_LIST == 3
        assert NBD_OPT_GO == 7


class TestNbdExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(NbdConnectionError, NbdError)
        assert issubclass(NbdNegotiationError, NbdError)
        assert issubclass(NbdReadError, NbdError)
        assert issubclass(NbdProtocolError, NbdError)

    def test_exception_message(self):
        err = NbdConnectionError("connection failed")
        assert str(err) == "connection failed"


class TestNbdClient:
    def test_client_init(self):
        client = NbdClient("localhost", 10809)
        assert client.host == "localhost"
        assert client.port == 10809
        assert client.export_name is None

    def test_client_with_export(self):
        client = NbdClient("127.0.0.1", 10809, export_name="test")
        assert client.export_name == "test"

    def test_client_default_port(self):
        client = NbdClient("localhost")
        assert client.port == 10809
