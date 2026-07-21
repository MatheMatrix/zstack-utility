# encoding: utf-8

import unittest

import mock
from kvmagent.plugins import host_plugin


class TestHostPluginVfioMdev(unittest.TestCase):
    PCI_ADDRESS = "0000:3b:00.0"
    VERBOSE_COMMAND = "nvidia-smi vgpu -i %s -v -c" % PCI_ADDRESS
    SUPPORTED_COMMAND = "nvidia-smi vgpu -i %s -s" % PCI_ADDRESS
    CREATABLE_COMMAND = "nvidia-smi vgpu -i %s -c" % PCI_ADDRESS

    def setUp(self):
        self.plugin = host_plugin.HostPlugin()
        self.pci_to = host_plugin.PciDeviceTO()
        self.pci_to.pciDeviceAddress = self.PCI_ADDRESS

    def test_fallback_to_supported_types_when_creatable_query_fails(self):
        results = [
            (1, '', 'no creatable instances'),
            (0, 'vGPU Type ID : 239\nName : GRID L20-4Q\n', ''),
        ]

        with mock.patch.object(host_plugin.os.path, 'isdir', return_value=False), \
                mock.patch.object(host_plugin, 'bash_roe', side_effect=results) as run:
            supported = self.plugin._get_nvidia_vfio_mdev_info(self.pci_to)

        self.assertTrue(supported)
        self.assertEqual('VFIO_MDEV_VIRTUALIZABLE', self.pci_to.virtStatus)
        self.assertEqual(
            [mock.call(self.VERBOSE_COMMAND), mock.call(self.SUPPORTED_COMMAND)],
            run.call_args_list,
        )

    def test_return_unsupported_when_both_vgpu_queries_fail(self):
        results = [
            (1, '', 'no creatable instances'),
            (1, '', 'not supported'),
        ]

        with mock.patch.object(host_plugin.os.path, 'isdir', return_value=False), \
                mock.patch.object(host_plugin, 'bash_roe', side_effect=results) as run:
            supported = self.plugin._get_nvidia_vfio_mdev_info(self.pci_to)

        self.assertFalse(supported)
        self.assertEqual('', self.pci_to.virtStatus)
        self.assertEqual(
            [mock.call(self.VERBOSE_COMMAND), mock.call(self.SUPPORTED_COMMAND)],
            run.call_args_list,
        )

    def test_set_virtualizable_when_verbose_query_succeeds_without_sysfs_dirs(self):
        output = 'Header\nvGPU Type ID : 239\nName : GRID L20-4Q\n'

        with mock.patch.object(host_plugin.os.path, 'isdir', return_value=False), \
                mock.patch.object(host_plugin, 'bash_roe', return_value=(0, output, '')) as run:
            supported = self.plugin._get_nvidia_vfio_mdev_info(self.pci_to)

        self.assertTrue(supported)
        self.assertEqual('VFIO_MDEV_VIRTUALIZABLE', self.pci_to.virtStatus)
        self.assertEqual('239', self.pci_to.mdevSpecifications[0]['TypeId'])
        self.assertEqual('GRID L20-4Q', self.pci_to.mdevSpecifications[0]['Name'])
        self.assertEqual([mock.call(self.VERBOSE_COMMAND)], run.call_args_list)

    def test_keep_legacy_device_virtualizable_when_creatable_status_fails(self):
        legacy_path = '/sys/bus/pci/devices/%s/mdev_supported_types' % self.PCI_ADDRESS
        output = 'Header\nvGPU Type ID : 239\nName : GRID L20-4Q\n'

        with mock.patch.object(
                host_plugin.os.path, 'isdir', side_effect=lambda path: path == legacy_path), \
                mock.patch.object(
                    host_plugin, 'bash_roe',
                    side_effect=[(0, output, ''), (1, '', 'no creatable instances')],
                ) as run, \
                mock.patch.object(self.plugin, '_legacy_mdev') as legacy_mdev:
            supported = self.plugin._get_nvidia_vfio_mdev_info(self.pci_to)

        self.assertTrue(supported)
        self.assertEqual('VFIO_MDEV_VIRTUALIZABLE', self.pci_to.virtStatus)
        self.assertEqual(
            [mock.call(self.VERBOSE_COMMAND), mock.call(self.CREATABLE_COMMAND)],
            run.call_args_list,
        )
        legacy_mdev.assert_not_called()


if __name__ == '__main__':
    unittest.main()
