"""VmMetadataHandler – abstract base class for VM metadata operations.

Each storage back-end (file-based, sblk, …) subclasses this and provides
concrete ``_do_*`` implementations.  The handler does **not** touch HTTP
routing or Rsp serialisation – it receives a parsed *cmd* (jsonobject) and
returns a plain ``dict``.
"""
from __future__ import absolute_import


class VmMetadataHandler(object):
    """Abstract handler for the five VM-metadata verbs."""

    # -- public API (thin delegation) -------------------------------------

    def write(self, cmd):
        """Write VM metadata.  Returns ``dict``."""
        return self._do_write(cmd)

    def read(self, cmd):
        """Read a single VM's metadata.  Returns ``dict``."""
        return self._do_read(cmd)

    def get_all(self, cmd):
        """Retrieve all VM metadata entries.  Returns ``dict``."""
        return self._do_get_all(cmd)

    def scan(self, cmd):
        """Lightweight scan (stat-level) of metadata entries.  Returns ``dict``."""
        return self._do_scan(cmd)

    def cleanup(self, cmd):
        """Delete a VM's metadata.  Returns ``dict``."""
        return self._do_cleanup(cmd)

    # -- abstract (must override) -----------------------------------------

    def _do_write(self, cmd):
        raise NotImplementedError

    def _do_read(self, cmd):
        raise NotImplementedError

    def _do_get_all(self, cmd):
        raise NotImplementedError

    def _do_scan(self, cmd):
        raise NotImplementedError

    def _do_cleanup(self, cmd):
        raise NotImplementedError
