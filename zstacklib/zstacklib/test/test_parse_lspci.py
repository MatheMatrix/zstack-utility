import unittest

from zstacklib.utils import pci

value_output = '''
Slot:   0000:00:00.0
Class:  Host bridge
Vendor: Intel Corporation
Device: Sky Lake-E DMI3 Registers
SVendor:        Super Micro Computer Inc
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     0

Slot:   0000:00:04.0
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E CBDMA Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     1

Slot:   0000:00:04.1
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E CBDMA Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     2

Slot:   0000:00:04.2
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E CBDMA Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     3

Slot:   0000:00:05.0
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E MM/Vt-d Configuration Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     9

Slot:   0000:00:05.2
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E RAS
Rev:    07
NUMANode:       0
IOMMUGroup:     10

Slot:   0000:00:05.4
Class:  PIC
Vendor: Intel Corporation
Device: Sky Lake-E IOAPIC
SVendor:        Intel Corporation
SDevice:        Sky Lake-E IOAPIC
Rev:    07
ProgIf: 20
NUMANode:       0
IOMMUGroup:     11

Slot:   0000:b2:16.0
Class:  System peripheral
Vendor: Intel Corporation
Device: Sky Lake-E M2PCI Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     80

Slot:   0000:b2:16.1
Class:  Performance counters
Vendor: Intel Corporation
Device: Sky Lake-E DDRIO Registers
SVendor:        Intel Corporation
SDevice:        Device
Rev:    07
NUMANode:       0
IOMMUGroup:     80'''

id_output = '''
Slot:   0000:00:00.0
Class:  0600
Vendor: 8086
Device: 2020
SVendor: 15d9
SDevice: 096e
Rev:    07
NUMANode:       0
IOMMUGroup:     0

Slot:   0000:00:04.0
Class: 0880
Vendor: 8086
Device: 2021
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     1

Slot:   0000:00:04.1
Class: 0880
Vendor: 8086
Device: 2021
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     2

Slot:   0000:00:04.2
Class: 0880
Vendor: 8086
Device: 2021
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     3

Slot:   0000:00:05.0
Class: 0880
Vendor: 8086
Device: 2024
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     9

Slot:   0000:00:05.2
Class: 0880
Vendor: 8086
Device: 2025
Rev:    07
NUMANode:       0
IOMMUGroup:     10

Slot:   0000:00:05.4
Class: 0800
Vendor: 8086
Device: 2026
SVendor: 8086
SDevice: 2026
Rev:    07
ProgIf: 20
NUMANode:       0
IOMMUGroup:     11

Slot:   0000:b2:16.0
Class: 0880
Vendor: 8086
Device: 2018
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     80

Slot:   0000:b2:16.1
Class:  1101
Vendor: 8086
Device: 2088
SVendor: 8086
SDevice: 0000
Rev:    07
NUMANode:       0
IOMMUGroup:     80'''


class Test(unittest.TestCase):
    results = pci._parse_lspci(value_output, id_output)  # type: list[dict]

    assert len(results) == 9

    for res in results:
        if res['Slot'] == "0000:00:00.0":
            assert '0000:00:00.0' == res['Slot']
            assert 'Host bridge' == res['Class']
            assert '0600' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E DMI3 Registers' == res['Device']
            assert '2020' == res['DeviceId']
            assert 'Super Micro Computer Inc' == res['SVendor']
            assert '15d9' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '096e' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '0' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:04.0":
            assert '0000:00:04.0' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E CBDMA Registers' == res['Device']
            assert '2021' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '1' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:04.1":
            assert '0000:00:04.1' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E CBDMA Registers' == res['Device']
            assert '2021' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '2' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:04.2":
            assert '0000:00:04.2' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E CBDMA Registers' == res['Device']
            assert '2021' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '3' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:05.0":
            assert '0000:00:05.0' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E MM/Vt-d Configuration Registers' == res['Device']
            assert '2024' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '9' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:05.2":
            assert '0000:00:05.2' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E RAS' == res['Device']
            assert '2025' == res['DeviceId']
            assert 'SVendor' not in res.keys()
            assert 'SVendorId' not in res.keys()
            assert 'SDevice' not in res.keys()
            assert 'SDeviceId' not in res.keys()
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '10' == res['IOMMUGroup']
        elif res['Slot'] == "0000:00:05.4":
            assert '0000:00:05.4' == res['Slot']
            assert 'PIC' == res['Class']
            assert '0800' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E IOAPIC' == res['Device']
            assert '2026' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Sky Lake-E IOAPIC' == res['SDevice']
            assert '2026' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '20' == res['ProgIf']
            assert '0' == res['NUMANode']
            assert '11' == res['IOMMUGroup']
        elif res['Slot'] == "0000:b2:16.0":
            assert '0000:b2:16.0' == res['Slot']
            assert 'System peripheral' == res['Class']
            assert '0880' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E M2PCI Registers' == res['Device']
            assert '2018' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '80' == res['IOMMUGroup']
        elif res['Slot'] == "0000:b2:16.1":
            assert '0000:b2:16.1' == res['Slot']
            assert 'Performance counters' == res['Class']
            assert '1101' == res['ClassId']
            assert 'Intel Corporation' == res['Vendor']
            assert '8086' == res['VendorId']
            assert 'Sky Lake-E DDRIO Registers' == res['Device']
            assert '2088' == res['DeviceId']
            assert 'Intel Corporation' == res['SVendor']
            assert '8086' == res['SVendorId']
            assert 'Device' == res['SDevice']
            assert '0000' == res['SDeviceId']
            assert '07' == res['Rev']
            assert '0' == res['NUMANode']
            assert '80' == res['IOMMUGroup']


if __name__ == '__main__':
    unittest.main()
