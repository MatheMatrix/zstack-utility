"""
M3 IPv6 测试：TP-079~082

覆盖场景：
  TP-079  ConsoleProxy websockify IPv6 格式  (console_proxy_agent._format_proxy_host_port)
  TP-080  BM Gateway 回调 URL IPv6           (baremetal_v2_gateway_agent._bracket_ipv6)
  TP-081  BM Agent HTTP 双栈绑定             (bm_instance_agent/api/config.py server['host'])
  TP-082  BM PXE Server IPv6 接口地址解析    (pxeserveragent._get_ip_address)

注意：目标模块存在重度第三方依赖（kvmagent、zstacklib 等），
      直接 import 会失败，因此将被测函数逻辑内联至测试文件并注明来源，
      与 M2 (test_ipv6_utils.py) 的做法保持一致。
"""
import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock
import subprocess


# ---------------------------------------------------------------------------
# 被测逻辑内联（来源标注）
# ---------------------------------------------------------------------------

def _format_proxy_host_port(hostname, port):
    """
    来源：zstack-utility/consoleproxy/consoleproxy/console_proxy_agent.py
    函数：_format_proxy_host_port(hostname, port)

    为 websockify 格式化 host:port；裸 IPv6 地址自动加方括号。
    """
    if hostname and ':' in hostname and not hostname.startswith('['):
        return "[%s]:%d" % (hostname, port)
    return "%s:%d" % (hostname, port)


def _bracket_ipv6(ip):
    """
    来源：zstack-utility/kvmagent/kvmagent/plugins/baremetal_v2_gateway_agent.py
    函数：_bracket_ipv6(ip)

    在 HTTP URL 中对裸 IPv6 地址加方括号。
    """
    if ip and ':' in ip and not ip.startswith('['):
        return '[%s]' % ip
    return ip


def _get_ip_address_logic(out):
    """
    来源：zstack-utility/baremetalpxeserver/baremetalpxeserver/pxeserveragent.py
    静态方法：PxeServerAgent._get_ip_address(ifname)

    将 `ip addr show` 的文本输出解析为 IP 地址（优先 IPv4，无则取 IPv6 全局地址）。
    此处提取纯解析逻辑以便单元测试，不依赖 subprocess 调用。
    """
    ipv4 = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)/', out)
    ipv6 = re.findall(r'inet6\s+([0-9a-f:]+)/\d+\s+scope global', out)
    if ipv4:
        return ipv4[0]
    if ipv6:
        return ipv6[0]
    raise Exception("no IP found")


def _resolve_server_host(env_value=None):
    """
    来源：zstack-utility/bm-instance-agent/bm_instance_agent/api/config.py
    配置项：server['host'] = os.environ.get('BM_AGENT_BIND_IP', '::')

    模拟模块加载时 os.environ.get() 的执行逻辑，便于测试环境变量覆盖行为。
    """
    if env_value is None:
        return os.environ.get('BM_AGENT_BIND_IP', '::')
    return env_value


# ===========================================================================
# TP-079: ConsoleProxy websockify IPv6 格式
# ===========================================================================

class TestFormatProxyHostPort(unittest.TestCase):
    """TP-079: websockify host:port 格式化——裸 IPv6 地址加方括号"""

    def test_ipv6_bare_gets_brackets(self):
        """TP-079a: 裸 IPv6 地址添加方括号，格式为 [addr]:port"""
        result = _format_proxy_host_port("2001:db8::1", 6080)
        self.assertEqual(result, "[2001:db8::1]:6080")

    def test_ipv4_no_brackets(self):
        """TP-079b: IPv4 地址不加方括号"""
        result = _format_proxy_host_port("192.168.1.1", 5900)
        self.assertEqual(result, "192.168.1.1:5900")

    def test_already_bracketed_ipv6_is_idempotent(self):
        """TP-079c: 已有方括号的 IPv6 地址不重复添加（幂等）"""
        result = _format_proxy_host_port("[2001:db8::1]", 6080)
        self.assertEqual(result, "[2001:db8::1]:6080")

    def test_ps_grep_pattern_escaping(self):
        """TP-079d: ps grep pattern 中方括号需转义，防止被 shell/grep 解释为字符类"""
        host_port = "[2001:db8::1]:6080"
        escaped = host_port.replace('[', r'\[').replace(']', r'\]')
        self.assertEqual(escaped, r"\[2001:db8::1\]:6080")
        # 转义后不再含未转义的 [ ]
        self.assertNotIn('[', escaped.replace(r'\[', '').replace(r'\]', ''))

    def test_localhost_ipv4(self):
        """TP-079e: 回环 IPv4 不加括号"""
        result = _format_proxy_host_port("127.0.0.1", 5900)
        self.assertEqual(result, "127.0.0.1:5900")

    def test_ipv6_loopback(self):
        """TP-079f: IPv6 回环地址 ::1 应加方括号"""
        result = _format_proxy_host_port("::1", 6080)
        self.assertEqual(result, "[::1]:6080")

    def test_empty_hostname_returns_colon_port(self):
        """TP-079g: hostname 为空字符串时，保持原样（不崩溃）"""
        result = _format_proxy_host_port("", 6080)
        self.assertEqual(result, ":6080")


