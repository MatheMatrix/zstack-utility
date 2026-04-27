"""
M1 IPv6 distro/zstackctl unit tests: TP-090~093

Test scenarios:
  TP-090  is_valid_ip("2001:db8::1") returns True
  TP-091  is_valid_ip("192.168.1.1") returns True (IPv4 regression)
  TP-092  ip_to_hostname("2001:db8::1") produces valid hostname (no colons, no dots)
  TP-093  DB URL IPv6 replacement (IPv4 URL -> IPv6 with brackets)

Note: ctl.py has heavy dependencies; tested logic is inlined here with source noted,
      consistent with test_ipv6_m3_utils.py approach.
"""

import re
import socket
import unittest


# ---------------------------------------------------------------------------
# Inlined logic (source: zstack-utility/zstackctl/zstackctl/ctl.py ChangeIpCmd.run())
# ---------------------------------------------------------------------------

def _is_valid_ip(addr):
    """F-037: replace IPv4-only ip_check regex"""
    for af in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(af, addr)
            return True
        except socket.error:
            pass
    return False


def _ip_to_hostname(ip):
    """F-037: replace args.ip.replace('.', '-')"""
    return ip.strip('[]').replace(':', '-').replace('.', '-')


def _replace_db_url(db_url, mysql_ip):
    """F-037: replace DB.url IP (supports both IPv4 and IPv6 JDBC format)"""
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
# Test cases
# ---------------------------------------------------------------------------

class TestIsValidIp(unittest.TestCase):
    """TP-090, TP-091"""

    def test_ipv6_valid(self):
        """TP-090: valid IPv6 address returns True"""
        self.assertTrue(_is_valid_ip("2001:db8::1"))
        self.assertTrue(_is_valid_ip("::1"))
        self.assertTrue(_is_valid_ip("fe80::1"))
        self.assertTrue(_is_valid_ip("2001:0db8:0000:0000:0000:0000:0000:0001"))

    def test_ipv4_valid(self):
        """TP-091: valid IPv4 address returns True (regression)"""
        self.assertTrue(_is_valid_ip("192.168.1.1"))
        self.assertTrue(_is_valid_ip("10.0.0.1"))
        self.assertTrue(_is_valid_ip("127.0.0.1"))

    def test_invalid_returns_false(self):
        """invalid address returns False"""
        self.assertFalse(_is_valid_ip("not-an-ip"))
        self.assertFalse(_is_valid_ip("999.999.999.999"))
        self.assertFalse(_is_valid_ip("2001:xyz::1"))
        self.assertFalse(_is_valid_ip(""))


class TestIpToHostname(unittest.TestCase):
    """TP-092"""

    def test_ipv6_hostname(self):
        """TP-092: IPv6 address converted to hostname (colons -> hyphens, no dots, no brackets)"""
        result = _ip_to_hostname("2001:db8::1")
        self.assertEqual(result, "2001-db8--1")
        # no colons, no brackets
        self.assertNotIn(':', result)
        self.assertNotIn('[', result)
        self.assertNotIn(']', result)

    def test_ipv4_hostname(self):
        """IPv4 address converted to hostname (dots -> hyphens, regression)"""
        result = _ip_to_hostname("192.168.1.100")
        self.assertEqual(result, "192-168-1-100")
        self.assertNotIn('.', result)

    def test_ipv6_full_form(self):
        """fully expanded IPv6 hostname"""
        result = _ip_to_hostname("2001:0db8:0000:0000:0000:0000:0000:0001")
        self.assertNotIn(':', result)
        self.assertNotIn('.', result)


class TestReplaceDbUrl(unittest.TestCase):
    """TP-093"""

    def test_ipv4_to_ipv6(self):
        """TP-093: IPv4 DB URL replaced with IPv6 (brackets added automatically)"""
        url = "jdbc:mysql://192.168.1.1:3306"
        new_url, old_ip = _replace_db_url(url, "2001:db8::1")
        self.assertEqual(new_url, "jdbc:mysql://[2001:db8::1]:3306")
        self.assertEqual(old_ip, "192.168.1.1")

    def test_ipv6_to_ipv4(self):
        """IPv6 DB URL replaced with IPv4 (brackets removed)"""
        url = "jdbc:mysql://[2001:db8::1]:3306"
        new_url, old_ip = _replace_db_url(url, "10.0.0.1")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.1:3306")
        self.assertEqual(old_ip, "2001:db8::1")

    def test_ipv4_to_ipv4(self):
        """IPv4 DB URL replaced with IPv4 (regression)"""
        url = "jdbc:mysql://192.168.1.1:3306/zstack"
        new_url, old_ip = _replace_db_url(url, "10.0.0.100")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.100:3306/zstack")
        self.assertEqual(old_ip, "192.168.1.1")

    def test_ipv6_to_ipv6(self):
        """IPv6 DB URL replaced with IPv6"""
        url = "jdbc:mysql://[2001:db8::1]:3306"
        new_url, old_ip = _replace_db_url(url, "2001:db8::2")
        self.assertEqual(new_url, "jdbc:mysql://[2001:db8::2]:3306")
        self.assertEqual(old_ip, "2001:db8::1")

    def test_localhost(self):
        """localhost DB URL replaced with IPv4 (regression)"""
        url = "jdbc:mysql://localhost:3306"
        new_url, old_ip = _replace_db_url(url, "10.0.0.1")
        self.assertEqual(new_url, "jdbc:mysql://10.0.0.1:3306")
        self.assertEqual(old_ip, "localhost")


if __name__ == '__main__':
    unittest.main()
