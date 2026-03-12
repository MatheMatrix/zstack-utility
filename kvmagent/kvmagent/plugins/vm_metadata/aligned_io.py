"""O_DIRECT aligned I/O via posix_memalign + ctypes.

All sblk metadata I/O uses O_DIRECT | O_SYNC for cache-bypass and durability.
Buffer addresses must be aligned to the logical sector size (typically 512 B);
we conservatively align to 4096 B (page size) for maximum compatibility.

See vm-metadata-04e-sblk-ops.md §5.3 / §5.5 for design rationale.
"""
from __future__ import absolute_import

import os
import ctypes
import errno as errno_mod

from .constants import ALIGNMENT

# ---------------------------------------------------------------------------
# libc binding – lazy-loaded so the module can be imported on non-Linux
# platforms (e.g. Windows dev machines) without crashing at import time.
# All actual I/O still requires Linux + libc.so.6.
# ---------------------------------------------------------------------------
_libc = None


def _get_libc():
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL('libc.so.6', use_errno=True)
    return _libc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def align_up(value, alignment=ALIGNMENT):
    """Round *value* up to the nearest multiple of *alignment*."""
    return ((value + alignment - 1) // alignment) * alignment


# ---------------------------------------------------------------------------
# AlignedBuffer
# ---------------------------------------------------------------------------
class AlignedBuffer(object):
    """Page-aligned buffer for O_DIRECT I/O.  Use as a context manager.

    Example::

        with AlignedBuffer(512) as buf:
            buf.fill(header_bytes)
            buf.pwrite(fd, 0)

        with AlignedBuffer(1 * 1024 * 1024) as buf:
            buf.pread(fd, slot_offset)
            data = buf.read(expected_size)
    """

    def __init__(self, size, alignment=ALIGNMENT):
        self._alignment = alignment
        self._size = align_up(size, alignment)
        self._ptr = ctypes.c_void_p()
        ret = _get_libc().posix_memalign(
            ctypes.byref(self._ptr), alignment, self._size)
        if ret != 0:
            raise OSError(ret, "posix_memalign failed (size=%d, align=%d)"
                          % (self._size, alignment))
        # Zero-fill the entire buffer to ensure deterministic content
        ctypes.memset(self._ptr, 0, self._size)

    # -- properties --------------------------------------------------------
    @property
    def size(self):
        """Actual (aligned-up) buffer size in bytes."""
        return self._size

    # -- data access -------------------------------------------------------
    def fill(self, data, offset=0):
        """Copy *data* (bytes) into the buffer starting at *offset*."""
        n = len(data)
        if offset + n > self._size:
            raise ValueError(
                "data (len=%d) at offset %d exceeds buffer size %d"
                % (n, offset, self._size))
        ctypes.memmove(self._ptr.value + offset, data, n)

    def read(self, length, offset=0):
        """Return *length* bytes from the buffer starting at *offset*."""
        if offset + length > self._size:
            raise ValueError(
                "read (len=%d) at offset %d exceeds buffer size %d"
                % (length, offset, self._size))
        return ctypes.string_at(self._ptr.value + offset, length)

    # -- I/O ---------------------------------------------------------------
    def pwrite(self, fd, file_offset):
        """Write the full buffer to *fd* at *file_offset* (pwrite(2)).

        Handles EINTR and short writes by retrying until all bytes are
        written, as required by §6 of the design spec.
        """
        total_written = 0
        while total_written < self._size:
            ptr = ctypes.c_void_p(self._ptr.value + total_written)
            remaining = self._size - total_written
            ret = _get_libc().pwrite(
                fd, ptr, remaining,
                ctypes.c_longlong(file_offset + total_written))
            if ret < 0:
                err = ctypes.get_errno()
                if err == errno_mod.EINTR:
                    continue
                raise OSError(err,
                              "pwrite failed at offset %d: %s"
                              % (file_offset + total_written,
                                 os.strerror(err)))
            if ret == 0:
                raise OSError(0, "pwrite returned 0 at offset %d"
                              % (file_offset + total_written))
            total_written += ret
        return total_written

    def pread(self, fd, file_offset):
        """Read from *fd* at *file_offset* into the buffer (pread(2)).

        Handles EINTR and short reads by retrying until the buffer is
        filled or EOF is reached, as required by §6 of the design spec.
        """
        total_read = 0
        while total_read < self._size:
            ptr = ctypes.c_void_p(self._ptr.value + total_read)
            remaining = self._size - total_read
            ret = _get_libc().pread(
                fd, ptr, remaining,
                ctypes.c_longlong(file_offset + total_read))
            if ret < 0:
                err = ctypes.get_errno()
                if err == errno_mod.EINTR:
                    continue
                raise OSError(err,
                              "pread failed at offset %d: %s"
                              % (file_offset + total_read,
                                 os.strerror(err)))
            if ret == 0:
                break  # EOF
            total_read += ret
        return total_read

    # -- lifecycle ---------------------------------------------------------
    def close(self):
        if self._ptr.value:
            _get_libc().free(self._ptr)
            self._ptr = ctypes.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------
def aligned_pwrite(fd, data, file_offset, alignment=ALIGNMENT):
    """Write *data* at *file_offset* using an aligned buffer.

    Data is zero-padded to the next *alignment* boundary automatically.
    """
    with AlignedBuffer(len(data), alignment) as buf:
        buf.fill(data)
        return buf.pwrite(fd, file_offset)


def aligned_pread(fd, size, file_offset, alignment=ALIGNMENT):
    """Read *size* bytes from *fd* at *file_offset* via aligned buffer.

    Returns raw bytes whose length equals ``align_up(size, alignment)``.
    """
    with AlignedBuffer(size, alignment) as buf:
        buf.pread(fd, file_offset)
        return buf.read(buf.size)


def open_lv(lv_path, readonly=False):
    """Open an LV device with O_DIRECT | O_SYNC.

    Returns:
        int – file descriptor (caller must ``os.close(fd)``).
    """
    flags = os.O_RDONLY if readonly else os.O_RDWR
    flags |= os.O_DIRECT | os.O_SYNC
    return os.open(lv_path, flags)
