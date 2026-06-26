import os
import tempfile
import unittest

from kvmagent.plugins import host_pushgateway


class TestHostPushgateway(unittest.TestCase):
    def test_get_auth_header_reads_lighttpd_config(self):
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, b'setenv.add-request-header = ( "Authorization" => "Basic custom" )')
            os.close(fd)

            self.assertEqual("Basic custom", host_pushgateway.get_auth_header([path]))
        finally:
            if fd:
                try:
                    os.close(fd)
                except OSError:
                    pass
            os.remove(path)

    def test_get_auth_header_falls_back_to_product_default(self):
        self.assertEqual(
            host_pushgateway.DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER,
            host_pushgateway.get_auth_header([])
        )

    def test_make_push_metrics_headers_adds_basic_auth(self):
        headers = host_pushgateway.make_push_metrics_headers()

        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual(host_pushgateway.DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER, headers["Authorization"])

    def test_make_get_metrics_headers_adds_basic_auth(self):
        headers = host_pushgateway.make_get_metrics_headers()

        self.assertEqual("text/plain", headers["Content-Type"])
        self.assertEqual(host_pushgateway.DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER, headers["Authorization"])

    def test_make_delete_metric_headers_adds_basic_auth(self):
        headers = host_pushgateway.make_delete_metric_headers()

        self.assertEqual(host_pushgateway.DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER, headers["Authorization"])


if __name__ == "__main__":
    unittest.main()
