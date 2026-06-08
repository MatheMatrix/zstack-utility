"""Go-style defer mechanism for Python.

Provides defer() to register cleanup functions that execute when the
decorated function exits, regardless of how it exits (return/exception).
"""

from zstacklib.system.defer.core import defer, protect

__all__ = ['defer', 'protect']
