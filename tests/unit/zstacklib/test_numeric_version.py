import unittest

from zstacklib.utils.version import NumericVersion


class TestNumericVersion(unittest.TestCase):

    def test_standard_version(self):
        self.assertTrue(NumericVersion('5.2.0') >= NumericVersion('5.2'))
        self.assertTrue(NumericVersion('2.5.0') >= NumericVersion('2.5'))
        self.assertFalse(NumericVersion('2.4') >= NumericVersion('2.5'))

    def test_non_standard_version_with_suffix(self):
        # e.g., qemu-ga version '5.2.0-8.el8'
        self.assertTrue(NumericVersion('5.2.0-8.el8') >= NumericVersion('5.2'))
        self.assertFalse(NumericVersion('5.2.0-8.el8') < NumericVersion('2.5'))
        self.assertTrue(NumericVersion('5.2.0-8.el8') < NumericVersion('100.0'))

    def test_version_with_letters_in_middle(self):
        # e.g., '2.a.1' -> [2, 1]
        self.assertTrue(NumericVersion('2.a.1') < NumericVersion('2.5'))

    def test_version_with_distro_suffix(self):
        # e.g., '108.1.0.el8_10.1'
        self.assertTrue(NumericVersion('108.1.0.el8_10.1') >= NumericVersion('5.2'))
        self.assertFalse(NumericVersion('108.1.0.el8_10.1') < NumericVersion('100.0'))

    def test_kernel_version(self):
        # e.g., '4.18.0-305.el8.x86_64'
        self.assertTrue(NumericVersion('4.18.0-305.el8.x86_64') >= NumericVersion('3.10.0'))
        self.assertTrue(NumericVersion('4.18.0-305.el8.x86_64') >= NumericVersion('4.18.0'))

    def test_release_version_with_build_number(self):
        # e.g., '6.2.0-902'
        self.assertTrue(NumericVersion('6.2.0-902') >= NumericVersion('6.2.0'))
        self.assertFalse(NumericVersion('6.2.0-902') < NumericVersion('5.2'))

    def test_edk2_version(self):
        # edk2-ovmf versions like '20230517gitXXX-2.el8'
        threshold = NumericVersion('20220126gitbb1bba3d77-4')
        self.assertTrue(NumericVersion('20230517gitXXX-2.el8') >= threshold)
        self.assertFalse(NumericVersion('20200101gitYYY-1.el8') >= threshold)

    def test_equal_versions(self):
        self.assertTrue(NumericVersion('5.2') == NumericVersion('5.2'))
        self.assertTrue(NumericVersion('1.0.0') == NumericVersion('1.0.0'))

    def test_chained_comparison(self):
        # Same pattern used in do_attach_ssh_key_pair
        ga_version = '5.2.0-8.el8'
        self.assertTrue(
            NumericVersion('100.0') > NumericVersion(ga_version) >= NumericVersion('5.2')
        )

    def test_below_minimum(self):
        self.assertTrue(NumericVersion('1.9') < NumericVersion('2.5'))
        self.assertTrue(NumericVersion('2.4.9') < NumericVersion('2.5'))

    def test_repr(self):
        v = NumericVersion('5.2.0-8.el8')
        self.assertIn('5.2.0-8.el8', repr(v))

    def test_version_list_contains_only_ints(self):
        v = NumericVersion('5.2.0-8.el8')
        for item in v.version:
            self.assertIsInstance(item, int)


if __name__ == '__main__':
    unittest.main()
