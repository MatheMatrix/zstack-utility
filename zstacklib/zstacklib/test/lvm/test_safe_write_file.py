import os
import time
import unittest
import mock
import stat
import logging
import re
from zstacklib.utils import linux
logger = logging.getLogger(__name__)

class TestCase(unittest.TestCase):
    def test(self):
        dest = "./iscsid.conf"
        with linux.CrashSafeFileEditor(dest) as content:
            content.text, _ = re.subn(r"^.*iscsid\.startup.*=.*$", "iscsid.startup = /bin/systemctl start iscsid.socket iscsiuio.socket",
                                      content.text, flags=re.MULTILINE)
        self.assertEqual(linux.read_file(dest).count("iscsid.startup = /bin/systemctl start iscsid.socket iscsiuio.socket"), 2)

        with linux.CrashSafeFileEditor(dest) as content:
            content.text, _ = re.subn(r"^.*xxxxxxxxx.*=.*$", "iscsid.startup = /bin/systemctl start iscsid.socket xxxxxxxxx",
                                      content.text, flags=re.MULTILINE)
        self.assertEqual(linux.read_file(dest).count("iscsid.startup = /bin/systemctl start iscsid.socket xxxxxxxxx"), 0)

        with linux.CrashSafeFileEditor(dest) as content:
            content.text, _ = re.subn(r"^.*iscsid\.startup.*=.*$", "iscsid.startup = /bin/systemctl start iscsid.socket xxxxxxxxx",
                                      content.text, flags=re.MULTILINE)
        self.assertEqual(linux.read_file(dest).count("iscsid.startup = /bin/systemctl start iscsid.socket xxxxxxxxx"), 2)

        os.remove(dest)
        with self.assertRaises(Exception) as e:
            with linux.CrashSafeFileEditor(dest) as content:
                content.text, _ = re.subn(r"^.*iscsid\.startup.*=.*$", "iscsid.startup = /bin/systemctl start iscsid.socket xxxxxxxxx",
                                          content.text, flags=re.MULTILINE)
        print(str(e))

        linux.touch_file(dest)
        with self.assertRaises(Exception) as ee:
            with linux.CrashSafeFileEditor(dest) as content:
                raise Exception("on purpose")

        print(str(ee))
if __name__ == '__main__':
    unittest.main()