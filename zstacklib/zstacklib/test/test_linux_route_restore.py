import unittest
from unittest.mock import patch

from zstacklib.utils import linux


class TestIpv6RouteRestore(unittest.TestCase):
    def test_restore_ipv6_route_drops_runtime_expiration(self):
        route_info = {
            'ipv4_addresses': [],
            'ipv6_addresses': [],
            'routes': [],
            'direct_routes6': [],
            'routes6': [
                'default via fe80::1 dev zsn1 proto ra metric 1024 '
                'expires 172sec hoplimit 64 pref medium'
            ],
        }

        with patch.object(linux.shell, 'call') as call:
            linux._restore_dev_route('br_zsn1', route_info)

        call.assert_called_once_with(
            'ip -6 route add default via fe80::1 dev br_zsn1 '
            'proto ra metric 1024 hoplimit 64 pref medium'
        )

    def test_restore_ipv6_route_keeps_routes_without_expiration(self):
        route_info = {
            'ipv4_addresses': [],
            'ipv6_addresses': [],
            'routes': [],
            'direct_routes6': [
                '2001:db8:1::/64 dev zsn1 proto kernel expires 172sec'
            ],
            'routes6': [],
        }

        with patch.object(linux.shell, 'call') as call:
            linux._restore_dev_route('br_zsn1', route_info)

        call.assert_called_once_with(
            'ip -6 route add 2001:db8:1::/64 dev br_zsn1 proto kernel'
        )


if __name__ == '__main__':
    unittest.main()
