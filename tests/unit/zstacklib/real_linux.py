from __future__ import annotations

import importlib.util
import ipaddress
from pathlib import Path


class _IPAddress:
    def __init__(self, value: str):
        self._address = ipaddress.ip_address(value)

    def __contains__(self, item: object) -> bool:
        return item in self._address


class _IPNetwork:
    def __init__(self, value: str):
        self._network = ipaddress.ip_network(value, strict=False)

    def __contains__(self, item: object) -> bool:
        address = item._address if isinstance(item, _IPAddress) else ipaddress.ip_address(str(item))
        return address in self._network


class _Netaddr:
    IPAddress = _IPAddress
    IPNetwork = _IPNetwork


def load_real_linux():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / 'zstacklib' / 'zstacklib' / 'utils' / 'linux.py'
    spec = importlib.util.spec_from_file_location('zstacklib_utils_linux_under_test', str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.netaddr = _Netaddr
    return module
