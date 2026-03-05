# -*- coding: utf-8 -*-
"""
Unit tests for _parse_watchers logic in cephagent.py.

Tests the watcher parsing without importing the full ceph agent
(which has heavy dependencies like rados, rbd, xms_client).
"""
import unittest
from unittest import mock
import simplejson


# Replicate the _parse_watchers logic for isolated testing
def _parse_watchers(path, shell_call_fn):
    """Standalone version of CephAgent._parse_watchers for testing."""
    try:
        output = shell_call_fn('timeout 10 rbd status --format json %s' % path)
        data = simplejson.loads(output)
    except Exception:
        output = shell_call_fn('timeout 10 rbd status %s' % path)
        raw = []
        infos = []
        if output:
            for line in output.splitlines():
                if "watcher=" not in line:
                    continue
                line = line.lstrip()
                raw.append(line)
                ip = ""
                try:
                    rest = line.split("watcher=")[1]
                    ip = rest.split(":")[0]
                except (IndexError, ValueError):
                    pass
                infos.append({"ip": ip, "address": "", "clientId": "", "cookie": ""})
        return raw, infos

    watchers = data.get("watchers", [])
    raw_list = []
    info_list = []
    for w in watchers:
        address = w.get("address", "")
        client_id = w.get("client", "")
        cookie = w.get("cookie", "")
        ip = address.split(":")[0] if ":" in address else ""
        raw_list.append("watcher=%s client.%s cookie=%s" % (
            address, client_id, cookie))
        info_list.append({
            "ip": ip,
            "address": address,
            "clientId": str(client_id),
            "cookie": str(cookie)
        })
    return raw_list, info_list


class TestParseWatchers(unittest.TestCase):

    def test_json_format_single_watcher(self):
        json_output = simplejson.dumps({
            "watchers": [
                {"address": "10.0.0.1:0/12345", "client": 6789, "cookie": 1}
            ]
        })
        shell_fn = mock.Mock(return_value=json_output)
        raw, infos = _parse_watchers("pool/vol-001", shell_fn)

        self.assertEqual(len(raw), 1)
        self.assertEqual(len(infos), 1)
        self.assertIn("10.0.0.1:0/12345", raw[0])
        self.assertEqual(infos[0]["ip"], "10.0.0.1")
        self.assertEqual(infos[0]["address"], "10.0.0.1:0/12345")
        self.assertEqual(infos[0]["clientId"], "6789")
        self.assertEqual(infos[0]["cookie"], "1")

    def test_json_format_multiple_watchers(self):
        json_output = simplejson.dumps({
            "watchers": [
                {"address": "10.0.0.1:0/111", "client": 100, "cookie": 1},
                {"address": "10.0.0.2:0/222", "client": 200, "cookie": 2}
            ]
        })
        shell_fn = mock.Mock(return_value=json_output)
        raw, infos = _parse_watchers("pool/vol-001", shell_fn)

        self.assertEqual(len(raw), 2)
        self.assertEqual(len(infos), 2)
        self.assertEqual(infos[0]["ip"], "10.0.0.1")
        self.assertEqual(infos[1]["ip"], "10.0.0.2")

    def test_json_format_no_watchers(self):
        json_output = simplejson.dumps({"watchers": []})
        shell_fn = mock.Mock(return_value=json_output)
        raw, infos = _parse_watchers("pool/vol-001", shell_fn)

        self.assertEqual(len(raw), 0)
        self.assertEqual(len(infos), 0)

    def test_text_fallback_single_watcher(self):
        """When JSON fails, fall back to text parsing."""
        text_output = "Watchers:\n\twatcher=10.0.0.5:0/999 client.123 cookie=1\n"

        def shell_fn(cmd):
            if "--format json" in cmd:
                raise Exception("not supported")
            return text_output

        raw, infos = _parse_watchers("pool/vol-001", shell_fn)

        self.assertEqual(len(raw), 1)
        self.assertIn("watcher=10.0.0.5:0/999", raw[0])
        self.assertEqual(infos[0]["ip"], "10.0.0.5")

    def test_text_fallback_empty(self):
        def shell_fn(cmd):
            if "--format json" in cmd:
                raise Exception("not supported")
            return ""

        raw, infos = _parse_watchers("pool/vol-001", shell_fn)
        self.assertEqual(len(raw), 0)
        self.assertEqual(len(infos), 0)

    def test_text_fallback_multiple_watchers(self):
        text_output = (
            "Watchers:\n"
            "\twatcher=10.0.0.1:0/111 client.100 cookie=1\n"
            "\twatcher=10.0.0.2:0/222 client.200 cookie=2\n"
        )

        def shell_fn(cmd):
            if "--format json" in cmd:
                raise Exception("not supported")
            return text_output

        raw, infos = _parse_watchers("pool/vol-001", shell_fn)
        self.assertEqual(len(raw), 2)
        self.assertEqual(infos[0]["ip"], "10.0.0.1")
        self.assertEqual(infos[1]["ip"], "10.0.0.2")

    def test_json_called_first(self):
        """Verify JSON format is attempted before text."""
        json_output = simplejson.dumps({
            "watchers": [
                {"address": "10.0.0.1:0/111", "client": 100, "cookie": 1}
            ]
        })
        shell_fn = mock.Mock(return_value=json_output)
        _parse_watchers("pool/vol-001", shell_fn)

        # should only call once (JSON succeeded, no fallback)
        shell_fn.assert_called_once()
        self.assertIn("--format json", shell_fn.call_args[0][0])

    def test_stale_watcher_ip_extraction(self):
        """Verify IP extraction works for filtering stale watchers."""
        json_output = simplejson.dumps({
            "watchers": [
                {"address": "192.168.1.100:0/111", "client": 1, "cookie": 1},
                {"address": "192.168.1.200:0/222", "client": 2, "cookie": 2}
            ]
        })
        shell_fn = mock.Mock(return_value=json_output)
        _, infos = _parse_watchers("pool/vol-001", shell_fn)

        # simulate Java-side filtering: disconnected host = 192.168.1.100
        disconnected_ips = {"192.168.1.100"}
        active = [i for i in infos if i["ip"] not in disconnected_ips]

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["ip"], "192.168.1.200")


if __name__ == "__main__":
    unittest.main()
