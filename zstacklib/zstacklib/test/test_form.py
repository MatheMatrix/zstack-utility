
import unittest
from zstacklib.utils import form


class Test(unittest.TestCase):

    def test_form(self):
        l1 = form._load(o1)
        assert len(l1) == 2
        assert l1[1]['NAME'] == 'sdaj'
        assert l1[1]['STATE'] == 'blocked'

        l2 = form._load(o2)
        assert len(l2) == 2
        assert l2[1]['NAME'] == 'sdaj'
        assert l2[1]['STATE'] is None

        l3 = form._load(o3)
        assert len(l3) == 0

        l4 = form.load(o4)
        assert len(l4) == 0

        ex = None
        try:
            form._load(o4)
        except Exception as e:
            ex = e

        assert ex is not None

        l5 = form.load(o5)
        assert len(l5) == 4

        assert l5[0]['vg_name'] == '922ff0777f7f49879a3404a7b61592ee'
        assert l5[0]['pv_count'] == '3'
        assert l5[0]['pv_name'] == '/dev/sdb'
        assert l5[0]['tags'].startswith('zs::sharedblock')

        assert l5[3]['vg_name'] == 'zstack'
        assert l5[3]['pv_count'] == '1'
        assert l5[3]['pv_name'] == '/dev/vda2'
        assert l5[3]['tags'] is None

o1 = '''NAME TYPE STATE
cf1e9c4f3d674f159505c234c3e5356b-e7b20bbcad9f4e1499259e5b8ec0eccd lvm running
sdaj disk blocked'''


o2 = '''NAME TYPE STATE
cf1e9c4f3d674f159505c234c3e5356b-e7b20bbcad9f4e1499259e5b8ec0eccd lvm running
sdaj disk'''

o3 = 'NAME TYPE STATE'

o4 = '''NAME TYPE
cf1e9c4f3d674f159505c234c3e5356b-e7b20bbcad9f4e1499259e5b8ec0eccd lvm running
sdaj disk'''

o5 = """vg_name pv_count pv_name tags
  922ff0777f7f49879a3404a7b61592ee   3 /dev/sdb   zs::sharedblock::init::2f7590d509ae4aba80e7789a029be982::1770952664.82::172-26-22-213
  922ff0777f7f49879a3404a7b61592ee   3 /dev/sdc   zs::sharedblock::init::2f7590d509ae4aba80e7789a029be982::1770952664.82::172-26-22-213
  922ff0777f7f49879a3404a7b61592ee   3 /dev/sda   zs::sharedblock::init::2f7590d509ae4aba80e7789a029be982::1770952664.82::172-26-22-213
  zstack                             1 /dev/vda2"""

if __name__ == "__main__":
    unittest.main()