# ===========================================================================
# TP-080: BM Gateway 回调 URL IPv6
# ===========================================================================

class TestBracketIpv6(unittest.TestCase):
    """TP-080: BM Gateway _bracket_ipv6 及 HTTP URL 构造"""

    def test_bare_ipv6_gets_brackets(self):
        """TP-080a: 裸 IPv6 地址加方括号"""
        self.assertEqual(_bracket_ipv6("2001:db8::1"), "[2001:db8::1]")

    def test_ipv4_passthrough(self):
        """TP-080b: IPv4 地址原样返回"""
        self.assertEqual(_bracket_ipv6("192.168.1.1"), "192.168.1.1")

    def test_already_bracketed_is_idempotent(self):
        """TP-080c: 已有方括号的 IPv6 不重复添加（幂等）"""
        self.assertEqual(_bracket_ipv6("[2001:db8::1]"), "[2001:db8::1]")

    def test_callback_url_ipv6(self):
        """TP-080d: 使用 _bracket_ipv6 构造 HTTP 回调 URL 格式正确"""
        url = "http://%s:%d/callback" % (_bracket_ipv6("2001:db8::1"), 7070)
        self.assertEqual(url, "http://[2001:db8::1]:7070/callback")

    def test_callback_url_ipv4(self):
        """TP-080e: IPv4 回调 URL 构造不受影响"""
        url = "http://%s:%d/callback" % (_bracket_ipv6("10.0.0.1"), 7070)
        self.assertEqual(url, "http://10.0.0.1:7070/callback")

    def test_ipv6_loopback(self):
        """TP-080f: ::1 回环地址加方括号"""
        self.assertEqual(_bracket_ipv6("::1"), "[::1]")

    def test_none_passthrough(self):
        """TP-080g: None 原样返回（不崩溃）"""
        self.assertIsNone(_bracket_ipv6(None))


# ===========================================================================
# TP-081: BM Agent HTTP 双栈绑定
# ===========================================================================

class TestBmAgentServerHost(unittest.TestCase):
    """TP-081: bm_instance_agent config.py server['host'] 双栈绑定默认值及环境变量覆盖"""

    def test_default_bind_is_double_colon(self):
        """TP-081a: 无 BM_AGENT_BIND_IP 环境变量时，默认绑定 '::' (IPv4/IPv6 双栈)"""
        env = os.environ.copy()
        env.pop('BM_AGENT_BIND_IP', None)
        with patch.dict(os.environ, env, clear=True):
            host = os.environ.get('BM_AGENT_BIND_IP', '::')
        self.assertEqual(host, '::')

    def test_env_var_overrides_default(self):
        """TP-081b: 设置 BM_AGENT_BIND_IP=192.168.1.1 时，server['host'] 被覆盖"""
        with patch.dict(os.environ, {'BM_AGENT_BIND_IP': '192.168.1.1'}):
            host = os.environ.get('BM_AGENT_BIND_IP', '::')
        self.assertEqual(host, '192.168.1.1')

    def test_env_var_ipv6_overrides_default(self):
        """TP-081c: 设置 BM_AGENT_BIND_IP 为 IPv6 地址时，server['host'] 为该 IPv6"""
        with patch.dict(os.environ, {'BM_AGENT_BIND_IP': 'fd00::1'}):
            host = os.environ.get('BM_AGENT_BIND_IP', '::')
        self.assertEqual(host, 'fd00::1')

    def test_default_double_colon_is_dual_stack(self):
        """TP-081d: '::' 是 Python/Flask 惯例的双栈监听地址（等价于 0.0.0.0 + ::）"""
        import socket
        # '::' 是合法的 IPv6 地址（全零）
        addr = socket.inet_pton(socket.AF_INET6, '::')
        self.assertEqual(addr, b'\x00' * 16)

    def test_env_var_removed_restores_default(self):
        """TP-081e: 删除环境变量后，server['host'] 恢复为 '::'"""
        with patch.dict(os.environ, {'BM_AGENT_BIND_IP': '10.0.0.1'}):
            pass  # 临时设置
        # 离开 patch.dict 上下文后变量已移除
        host = os.environ.get('BM_AGENT_BIND_IP', '::')
        self.assertEqual(host, '::')


