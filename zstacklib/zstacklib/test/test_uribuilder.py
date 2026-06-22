'''

@author: frank
'''
import unittest
from zstacklib.utils import http

class TestUriBuilder(unittest.TestCase):


    def test_build_url(self):
        url = 'http://localhost:7070/'
        builder = http.UriBuilder(url)
        builder.add_path('/connect')
        builder.add_path('/vm')
        ret = builder.build()
        self.assertEqual('http://localhost:7070/connect/vm/', ret)
        
    def test_build_url2(self):
        ret = http.build_url(('http', 'google.com', '8080', 'search'))
        self.assertEqual('http://google.com:8080/search/', ret)
        
    def test_build_url3(self):
        ret = http.build_url(('http', 'google.com', '8080', '/search/world/'))
        self.assertEqual('http://google.com:8080/search/world/', ret)
        
    def test_build_url4(self):
        url = 'http://localhost/'
        builder = http.UriBuilder(url)
        builder.add_path('/connect')
        builder.add_path('/vm')
        ret = builder.build()
        self.assertEqual('http://localhost:80/connect/vm/', ret)

    def test_build_url5(self):
        url = 'http://localhost/'
        builder = http.UriBuilder(url)
        ret = builder.build()
        self.assertEqual('http://localhost:80/', ret)

    def test_build_url_with_ipv6_host(self):
        ret = http.build_url(('http', 'fd11:5:5:29::220', '8080', '/zstack/api/'))
        self.assertEqual('http://[fd11:5:5:29::220]:8080/zstack/api/', ret)

    def test_build_url_with_bracketed_ipv6_host(self):
        ret = http.build_url(('http', '[fd11:5:5:29::220]', '8080', '/zstack/api/'))
        self.assertEqual('http://[fd11:5:5:29::220]:8080/zstack/api/', ret)

    def test_build_url_with_ipv6_uri(self):
        builder = http.UriBuilder('http://[fd11:5:5:29::220]:8080/zstack/api/')
        self.assertEqual('http://[fd11:5:5:29::220]:8080/zstack/api/', builder.build())

    def test_build_url_with_https_default_port(self):
        builder = http.UriBuilder('https://localhost/')
        self.assertEqual('https://localhost:443/', builder.build())

    def test_build_url_with_invalid_port(self):
        self.assertRaises(Exception, http.UriBuilder, 'http://localhost:abc/')


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
