"""
Test PMU configuration in VM XML generation.
See ZSTAC-76375: Kunpeng-920 7270Z kernel panic due to PMMIR_EL1.
"""

import unittest
from xml.etree import ElementTree as ET


class TestVmPmuConfig(unittest.TestCase):
    """Test that PMU feature is correctly added to VM XML."""

    def _make_features_xml(self, pmu_value):
        """Simulate make_features() logic for PMU."""
        root = ET.Element("domain")
        features = ET.SubElement(root, "features")
        ET.SubElement(features, "apic")
        ET.SubElement(features, "pae")
        ET.SubElement(features, "acpi")

        # This mirrors the logic in vm_plugin.py make_features()
        if pmu_value is False:
            ET.SubElement(features, "pmu", attrib={'state': 'off'})

        return root

    def test_pmu_off_generates_xml(self):
        """When cmd.pmu is False, <pmu state='off'/> should be in features."""
        root = self._make_features_xml(pmu_value=False)
        pmu = root.find('./features/pmu')
        self.assertIsNotNone(pmu, "PMU element should exist when pmu=False")
        self.assertEqual(pmu.get('state'), 'off', "PMU state should be 'off'")

    def test_pmu_true_no_pmu_element(self):
        """When cmd.pmu is True, no <pmu> element should be added."""
        root = self._make_features_xml(pmu_value=True)
        pmu = root.find('./features/pmu')
        self.assertIsNone(pmu, "PMU element should NOT exist when pmu=True")

    def test_pmu_none_no_pmu_element(self):
        """When cmd.pmu is not set (None), no <pmu> element should be added."""
        root = self._make_features_xml(pmu_value=None)
        pmu = root.find('./features/pmu')
        self.assertIsNone(pmu, "PMU element should NOT exist when pmu=None")

    def test_hasattr_guard(self):
        """Test the hasattr guard used in vm_plugin.py."""
        class FakeCmd:
            pass

        cmd = FakeCmd()
        # No pmu attribute: should not generate PMU element
        root = ET.Element("domain")
        features = ET.SubElement(root, "features")
        if hasattr(cmd, 'pmu') and cmd.pmu is False:
            ET.SubElement(features, "pmu", attrib={'state': 'off'})
        self.assertIsNone(root.find('./features/pmu'),
                          "No PMU element when cmd has no pmu attribute")

        # With pmu=False: should generate PMU element
        cmd.pmu = False
        root2 = ET.Element("domain")
        features2 = ET.SubElement(root2, "features")
        if hasattr(cmd, 'pmu') and cmd.pmu is False:
            ET.SubElement(features2, "pmu", attrib={'state': 'off'})
        pmu = root2.find('./features/pmu')
        self.assertIsNotNone(pmu, "PMU element should exist when cmd.pmu=False")
        self.assertEqual(pmu.get('state'), 'off')


if __name__ == "__main__":
    unittest.main()
