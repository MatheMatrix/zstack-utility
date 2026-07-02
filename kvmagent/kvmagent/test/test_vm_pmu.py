import unittest
import xml.etree.ElementTree as etree

from kvmagent.plugins.vm_plugin import e
from kvmagent.plugins.vm_plugin import make_pmu_feature


class TestVmPmuConfig(unittest.TestCase):
    def test_pmu_off_generates_xml(self):
        root, features = self._new_domain_with_features()
        cmd = self._cmd(False)

        make_pmu_feature(cmd, features)

        pmu = root.find('./features/pmu')
        self.assertIsNotNone(pmu)
        self.assertEqual('off', pmu.get('state'))

    def test_pmu_true_omits_pmu_element(self):
        root, features = self._new_domain_with_features()
        cmd = self._cmd(True)

        make_pmu_feature(cmd, features)

        self.assertIsNone(root.find('./features/pmu'))

    def test_missing_pmu_omits_pmu_element(self):
        root, features = self._new_domain_with_features()

        make_pmu_feature(object(), features)

        self.assertIsNone(root.find('./features/pmu'))

    def test_pmu_element_stays_under_features(self):
        root, features = self._new_domain_with_features()
        cmd = self._cmd(False)

        make_pmu_feature(cmd, features)

        children = [child.tag for child in features]
        self.assertEqual(['apic', 'pae', 'acpi', 'pmu'], children)
        self.assertIn('<pmu state="off"', etree.tostring(root).decode('utf-8'))

    @staticmethod
    def _new_domain_with_features():
        root = etree.Element('domain')
        features = e(root, 'features')
        e(features, 'apic')
        e(features, 'pae')
        e(features, 'acpi')
        return root, features

    @staticmethod
    def _cmd(pmu):
        class Cmd(object):
            pass

        cmd = Cmd()
        cmd.pmu = pmu
        return cmd


if __name__ == '__main__':
    unittest.main()
