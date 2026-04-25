"""
M1 IPv6 distro/zstackctl 单元测试：TP-090~093

覆盖场景：
  TP-090  is_valid_ip("2001:db8::1") 返回 True
  TP-091  is_valid_ip("192.168.1.1") 返回 True（IPv4 回归）
  TP-092  ip_to_hostname("2001:db8::1") 生成合法 hostname（无冒号无点）
  TP-093  DB URL 中 IPv6 正确替换（IPv4 URL → IPv6 with brackets）

注意：ctl.py 存在重度依赖，将被测逻辑内联至本文件并注明来源，
      与 test_ipv6_m3_utils.py 保持一致。
"""

import re
import socket
import unittest


# ---------------------------------------------------------------------------
# 内联逻辑（来源：zstack-utility/zstackctl/zstackctl/ctl.py ChangeIpCmd.run()）
# ---------------------------------------------------------------------------

def _is_valid_ip(addr):
    """F-037: 替换 IPv4-only ip_check 正则"""
    for af in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(af, addr)
            return True
        except socket.error:
            pass
    return False


def _ip_to_hostname(ip):
    """F-037: 替换 args.ip.replace('.', '-')"""
    return ip.strip('[]').replace(':', '-').replace('.', '-')


def _replace_db_url(db_url, mysql_ip):
    """F-037: 替换 DB.url 中的 IP（支持 IPv4 和 IPv6 JDBC 格式）"""
    ipv6_match = re.findall(r'\[([0-9a-fA-F:]+)\]', db_url)
    ipv4_match = re.findall(r'[0-9]+(?:\.[0-9]{1,3}){3}|localhost', db_url)
    if ipv6_match:
        db_old_ip = ipv6_match[0]
        db_new_ip = ('[%s]' % mysql_ip) if ':' in mysql_ip else mysql_ip
        return db_url.replace('[%s]' % db_old_ip, db_new_ip, 1), db_old_ip
    elif ipv4_match:
        db_old_ip = ipv4_match[0]
        db_new_ip = ('[%s]' % mysql_ip) if ':' in mysql_ip else mysql_ip
        return db_url.replace(db_old_ip, db_new_ip, 1), db_old_ip
    return db_url, None


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------

class TestIsValidIp(unittest.TestCase):
    """TP-090, TP-091"""

    def test_ipv6_valid(self):
        """TP-090: 合法 IPv6 地址返回 True"""
        self.assertTrue(_is_valid_ip("2001:db8::1"))
        self.assertTrue(_is_valid_ip("::1"))
        self.assertTrue(_is_valid_ip("fe80::1"))
        self.assertTrue(_is_valid_ip("2001:0db8:0000:0000:0000:0000:0000:0001"))

    def test_ipv4_valid(self):
        """TP-091: 合法 IPv4 地址返回 True（回归）"""
        self.assertTrue(_is_valid_ip("192.168.1.1"))
        self.assertTrue(_is_valid_ip("10.0.0.1"))
        self.assertTrue(_is_valid_ip("127.0.0.1"))

    def test_invalid_returns_false(self):
        """非法地址返回 False"""
        self.assertFalse(_is_valid_ip("not-an-ip"))
        self.assertFalse(_is_valid_ip("999.999.999.999"))
        self.assertFalse(_is_valid_ip("2001:xyz::1"))
        self.assertFalse(_is_valid_ip(""))


class TestIpToHostname(unittest.TestCase):
    """TP-092"""

    def test_ipv6_hostname(self):
        """TP-092: IPv6 地址转 hostname（冒号→连字符，无点，无括号）"""
        result = _ip_to_hostname("2001:db8::1")
        self.assertEqual(result, "2001-db8--1")
        # no colons, no brackets
        self.assertNotIn(':', result)
        self.assertNotIn('[', result)
        self.assertNotIn(']', result)

    def test_ipv4_hostname(self):
        """IPv4 地址转 hostname（点→连字符，回归）"""
        result = _ip_to_hostname("192.168.1.100")
        self.assertEqual(result, "192-168-1-100")
        self.assertNotIn('.', result)

    def test_ipv6_full_form(self):
        """全展开 IPv6 hostname"""
        result = _ip_to_hostname("2001:0db8:0000:0000:0000:0000:0000:0001")
        self.assertNotIn(':', result)
        self.assertNotIn('.', result)


class TestReplaceDbUrl(unittest.TestCase):
    """TP-093"""

    def test_ipv4_to_ipv6(self):
        """TP-093: IPv4 DB URL 替换为 IPv6（自动加括号）"""
        url = "jdbc:mysql://192.168.1.1:3306"
        new_url, old_ip = _replace_db_url(url, "2001:db8::1")
        self.assertEqual(new_url, "jdbc:mysql://[2001:db8::1]:3306")
        self.assertEqual(old_ip, "192.168.1.1")

    def test_ipv6_to_ipv4(self):
        """IPv6 DB URL 替换为 IPv4（去括号）"""
        url = "jdbc:mysql://[2001:db8::1]:3306"
        new_url, old_ip = _replace_db_url(url, "10.0.0.1")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.1:3306")
        self.assertEqual(old_ip, "2001:db8::1")

    def test_ipv4_to_ipv4(self):
        """IPv4 DB URL 替换为 IPv4（回归）"""
        url = "jdbc:mysql://192.168.1.1:3306/zstack"
        new_url, old_ip = _replace_db_url(url, "10.0.0.100")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.100:3306/zstack")
        self.assertEqual(old_ip, "192.168.1.1")

    def test_ipv6_to_ipv6(self):
        """IPv6 DB URL 替换为 IPv6"""
        url = "jdbc:mysql://[2001:db8::1]:3306"
        new_url, old_ip = _replace_db_url(url, "2001:db8::2")
        self.assertEqual(new_url, "jdbc:mysql://[2001:db8::2]:3306")
        self.assertEqual(old_ip, "2001:db8::1")

    def test_localhost(self):
        """localhost DB URL 替换为 IPv4（回归）"""
        url = "jdbc:mysql://localhost:3306"
        new_url, old_ip = _replace_db_url(url, "10.0.0.1")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.1:3306")
        self.assertEqual(old_ip, "localhost")


if __name__ == '__main__':
    unittest.main()