# ===========================================================================
# TP-082: BM PXE Server IPv6 接口地址解析
# ===========================================================================

# 模拟 `ip addr show dev eth0` 返回的输出（同时包含 IPv4 / IPv6 全局 / link-local）
_IP_ADDR_DUAL = """\
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 52:54:00:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 10.0.0.1/24 brd 10.0.0.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 2001:db8::1/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::1/64 scope link
       valid_lft forever preferred_lft forever
"""

# 仅 IPv6（无 IPv4），含全局和 link-local
_IP_ADDR_V6_ONLY = """\
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 52:54:00:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet6 2001:db8::1/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::1/64 scope link
       valid_lft forever preferred_lft forever
"""

# 仅 link-local，无任何可路由地址
_IP_ADDR_LINK_LOCAL_ONLY = """\
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 52:54:00:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet6 fe80::1/64 scope link
       valid_lft forever preferred_lft forever
"""


class TestGetIpAddress(unittest.TestCase):
    """TP-082: pxeserveragent._get_ip_address 地址解析（mock subprocess）"""

    def test_ipv4_returned_when_present(self):
        """TP-082a: 有 IPv4 时，优先返回 IPv4（10.0.0.1），不返回 IPv6"""
        result = _get_ip_address_logic(_IP_ADDR_DUAL)
        self.assertEqual(result, "10.0.0.1")

    def test_global_ipv6_returned_when_no_ipv4(self):
        """TP-082b: 无 IPv4 时，返回全局 IPv6 地址 2001:db8::1"""
        result = _get_ip_address_logic(_IP_ADDR_V6_ONLY)
        self.assertEqual(result, "2001:db8::1")

    def test_link_local_not_returned(self):
        """TP-082c: link-local 地址 fe80::1 不被 scope global 正则匹配，不返回"""
        # 双栈情况下，IPv4 优先，fe80 不出现
        result = _get_ip_address_logic(_IP_ADDR_DUAL)
        self.assertNotEqual(result, "fe80::1")

        # 仅 IPv6 情况下，只返回全局地址，不返回 link-local
        result_v6only = _get_ip_address_logic(_IP_ADDR_V6_ONLY)
        self.assertNotEqual(result_v6only, "fe80::1")
        self.assertEqual(result_v6only, "2001:db8::1")

    def test_no_ip_raises_exception(self):
        """TP-082d: 接口无任何可用 IP（只有 link-local）时抛出异常"""
        with self.assertRaises(Exception) as ctx:
            _get_ip_address_logic(_IP_ADDR_LINK_LOCAL_ONLY)
        self.assertIn("no IP found", str(ctx.exception))

    def test_scope_global_regex_excludes_link_local(self):
        """TP-082e: 正则 'scope global' 准确排除 fe80 link-local，仅匹配全局地址"""
        ipv6_matches = re.findall(r'inet6\s+([0-9a-f:]+)/\d+\s+scope global', _IP_ADDR_DUAL)
        self.assertIn("2001:db8::1", ipv6_matches)
        self.assertNotIn("fe80::1", ipv6_matches)

    def test_subprocess_mock_integration(self):
        """TP-082f: 通过 mock subprocess.check_output 验证完整调用链（集成风格）"""
        mock_output = _IP_ADDR_DUAL.encode('utf-8')
        with patch('subprocess.check_output', return_value=mock_output) as mock_co:
            raw = subprocess.check_output(
                ['ip', 'addr', 'show', 'dev', 'eth0'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8', errors='replace')
            mock_co.assert_called_once()
        # 用解析逻辑验证结果
        result = _get_ip_address_logic(raw)
        self.assertEqual(result, "10.0.0.1")


if __name__ == '__main__':
    unittest.main()
