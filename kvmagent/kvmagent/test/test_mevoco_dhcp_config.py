import os
import shutil
import tempfile
import unittest

from kvmagent.plugins import mevoco


class DhcpInfo(object):
    def __init__(self, mac, ip, ip6=None):
        self.mac = mac
        self.ip = ip
        self.ip6 = ip6


class TestMevocoDhcpConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dhcp_path = os.path.join(self.temp_dir, 'hosts.dhcp')
        self.option_path = os.path.join(self.temp_dir, 'hosts.option')
        self.dns_path = os.path.join(self.temp_dir, 'hosts.dns')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_erase_configurations_batch_for_zstac_85312(self):
        plugin = mevoco.Mevoco()

        with open(self.dhcp_path, 'w') as fd:
            fd.write('fa:16:3e:00:00:01,set:fa163e000001,172.26.104.200,vm1,infinite\n')
            fd.write('fa:16:3e:00:00:02,set:fa163e000002,172.26.104.201,vm2,infinite\n')
            fd.write('\n')
        with open(self.option_path, 'w') as fd:
            fd.write('tag:fa163e000001,option:router,172.26.104.1\n')
            fd.write('tag:fa163e000002,option:router,172.26.104.1\n')
            fd.write('\n')
        with open(self.dns_path, 'w') as fd:
            fd.write('172.26.104.200 vm1\n')
            fd.write('fd00::200 vm1\n')
            fd.write('172.26.104.201 vm2\n')
            fd.write('fd00::201 vm2\n')
            fd.write('\n')

        plugin._erase_configurations_batch([
            DhcpInfo('fa:16:3e:00:00:01', '172.26.104.200', 'fd00::200')
        ], self.dhcp_path, self.dns_path, self.option_path)

        with open(self.dhcp_path) as fd:
            dhcp_content = fd.read()
        with open(self.option_path) as fd:
            option_content = fd.read()
        with open(self.dns_path) as fd:
            dns_content = fd.read()

        self.assertNotIn('fa:16:3e:00:00:01', dhcp_content)
        self.assertNotIn('172.26.104.200', dhcp_content)
        self.assertIn('fa:16:3e:00:00:02', dhcp_content)
        self.assertNotIn('fa163e000001', option_content)
        self.assertIn('fa163e000002', option_content)
        self.assertNotIn('172.26.104.200 vm1', dns_content)
        self.assertNotIn('fd00::200 vm1', dns_content)
        self.assertIn('172.26.104.201 vm2', dns_content)
        self.assertIn('fd00::201 vm2', dns_content)


if __name__ == '__main__':
    unittest.main()
