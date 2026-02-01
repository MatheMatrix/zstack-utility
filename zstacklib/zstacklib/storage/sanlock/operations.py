# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from zstacklib.utils import shell


def init_resource(resource: str) -> int:
    cmd = f"sanlock direct init -r {resource}"
    return shell.run(cmd)
