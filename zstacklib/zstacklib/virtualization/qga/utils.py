# Copyright (c) ZStack.io, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from zstacklib.virtualization.qga.constants import (
    QGA_CHANNEL_STATE_CONNECTED,
)

if TYPE_CHECKING:
    pass


def get_qga_channel_state(domain_xml: str) -> str | None:
    xml_tree = ET.fromstring(domain_xml)
    channel = xml_tree.find("./devices/channel/target[@name='org.qemu.guest_agent.0']")
    if channel is not None:
        return channel.get('state')
    return None


def is_qga_connected(domain_xml: str) -> bool:
    try:
        return get_qga_channel_state(domain_xml) == QGA_CHANNEL_STATE_CONNECTED
    except Exception:
        return False
