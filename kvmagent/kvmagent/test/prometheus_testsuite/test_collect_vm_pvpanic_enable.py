try:
    from unittest import mock
except ImportError:
    import mock

from unittest import TestCase

from kvmagent.test.utils.stub import *

init_kvmagent()

from kvmagent.plugins import prometheus


class FakeQemuProcess(object):
    def __init__(self, cmdline):
        self._cmdline = cmdline

    def cmdline(self):
        return self._cmdline


class TestCollectVmPvpanicEnable(TestCase):
    VM_UUID = '3bf341c5402046ce8105ab27ad85e61f'

    def _collect_value(self, device_arg):
        process = FakeQemuProcess([
            '/usr/libexec/qemu-kvm',
            'guest=%s,debug-threads=on' % self.VM_UUID,
            '-device',
            device_arg,
        ])
        with mock.patch.object(prometheus, 'fetch_vm_qemu_processes', return_value=[process]):
            metrics = prometheus.collect_vm_pvpanic_enable_in_domain_xml()

        samples = metrics[0].samples
        self.assertEqual(1, len(samples))
        self.assertEqual(self.VM_UUID, samples[0].labels['vmUuid'])
        return samples[0].value

    def test_collects_legacy_pvpanic_device(self):
        self.assertEqual(1, self._collect_value('pvpanic,ioport=1285'))
        self.assertEqual(1, self._collect_value('pvpanic,id=pvpanic0,ioport=0x505'))

    def test_collects_json_pvpanic_device_from_qemu_cmdline(self):
        self.assertEqual(1, self._collect_value('{"driver":"pvpanic","ioport":1285}'))
        self.assertEqual(1, self._collect_value('{"driver":"pvpanic","ioport":"0x505"}'))

    def test_does_not_collect_other_or_invalid_devices(self):
        self.assertEqual(0, self._collect_value('{"driver":"pvpanic-pci","ioport":1285}'))
        self.assertEqual(0, self._collect_value('{"driver":"pvpanic","ioport":1286}'))
        self.assertEqual(0, self._collect_value('{"driver":"pvpanic","ioport":'))
        self.assertEqual(0, self._collect_value('{"driver":"virtio-balloon-pci"}'))

    def test_ignores_pvpanic_outside_device_arguments(self):
        self.assertFalse(prometheus.is_pvpanic_enabled_in_qemu_cmdline([
            '-name',
            '{"driver":"pvpanic","ioport":1285}',
            '-fw_cfg',
            'pvpanic,ioport=1285',
        ]))
