import pytest
import unittest

from kvmagent.test.utils import pytest_utils
from zstacklib.utils import pci

context = {}

__ENV_SETUP__ = {
    'self': {}
}

def error_message(message):
    return '%s, context: %s' % (message, context)

output = '''
Slot:   0000:00:00.0
Class:  Host bridge [0600]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E DMI3 Registers [2020]
SVendor:        Super Micro Computer Inc [15d9]
SDevice:        Device [096e]
Rev:    07
NUMANode:       0
IOMMUGroup:     0

Slot:   0000:00:04.0
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E CBDMA Registers [2021]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     1

Slot:   0000:00:04.1
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E CBDMA Registers [2021]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     2

Slot:   0000:00:04.2
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E CBDMA Registers [2021]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     3

Slot:   0000:00:05.0
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E MM/Vt-d Configuration Registers [2024]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     9

Slot:   0000:00:05.2
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E RAS [2025]
Rev:    07
NUMANode:       0
IOMMUGroup:     10

Slot:   0000:00:05.4
Class:  PIC [0800]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E IOAPIC [2026]
SVendor:        Intel Corporation [8086]
SDevice:        Sky Lake-E IOAPIC [2026]
Rev:    07
ProgIf: 20
NUMANode:       0
IOMMUGroup:     11

Slot:   0000:b2:16.0
Class:  System peripheral [0880]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E M2PCI Registers [2018]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     80

Slot:   0000:b2:16.1
Class:  Performance counters [1101]
Vendor: Intel Corporation [8086]
Device: Sky Lake-E DDRIO Registers [2088]
SVendor:        Intel Corporation [8086]
SDevice:        Device [0000]
Rev:    07
NUMANode:       0
IOMMUGroup:     80'''

