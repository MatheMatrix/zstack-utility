"""Ebtables command utilities."""

from typing import Optional

from zstacklib.utils import shell

_ebtablesUseLock: Optional[bool] = None


def get_ebtables_cmd() -> str:
    """Get the appropriate ebtables command with concurrent flag if supported."""
    global _ebtablesUseLock

    if _ebtablesUseLock is None:
        _ebtablesUseLock = shell.run("ebtables --concurrent -L > /dev/null") == 0

    if _ebtablesUseLock:
        return "ebtables --concurrent"
    return "ebtables"
