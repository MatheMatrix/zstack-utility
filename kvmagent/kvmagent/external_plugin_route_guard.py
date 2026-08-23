# -*- coding: utf-8 -*-
from __future__ import absolute_import

import functools
import json


def mutation_failure(compatibility_state):
    if compatibility_state == "DRIFTED_NEXT_START":
        return ("PLUGIN_NEXT_START_DRIFT",
                "external plugin next-start runtime has drifted")
    if compatibility_state == "INCOMPATIBLE_RUNTIME":
        return ("PLUGIN_RUNTIME_INCOMPATIBLE",
                "external plugin runtime is not compatible")
    return ("PLUGIN_RUNTIME_VERSION_UNAVAILABLE",
            "external plugin runtime compatibility is unavailable")


def guard_mutation(handler, allowed, compatibility_state):
    """Fence mutation routes while leaving diagnostic handlers untouched."""
    @functools.wraps(handler)
    def guarded(*args, **kwargs):
        if not allowed():
            error_code, message = mutation_failure(compatibility_state())
            return json.dumps({
                "success": False,
                "errorCode": error_code,
                "error": message,
            }, sort_keys=True)
        return handler(*args, **kwargs)
    return guarded