class TestParseLspci(unittest.TestCase, pytest_utils.PytestExtension):
    @pytest.mark.run(order=1)
    @pytest_utils.ztest_decorater
    def test_lspci(self):
        results = pci._parse_lspci(output) # type: list[dict]
        context['results'] = results
        self.assertEqual(9, len(results), error_message("expect results.length = 9"))

        self.assertEqual('0000:00:00.0',      results[0]['Slot'],           error_message("failed to check results[0]"))
        self.assertEqual('Host bridge',       results[0]['Class'],          error_message("failed to check results[0]"))
        self.assertEqual('0600',              results[0]['ClassId'],        error_message("failed to check results[0]"))
        self.assertEqual('Intel Corporation', results[0]['Vendor'],         error_message("failed to check results[0]"))
        self.assertEqual('8086',              results[0]['VendorId'],       error_message("failed to check results[0]"))
        self.assertEqual('Sky Lake-E DMI3 Registers', results[0]['Device'], error_message("failed to check results[0]"))
        self.assertEqual('2020',              results[0]['DeviceId'],       error_message("failed to check results[0]"))
        self.assertEqual('Super Micro Computer Inc', results[0]['SVendor'], error_message("failed to check results[0]"))
        self.assertEqual('15d9',              results[0]['SVendorId'],      error_message("failed to check results[0]"))
        self.assertEqual('Device',            results[0]['SDevice'],        error_message("failed to check results[0]"))
        self.assertEqual('096e',              results[0]['SDeviceId'],      error_message("failed to check results[0]"))
        self.assertEqual('07',                results[0]['Rev'],            error_message("failed to check results[0]"))
        self.assertEqual('0',                 results[0]['NUMANode'],       error_message("failed to check results[0]"))
        self.assertEqual('0',                 results[0]['IOMMUGroup'],     error_message("failed to check results[0]"))

        self.assertEqual('0000:00:04.0',      results[1]['Slot'],           error_message("failed to check results[1]"))
        self.assertEqual('System peripheral', results[1]['Class'],          error_message("failed to check results[1]"))
        self.assertEqual('0880',              results[1]['ClassId'],        error_message("failed to check results[1]"))
        self.assertEqual('Intel Corporation', results[1]['Vendor'],         error_message("failed to check results[1]"))
        self.assertEqual('8086',              results[1]['VendorId'],       error_message("failed to check results[1]"))
        self.assertEqual('Sky Lake-E CBDMA Registers',results[1]['Device'], error_message("failed to check results[1]"))
        self.assertEqual('2021',              results[1]['DeviceId'],       error_message("failed to check results[1]"))
        self.assertEqual('Intel Corporation', results[1]['SVendor'],        error_message("failed to check results[1]"))
        self.assertEqual('8086',              results[1]['SVendorId'],      error_message("failed to check results[1]"))
        self.assertEqual('Device',            results[1]['SDevice'],        error_message("failed to check results[1]"))
        self.assertEqual('0000',              results[1]['SDeviceId'],      error_message("failed to check results[1]"))
        self.assertEqual('07',                results[1]['Rev'],            error_message("failed to check results[1]"))
        self.assertEqual('0',                 results[1]['NUMANode'],       error_message("failed to check results[1]"))
        self.assertEqual('1',                 results[1]['IOMMUGroup'],     error_message("failed to check results[1]"))

        self.assertEqual('0000:00:04.1',      results[2]['Slot'],           error_message("failed to check results[2]"))
        self.assertEqual('System peripheral', results[2]['Class'],          error_message("failed to check results[2]"))
        self.assertEqual('0880',              results[2]['ClassId'],        error_message("failed to check results[2]"))
        self.assertEqual('Intel Corporation', results[2]['Vendor'],         error_message("failed to check results[2]"))
        self.assertEqual('8086',              results[2]['VendorId'],       error_message("failed to check results[2]"))
        self.assertEqual('Sky Lake-E CBDMA Registers',results[2]['Device'], error_message("failed to check results[2]"))
        self.assertEqual('2021',              results[2]['DeviceId'],       error_message("failed to check results[2]"))
        self.assertEqual('Intel Corporation', results[2]['SVendor'],        error_message("failed to check results[2]"))
        self.assertEqual('8086',              results[2]['SVendorId'],      error_message("failed to check results[2]"))
        self.assertEqual('Device',            results[2]['SDevice'],        error_message("failed to check results[2]"))
        self.assertEqual('0000',              results[2]['SDeviceId'],      error_message("failed to check results[2]"))
        self.assertEqual('07',                results[2]['Rev'],            error_message("failed to check results[2]"))
        self.assertEqual('0',                 results[2]['NUMANode'],       error_message("failed to check results[2]"))
        self.assertEqual('2',                 results[2]['IOMMUGroup'],     error_message("failed to check results[2]"))

        self.assertEqual('0000:00:04.2',      results[3]['Slot'],           error_message("failed to check results[3]"))
        self.assertEqual('System peripheral', results[3]['Class'],          error_message("failed to check results[3]"))
        self.assertEqual('0880',              results[3]['ClassId'],        error_message("failed to check results[3]"))
        self.assertEqual('Intel Corporation', results[3]['Vendor'],         error_message("failed to check results[3]"))
        self.assertEqual('8086',              results[3]['VendorId'],       error_message("failed to check results[3]"))
        self.assertEqual('Sky Lake-E CBDMA Registers',results[3]['Device'], error_message("failed to check results[3]"))
        self.assertEqual('2021',              results[3]['DeviceId'],       error_message("failed to check results[3]"))
        self.assertEqual('Intel Corporation', results[3]['SVendor'],        error_message("failed to check results[3]"))
        self.assertEqual('8086',              results[3]['SVendorId'],      error_message("failed to check results[3]"))
        self.assertEqual('Device',            results[3]['SDevice'],        error_message("failed to check results[3]"))
        self.assertEqual('0000',              results[3]['SDeviceId'],      error_message("failed to check results[3]"))
        self.assertEqual('07',                results[3]['Rev'],            error_message("failed to check results[3]"))
        self.assertEqual('0',                 results[3]['NUMANode'],       error_message("failed to check results[3]"))
        self.assertEqual('3',                 results[3]['IOMMUGroup'],     error_message("failed to check results[3]"))

        self.assertEqual('0000:00:05.0',      results[4]['Slot'],           error_message("failed to check results[4]"))
        self.assertEqual('System peripheral', results[4]['Class'],          error_message("failed to check results[4]"))
        self.assertEqual('0880',              results[4]['ClassId'],        error_message("failed to check results[4]"))
        self.assertEqual('Intel Corporation', results[4]['Vendor'],         error_message("failed to check results[4]"))
        self.assertEqual('8086',              results[4]['VendorId'],       error_message("failed to check results[4]"))
        self.assertEqual('Sky Lake-E MM/Vt-d Configuration Registers', results[4]['Device'], error_message("failed to check results[4]"))
        self.assertEqual('2024',              results[4]['DeviceId'],       error_message("failed to check results[4]"))
        self.assertEqual('Intel Corporation', results[4]['SVendor'],        error_message("failed to check results[4]"))
        self.assertEqual('8086',              results[4]['SVendorId'],      error_message("failed to check results[4]"))
        self.assertEqual('Device',            results[4]['SDevice'],        error_message("failed to check results[4]"))
        self.assertEqual('0000',              results[4]['SDeviceId'],      error_message("failed to check results[4]"))
        self.assertEqual('07',                results[4]['Rev'],            error_message("failed to check results[4]"))
        self.assertEqual('0',                 results[4]['NUMANode'],       error_message("failed to check results[4]"))
        self.assertEqual('9',                 results[4]['IOMMUGroup'],     error_message("failed to check results[4]"))

        self.assertEqual('0000:00:05.2',      results[5]['Slot'],           error_message("failed to check results[5]"))
        self.assertEqual('System peripheral', results[5]['Class'],          error_message("failed to check results[5]"))
        self.assertEqual('0880',              results[5]['ClassId'],        error_message("failed to check results[5]"))
        self.assertEqual('Intel Corporation', results[5]['Vendor'],         error_message("failed to check results[5]"))
        self.assertEqual('8086',              results[5]['VendorId'],       error_message("failed to check results[5]"))
        self.assertEqual('Sky Lake-E RAS',    results[5]['Device'],         error_message("failed to check results[5]"))
        self.assertEqual('2025',              results[5]['DeviceId'],       error_message("failed to check results[5]"))
        self.assertFalse(results[5].has_key('SVendor'),                     error_message("failed to check results[5]"))
        self.assertFalse(results[5].has_key('SVendorId'),                   error_message("failed to check results[5]"))
        self.assertFalse(results[5].has_key('SDevice'),                     error_message("failed to check results[5]"))
        self.assertFalse(results[5].has_key('SDeviceId'),                   error_message("failed to check results[5]"))
        self.assertEqual('07',                results[5]['Rev'],            error_message("failed to check results[5]"))
        self.assertEqual('0',                 results[5]['NUMANode'],       error_message("failed to check results[5]"))
        self.assertEqual('10',                results[5]['IOMMUGroup'],     error_message("failed to check results[5]"))

        self.assertEqual('0000:00:05.4',      results[6]['Slot'],           error_message("failed to check results[6]"))
        self.assertEqual('PIC',               results[6]['Class'],          error_message("failed to check results[6]"))
        self.assertEqual('0800',              results[6]['ClassId'],        error_message("failed to check results[6]"))
        self.assertEqual('Intel Corporation', results[6]['Vendor'],         error_message("failed to check results[6]"))
        self.assertEqual('8086',              results[6]['VendorId'],       error_message("failed to check results[6]"))
        self.assertEqual('Sky Lake-E IOAPIC', results[6]['Device'],         error_message("failed to check results[6]"))
        self.assertEqual('2026',              results[6]['DeviceId'],       error_message("failed to check results[6]"))
        self.assertEqual('Intel Corporation', results[6]['SVendor'],        error_message("failed to check results[6]"))
        self.assertEqual('8086',              results[6]['SVendorId'],      error_message("failed to check results[6]"))
        self.assertEqual('Sky Lake-E IOAPIC', results[6]['SDevice'],        error_message("failed to check results[6]"))
        self.assertEqual('2026',              results[6]['SDeviceId'],      error_message("failed to check results[6]"))
        self.assertEqual('07',                results[6]['Rev'],            error_message("failed to check results[6]"))
        self.assertEqual('20',                results[6]['ProgIf'],         error_message("failed to check results[6]"))
        self.assertEqual('0',                 results[6]['NUMANode'],       error_message("failed to check results[6]"))
        self.assertEqual('11',                results[6]['IOMMUGroup'],     error_message("failed to check results[6]"))

        self.assertEqual('0000:b2:16.0',      results[7]['Slot'],           error_message("failed to check results[7]"))
        self.assertEqual('System peripheral', results[7]['Class'],          error_message("failed to check results[7]"))
        self.assertEqual('0880',              results[7]['ClassId'],        error_message("failed to check results[7]"))
        self.assertEqual('Intel Corporation', results[7]['Vendor'],         error_message("failed to check results[7]"))
        self.assertEqual('8086',              results[7]['VendorId'],       error_message("failed to check results[7]"))
        self.assertEqual('Sky Lake-E M2PCI Registers', results[7]['Device'],error_message("failed to check results[7]"))
        self.assertEqual('2018',              results[7]['DeviceId'],       error_message("failed to check results[7]"))
        self.assertEqual('Intel Corporation', results[7]['SVendor'],        error_message("failed to check results[7]"))
        self.assertEqual('8086',              results[7]['SVendorId'],      error_message("failed to check results[7]"))
        self.assertEqual('Device',            results[7]['SDevice'],        error_message("failed to check results[7]"))
        self.assertEqual('0000',              results[7]['SDeviceId'],      error_message("failed to check results[7]"))
        self.assertEqual('07',                results[7]['Rev'],            error_message("failed to check results[7]"))
        self.assertEqual('0',                 results[7]['NUMANode'],       error_message("failed to check results[7]"))
        self.assertEqual('80',                results[7]['IOMMUGroup'],     error_message("failed to check results[7]"))

        self.assertEqual('0000:b2:16.1',      results[8]['Slot'],           error_message("failed to check results[8]"))
        self.assertEqual('Performance counters', results[8]['Class'],       error_message("failed to check results[8]"))
        self.assertEqual('1101',              results[8]['ClassId'],        error_message("failed to check results[8]"))
        self.assertEqual('Intel Corporation', results[8]['Vendor'],         error_message("failed to check results[8]"))
        self.assertEqual('8086',              results[8]['VendorId'],       error_message("failed to check results[8]"))
        self.assertEqual('Sky Lake-E DDRIO Registers', results[8]['Device'],error_message("failed to check results[8]"))
        self.assertEqual('2088',              results[8]['DeviceId'],       error_message("failed to check results[8]"))
        self.assertEqual('Intel Corporation', results[8]['SVendor'],        error_message("failed to check results[8]"))
        self.assertEqual('8086',              results[8]['SVendorId'],      error_message("failed to check results[8]"))
        self.assertEqual('Device',            results[8]['SDevice'],        error_message("failed to check results[8]"))
        self.assertEqual('0000',              results[8]['SDeviceId'],      error_message("failed to check results[8]"))
        self.assertEqual('07',                results[8]['Rev'],            error_message("failed to check results[8]"))
        self.assertEqual('0',                 results[8]['NUMANode'],       error_message("failed to check results[8]"))
        self.assertEqual('80',                results[8]['IOMMUGroup'],     error_message("failed to check results[8]"))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
