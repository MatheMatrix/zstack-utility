'''

@author: Frank
'''
import unittest
from zstacklib.utils import linux

class Test(unittest.TestCase):


    def testName(self):
        linux.create_bridge('testbr0', 'eth0')


if __name__ == "__main__":
    #import sys;sys.path_hooks = ['', 'Test.testName']
    unittest.main()