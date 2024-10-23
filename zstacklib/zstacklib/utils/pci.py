from zstacklib.utils import bash

def fmt_pci_address(pci_device):
    # type: (dict) -> str
    domain = pci_device['domain'] if 'domain' in pci_device else 0
    return "%s:%s:%s.%s" % (format(domain, '04x'),
                            format(pci_device['bus'], '02x'),
                            format(pci_device['slot'], '02x'),
                            format(pci_device['function'], 'x'))

#   ex: lspci_s('0000:00:04.0') # equals to: lspci -s '0000:00:04.0'
#   output:
#   [
#       {
#           'Slot' : '0000:00:04.0',
#           'Vendor' : 'Intel Corporation',
#           'VendorId' : '8086',
#           'NUMANode' : '0',
#           'IOMMUGroup' : '0',
#           ...
#       }
#   ]
def lspci_s(option_slot):
    # type: (str) -> list[dict]
    r, o = bash.bash_ro('lspci -Dmmnnv -s ' + option_slot)
    if r != 0:
        return None
    return _parse_lspci(o)

def lspci():
    # type: () -> list[dict]
    r, o = bash.bash_ro('lspci -Dmmnnv')
    if r != 0:
        return None
    return _parse_lspci(o)

def lspci_s_or_throw(option_slot):
    # type: (str) -> list[dict]
    r, o, e = bash.bash_roe('lspci -Dmmnnv -s ' + option_slot)
    if r != 0:
        raise Exception('failed to execute command lspci: %s' % e)
    return _parse_lspci(o)

def lspci_or_throw():
    # type: () -> list[dict]
    r, o, e = bash.bash_roe('lspci -Dmmnnv')
    if r != 0:
        raise Exception('failed to execute command lspci: %s' % e)
    return _parse_lspci(o)

def _parse_lspci(o):
    # type: (str) -> list[dict]
    results = []
    current = {}
    lines = o.strip().split('\n') # type: list[str]
    lines.extend([''])

    for line in lines:
        colon_index = line.find(':') # type: int
        if colon_index < 0:
            if len(current) > 0:
                results.append(current)
                current = {}
                continue

        key = line[ : colon_index] # type: str
        value = line[colon_index + 1 :].strip() # type: str

        if key == 'Slot':
            current['Slot'] = value
        elif key == "Class":
            bracket_index = value.index('[')
            current['Class'] = value[0 : bracket_index].strip()
            current['ClassId'] = value[bracket_index + 1 : -1]
        elif key == "Vendor":
            bracket_index = value.index('[')
            current['Vendor'] = value[0 : bracket_index].strip()
            current['VendorId'] = value[bracket_index + 1 : -1]
        elif key == "Device":
            bracket_index = value.index('[')
            current['Device'] = value[0 : bracket_index].strip()
            current['DeviceId'] = value[bracket_index + 1 : -1]
        elif key == "SVendor":
            bracket_index = value.index('[')
            current['SVendor'] = value[0 : bracket_index].strip()
            current['SVendorId'] = value[bracket_index + 1 : -1]
        elif key == "SDevice":
            bracket_index = value.index('[')
            current['SDevice'] = value[0 : bracket_index].strip()
            current['SDeviceId'] = value[bracket_index + 1 : -1]
        else:
            current[key] = value
    return results
