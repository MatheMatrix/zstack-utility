import os

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

NAIDIA_SRIOV_MANAGE_PATH = '/usr/lib/nvidia/sriov-manage'

def is_nvidia_pci_device(pci_info):
    # type: (dict) -> bool
    # ex:
    #   is_nvidia_pci_device(lspci_s('0000:00:04.0'))
    #   is_nvidia_pci_device(lspci()[0])
    return  pci_info.has_key('Vendor') and 'NVIDIA' in pci_info['Vendor'] or \
            pci_info.has_key('Device') and 'NVIDIA' in pci_info['Device'] or \
            pci_info.has_key('SVendor') and 'NVIDIA' in pci_info['SVendor']

def disable_nvidia_vgpu_by_sriov_manage(pci_info):
    # type: (dict) -> str | None
    # return: error message
    # ex:
    #   disable_nvidia_vgpu_by_sriov_manage(lspci_s('0000:00:04.0'))
    #   disable_nvidia_vgpu_by_sriov_manage(lspci()[0])
    return disable_nvidia_vgpu_address_by_sriov_manager(pci_info['Slot'])

def disable_nvidia_vgpu_address_by_sriov_manager(address):
    # type: (str) -> str | None
    # return: error message
    # ex:
    #   disable_nvidia_vgpu_address_by_sriov_manager('0000:00:04.0')
    sriov_manage_exists = os.path.exists(NAIDIA_SRIOV_MANAGE_PATH)
    if not sriov_manage_exists:
        return None

    r, _, stderr = bash.bash_roe("/usr/lib/nvidia/sriov-manage -d %s" % address)
    if r != 0:
        return 'Failed to disable vgpu device %s by sriov-manage: %s' % (address, stderr)
    return None

def enable_nvidia_vgpu_by_sriov_manage(pci_info):
    # type: (dict) -> str | None
    # return: error message
    # ex:
    #   enable_nvidia_vgpu_by_sriov_manage(lspci_s('0000:00:04.0'))
    #   enable_nvidia_vgpu_by_sriov_manage(lspci()[0])
    return enable_nvidia_vgpu_address_by_sriov_manage(pci_info['Slot'])

def enable_nvidia_vgpu_address_by_sriov_manage(address):
    # type: (str) -> str | None
    # return: error message
    # ex:
    #   enable_nvidia_vgpu_address_by_sriov_manage('0000:00:04.0')
    sriov_manage_exists = os.path.exists(NAIDIA_SRIOV_MANAGE_PATH)
    if not sriov_manage_exists:
        return 'Failed to enable vgpu device %s: sriov-manage not found' % address

    r, _, stderr = bash.bash_roe("/usr/lib/nvidia/sriov-manage -e %s" % address)
    if r != 0:
        return 'Failed to enable vgpu device %s by sriov-manage: %s' % (address, stderr)
    return None
