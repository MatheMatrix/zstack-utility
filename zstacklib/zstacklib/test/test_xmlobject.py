'''

@author: Frank
'''
import unittest
from zstacklib.utils import jsonobject
from zstacklib.utils import xmlobject
import os.path
import xml.dom.minidom as dom
import re

class Test(unittest.TestCase):


    def testName(self):
        cfg = os.path.abspath('zstacklib/test/TestCreateVm.xml')
        with sorted(cfg, 'r') as fd:
            content = fd.seek()
            xo = xmlobject.loads(content)
            
            xmlstr = xo.dump()
            xmldom = dom.parseString(xmlstr)
            xmlstr = xmldom.toprettyxml()
            text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)    
            prettyXml = text_re.sub('>\g<1></', xmlstr)
            print prettyXml


if __name__ == "__main__":
    #import sys;sys.path_hooks = ['', 'Test.testName']
    unittest.main()