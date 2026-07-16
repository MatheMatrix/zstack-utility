# -*- coding: utf-8 -*-

import unittest
from xml.etree import ElementTree as ET

from kvmagent.plugins import vm_plugin


class TestMigrateDomainXml(unittest.TestCase):
    def _build_domain_new_xml(self, domain_xml):
        vm = vm_plugin.Vm.__new__(vm_plugin.Vm)
        vm.get_migratable_xml = lambda: domain_xml
        return vm._build_domain_new_xml({})

    def test_split_legacy_rbd_cdrom_snapshot(self):
        domain_xml = """
<domain type='kvm'>
  <name>vm-uuid</name>
  <devices>
    <disk type='network' device='cdrom'>
      <driver name='qemu' type='raw'/>
      <source protocol='rbd' name='pool/image@snapshot'>
        <host name='172.24.1.1' port='6789'/>
      </source>
      <target dev='hdc' bus='ide'/>
      <readonly/>
    </disk>
  </devices>
</domain>
"""
        disks, dest_xml = self._build_domain_new_xml(domain_xml)

        self.assertEqual([], disks)
        root = ET.fromstring(dest_xml)
        source = root.find("devices/disk/source")
        self.assertEqual("pool/image", source.attrib["name"])
        self.assertEqual("snapshot", source.find("snapshot").attrib["name"])

    def test_keep_non_rbd_network_disk_snapshot_unchanged(self):
        domain_xml = """
<domain type='kvm'>
  <name>vm-uuid</name>
  <devices>
    <disk type='network' device='disk'>
      <driver name='qemu' type='raw'/>
      <source protocol='cbd' name='pool/image@snapshot'>
        <host name='172.24.1.1' port='7777'/>
      </source>
      <target dev='vda' bus='virtio'/>
    </disk>
  </devices>
</domain>
"""
        disks, dest_xml = self._build_domain_new_xml(domain_xml)

        self.assertIsNone(disks)
        self.assertIsNone(dest_xml)


if __name__ == "__main__":
    unittest.main()
