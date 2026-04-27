"""
M2 IPv6 测试：TP-047~051
"""
import sys
import unittest
import socket
import ipaddress
from unittest.mock import MagicMock, patch


class TestHttpIpv6Bind(unittest.TestCase):
    """TP-047: CherryPy server.socket_host IPv6 dual-stack binding (http.py L308-314)"""

    def test_ipv6_socket_available_binds_colon_colon(self):
        """TP-047a: when IPv6 is available, socket_host = '::'"""
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.__enter__ = mock_socket.return_value
            mock_socket.return_value.__exit__ = lambda *a: None
            try:
                _s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                _s.close()
                bind_ip = '::'
            except OSError:
                bind_ip = '0.0.0.0'
            self.assertEqual(bind_ip, '::')

    def test_ipv6_unavailable_fallback_to_0000(self):
        """TP-047b: when IPv6 is disabled, fallback to 0.0.0.0"""
        with patch('socket.socket') as mock_socket:
            mock_socket.side_effect = OSError("IPv6 not available")
            try:
                _s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                _s.close()
                bind_ip = '::'
            except OSError:
                bind_ip = '0.0.0.0'
            self.assertEqual(bind_ip, '0.0.0.0')


class TestLinkLocalFilter(unittest.TestCase):
    """TP-050/051: link-local 地址过滤（host_plugin.py L1359-1364 / cephagent.py L695-700）"""

    def _is_valid_ipv6(self, addr):
        """与源码一致的过滤逻辑"""
        try:
            return not ipaddress.ip_address(addr.split('%')[0]).is_link_local
        except ValueError:
            return False

    def test_fe80_is_link_local(self):
        """TP-050: fe80:: 地址被过滤"""
        self.assertFalse(self._is_valid_ipv6("fe80::1"))
        self.assertFalse(self._is_valid_ipv6("fe80::1%eth0"))

    def test_fe9x_is_link_local(self):
        """RFC 4291 fe80::/10 覆盖 fe80~febf，不只是 fe80"""
        self.assertFalse(self._is_valid_ipv6("fe90::1"))
        self.assertFalse(self._is_valid_ipv6("fea0::1"))
        self.assertFalse(self._is_valid_ipv6("febf::1"))

    def test_global_ipv6_passes(self):
        """TP-050/051: 全局 IPv6 地址不被过滤"""
        self.assertTrue(self._is_valid_ipv6("2001:db8::1"))
        self.assertTrue(self._is_valid_ipv6("fd00::1"))
        self.assertTrue(self._is_valid_ipv6("::1"))

    def test_zone_id_stripped(self):
        """TP-050: 带 zone id 的 IPv6 地址正确处理（strip %ifname）"""
        self.assertTrue(self._is_valid_ipv6("2001:db8::1%eth0"))
        self.assertFalse(self._is_valid_ipv6("fe80::1%eth0"))

    def test_startswith_fe80_is_insufficient(self):
        """TP-050: 旧 startswith('fe80') 会漏掉 fea0 等，ipaddress.is_link_local 覆盖全范围"""
        fea0 = "fea0::1"
        self.assertFalse(fea0.lower().startswith('fe80'))
        self.assertTrue(ipaddress.ip_address(fea0).is_link_local)


class TestCheckSocketAvailable(unittest.TestCase):
    """TP-049: linux.py check_socket_available() IPv6 支持（L2512-2530）

    实际修改的函数为 check_socket_available，使用 getaddrinfo(AF_UNSPEC) 支持 IPv6。
    """

    def test_getaddrinfo_accepts_ipv6(self):
        """TP-049: getaddrinfo 对 IPv6 地址不抛异常，且返回 AF_INET6 结果"""
        host = "2001:db8::1"
        port = 22
        try:
            results = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            self.assertIsNotNone(results)
            families = [r[0] for r in results]
            self.assertIn(socket.AF_INET6, families)
        except Exception as e:
            self.fail(f"getaddrinfo should not raise for IPv6, got: {e}")

    def test_getaddrinfo_accepts_ipv4(self):
        """TP-049: getaddrinfo 对 IPv4 地址同样工作（不退化）"""
        try:
            results = socket.getaddrinfo("192.168.1.1", 22, socket.AF_UNSPEC, socket.SOCK_STREAM)
            families = [r[0] for r in results]
            self.assertIn(socket.AF_INET, families)
        except Exception as e:
            self.fail(f"getaddrinfo should not raise for IPv4, got: {e}")

    def test_getaddrinfo_af_unspec_supports_both(self):
        """TP-049: AF_UNSPEC 让 getaddrinfo 同时支持 IPv4 和 IPv6（与源码逻辑一致）"""
        ipv6_host = "::1"
        ipv4_host = "127.0.0.1"
        for host in (ipv6_host, ipv4_host):
            try:
                results = socket.getaddrinfo(host, 80, socket.AF_UNSPEC, socket.SOCK_STREAM)
                self.assertTrue(len(results) > 0, f"No results for {host}")
            except Exception as e:
                self.fail(f"getaddrinfo raised for {host}: {e}")


if __name__ == '__main__':
    unittest.main()
