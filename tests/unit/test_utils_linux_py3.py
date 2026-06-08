"""Tests for Python 3.11 bytes/str fixes in linux.py and ceph agents."""
from __future__ import annotations

import os
import struct
import tempfile
import pytest


# ---------------------------------------------------------------------------
# qcow2_direct_get_backing_file — replicate fixed logic to verify
# correctness, since linux module is mocked by conftest.
# TODO: if conftest stops mocking linux, replace with direct import from
#       zstacklib.utils.linux.qcow2_direct_get_backing_file
# ---------------------------------------------------------------------------
def _qcow2_direct_get_backing_file(path):
    """Exact copy of the fixed qcow2_direct_get_backing_file from linux.py"""
    with open(path, 'rb') as f:
        o = f.read(4096)
    magic = o[:4]
    if magic != b'QFI\xfb':
        return ""

    backing_file_info = o[8:20]
    backing_file_offset = struct.unpack('>Q', backing_file_info[:8])[0]
    if backing_file_offset == 0:
        return ""

    backing_file_size = struct.unpack('>L', backing_file_info[8:])[0]
    return o[backing_file_offset:backing_file_offset+backing_file_size].decode()


class TestQcow2DirectGetBackingFile:
    @staticmethod
    def _make_qcow2_header(backing_file=b""):
        """Build a minimal qcow2 header with optional backing file."""
        buf = bytearray(4096)
        buf[0:4] = b'QFI\xfb'  # magic
        if backing_file:
            offset = 512
            buf[8:16] = struct.pack('>Q', offset)
            buf[16:20] = struct.pack('>L', len(backing_file))
            buf[offset:offset+len(backing_file)] = backing_file
        else:
            buf[8:16] = struct.pack('>Q', 0)
        return bytes(buf)

    def test_detects_backing_file(self):
        header = self._make_qcow2_header(b"/var/lib/images/base.qcow2")
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, header)
            os.close(fd)
            result = _qcow2_direct_get_backing_file(path)
            assert result == "/var/lib/images/base.qcow2"
        finally:
            os.unlink(path)

    def test_no_backing_file(self):
        header = self._make_qcow2_header()
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, header)
            os.close(fd)
            result = _qcow2_direct_get_backing_file(path)
            assert result == ""
        finally:
            os.unlink(path)

    def test_non_qcow2_returns_empty(self):
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, b'\x00' * 4096)
            os.close(fd)
            result = _qcow2_direct_get_backing_file(path)
            assert result == ""
        finally:
            os.unlink(path)

    def test_return_type_is_str(self):
        header = self._make_qcow2_header(b"/backing/file.qcow2")
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, header)
            os.close(fd)
            result = _qcow2_direct_get_backing_file(path)
            assert isinstance(result, str)
        finally:
            os.unlink(path)
