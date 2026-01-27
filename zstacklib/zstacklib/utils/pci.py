import os
import platform
import re

from zstacklib.utils import log, linux, sizeunit
import xml.etree.ElementTree as ET

from zstacklib.utils.bash import bash_roe

logger = log.get_logger(__name__)

_pci_device_cache = {}

# Vendor name mapping for simplification (lightweight, no GPU vendor system dependency)
# Maps full vendor names from lspci to simplified names
_VENDOR_NAME_MAPPING = {
    'Intel Corporation': 'Intel',
    'Advanced Micro Devices': 'AMD',
    'NVIDIA Corporation': 'NVIDIA',
    'Chengdu Haiguang': 'Haiguang',
    'Haiguang': 'Haiguang',
    'Huawei': 'Huawei',
    'TianShu': 'TianShu',
    'Vastai': 'Vastai',
    'Enflame': 'Enflame',
    'Alibaba': 'Alibaba',
    'Kunlunxin': 'Kunlunxin',
}

# Vendor ID mapping (for cases where name matching fails)
# Format: lowercase vendor_id -> simplified name
_VENDOR_ID_MAPPING = {
    '1ded': 'Alibaba',  # Alibaba vendor ID
    '1e3e': 'TianShu',  # TianShu vendor ID
    '2057': 'Kunlunxin',  # Kunlunxin vendor ID
}


def simplify_vendor_name(name, vendor_id=None):
    """
    Simplify PCI vendor name using lightweight configuration mapping.

    This function does not depend on the GPU vendor system, making it suitable
    for use in a generic PCI library. It uses simple string matching and
    configuration dictionaries.

    Args:
        name: Full vendor name from lspci (e.g., "NVIDIA Corporation")
        vendor_id: Optional vendor ID (e.g., "10de" for NVIDIA)

    Returns:
        str: Simplified vendor name (e.g., "NVIDIA"), or cleaned original name
    """
    if not name:
        return name

    # Try name-based matching first
    name_lower = name.lower()
    for full_name, short_name in _VENDOR_NAME_MAPPING.items():
        if full_name.lower() in name_lower:
            return short_name

    # If name matching fails and vendor_id is provided, try vendor_id mapping
    if vendor_id:
        vendor_id_lower = vendor_id.lower().strip()
        if vendor_id_lower in _VENDOR_ID_MAPPING:
            return _VENDOR_ID_MAPPING[vendor_id_lower]

    # Fallback: clean common suffixes
    result = name.replace('Co., Ltd ', '').replace('Corporation', '').strip()
    return result


def normalize_pci_address(pci_address):
    """
    Normalize PCI address to standard format for exact matching.

    Handles various input formats:
    - "00000000:3B:00.0" -> "0000:3b:00.0"
    - "0000:3B:00.0" -> "0000:3b:00.0"
    - "3B:00.0" -> "0000:3b:00.0"
    - "0x0000:0x3b:0x00.0x0" -> "0000:3b:00.0"

    Args:
        pci_address: PCI address string in any format

    Returns:
        str: Normalized PCI address in format "xxxx:xx:xx.x" (lowercase), or None if invalid
    """
    if not pci_address:
        return None

    # Convert to string and strip whitespace
    addr = str(pci_address).strip()
    if not addr:
        return None

    # Remove 0x prefixes if present
    addr = re.sub(r'0x', '', addr, flags=re.IGNORECASE)

    # Parse components
    parts = addr.split(':')
    if len(parts) == 2:
        # Format: "3B:00.0" -> bus:slot.function (domain defaults to "0000")
        # Check if parts[1] contains '.' to distinguish from invalid formats
        if '.' in parts[1]:
            domain = '0000'
            bus = parts[0]
            bus_slot_func = parts[1]  # This is slot.function
        else:
            # Invalid format
            return None
    elif len(parts) == 3:
        # Format: "0000:3B:00.0" or "00000000:3B:00.0"
        domain = parts[0]
        bus = parts[1]
        bus_slot_func = parts[2]  # This is slot.function
    else:
        # Invalid format
        return None

    # Normalize domain (remove leading zeros, pad to 4 chars)
    try:
        domain_num = int(domain, 16)
        domain = format(domain_num, '04x')
    except ValueError:
        return None

    # Handle 8-char domain (e.g., "00000000" -> "0000")
    if len(domain) == 8:
        domain = domain[4:]

    # Parse slot.function
    if '.' not in bus_slot_func:
        return None

    slot, function = bus_slot_func.split('.', 1)

    # Normalize bus, slot, function
    try:
        bus_num = int(bus, 16)
        slot_num = int(slot, 16)
        func_num = int(function, 16)
        bus = format(bus_num, '02x')
        slot = format(slot_num, '02x')
        function = format(func_num, 'x')
    except ValueError:
        return None

    return "%s:%s:%s.%s" % (domain, bus, slot, function)


def get_cached_device(pci_address):
    return _pci_device_cache.get(pci_address)


def clear_pci_cache():
    _pci_device_cache.clear()


def update_cache_devices(devices_dict):
    _pci_device_cache.clear()
    _pci_device_cache.update(devices_dict)


def fmt_pci_address(pci_device):
    # type: (dict) -> str
    domain = pci_device['domain'] if 'domain' in pci_device else 0
    return "%s:%s:%s.%s" % (format(domain, '04x'),
                            format(pci_device['bus'], '02x'),
                            format(pci_device['slot'], '02x'),
                            format(pci_device['function'], 'x'))


PCI_IOV_NUM_BAR = 6
PCI_BASE_ADDRESS_MEM_TYPE_MASK = 0x06
PCI_BASE_ADDRESS_MEM_TYPE_32 = 0x00  # 32 bit address
PCI_BASE_ADDRESS_MEM_TYPE_64 = 0x04  # 64 bit address
PCI_DEVICES_ROOT = "/sys/bus/pci/devices"

DEFAULT_PCDPCIMMIO64SIZE_ON_32BIT = 0x100000000
DEFAULT_PCDPCIMMIO64SIZE_MIN_SIZE = 0x800000000
DEFAULT_ARM_PCI_MMIO64_SIZE = 0x8000000000
max_addressable_memory_32bit = 2 * 1024 * 1024
max_addressable_memory_64bit = 2 * 1024 * 1024


class MemoryResource:
    def __init__(self, start, end, flags, path):
        self.start = start
        self.end = end
        self.flags = flags
        self.path = path

    def __str__(self):
        return "start: %s, end: %s, flags: %s, path: %s" % (self.start, self.end, self.flags, self.path)

    def __repr__(self):
        return str(self)


def calc_next_power_of_2(n):
    """
    Calculate the next power of 2 for a given number.

    :param n: The input number
    :return: The next power of 2
    """
    n -= 1
    n |= n >> 1
    n |= n >> 2
    n |= n >> 4
    n |= n >> 8
    n |= n >> 16
    n |= n >> 32
    n += 1
    return n


def need_config_pcimmio():
    if platform.machine() == 'aarch64':
        if max_addressable_memory_64bit <= DEFAULT_ARM_PCI_MMIO64_SIZE:
            logger.info("max_addressable_memory %s is less than DEFAULT_ARM_PCI_MMIO64_SIZE %s" %
                        (max_addressable_memory_64bit, DEFAULT_ARM_PCI_MMIO64_SIZE))
            return False
    else:
        if max_addressable_memory_64bit <= DEFAULT_PCDPCIMMIO64SIZE_ON_32BIT:
            logger.info("max_addressable_memory %s is less than DEFAULT_PCDPCIMMIO64SIZE_ON_32BIT %s" %
                        (max_addressable_memory_64bit, DEFAULT_PCDPCIMMIO64SIZE_ON_32BIT))
            return False

    return True


def get_bars_max_addressable_memory():
    if max_addressable_memory_64bit is None:
        logger.warn(
            "max_addressable_memory is None, please reconnect host and try again")

    if platform.machine() == 'aarch64':
        return "%sG" % sizeunit.Byte.toGigaByte(calc_next_power_of_2(max_addressable_memory_64bit))

    if max_addressable_memory_64bit < DEFAULT_PCDPCIMMIO64SIZE_MIN_SIZE:
        return DEFAULT_PCDPCIMMIO64SIZE_MIN_SIZE / 1024 / 1024

    return max_addressable_memory_64bit / 1024 / 1024


def calculate_max_addressable_memory(pci_devices):
    """
    Calculate max addressable memory for all GPU devices.

    Optimized: Batch query all GPU information once, then filter by PCI address.
    Uses gpu.get_all_gpu_infos_by_pci() for efficient batch processing.
    """
    global max_addressable_memory_32bit
    global max_addressable_memory_64bit
    max32bit = 2 * 1024 * 1024
    max64bit = 2 * 1024 * 1024

    # Batch query all GPU information once (optimized approach)
    # Uses unified gpu.get_all_gpu_infos_by_pci() interface for efficient batch processing
    try:
        from zstacklib.utils import gpu
        gpu_info_map = gpu.get_all_gpu_infos_by_pci()
    except Exception as e:
        logger.debug("Failed to batch query GPU infos: %s" % str(e))
        gpu_info_map = {}

    for dev in pci_devices:
        # Normalize PCI address for lookup
        normalized_pci = normalize_pci_address(dev.pciDeviceAddress)
        if not normalized_pci:
            continue

        # Check if this PCI address is in the GPU info map (O(1) lookup)
        if normalized_pci not in gpu_info_map:
            continue

        mem_size_32bit, mem_size_64bit = get_total_addressable_memory(
            get_pci_resources(dev.pciDeviceAddress))
        logger.info("get pci device: %s, name: %s, max addressable memory: %s" %
                    (dev.pciDeviceAddress, dev.name, mem_size_64bit))
        max32bit += calc_next_power_of_2(mem_size_32bit)
        max64bit += calc_next_power_of_2(mem_size_64bit)

    max_addressable_memory_32bit = max32bit * 2
    max_addressable_memory_64bit = max64bit
    logger.info("calculate max addressable memory: 32bit: "
                "%s, 64bit: %s", max_addressable_memory_32bit, max_addressable_memory_64bit)


def get_total_addressable_memory(resources):
    # type: (dict) -> (int, int)
    """
        Calculate the total addressable memory for 32-bit and 64-bit addresses.

        :param resources: A dictionary of memory resources
        :return: A tuple containing the 32-bit and 64-bit addressable memory sizes
    """
    mem_size_32bit = 0
    mem_size_64bit = 0

    for key in resources.keys():
        # The PCIe spec only defines 5 BARs per device, we're
        # discarding everything after the 5th entry of the resources
        # file, see lspci.c
        if key >= PCI_IOV_NUM_BAR:
            break

        region = resources[key]
        flags = region.flags & PCI_BASE_ADDRESS_MEM_TYPE_MASK
        mem_size = (region.end - region.start) + 1

        if flags == PCI_BASE_ADDRESS_MEM_TYPE_32:
            mem_size_32bit += mem_size
        if flags == PCI_BASE_ADDRESS_MEM_TYPE_64:
            mem_size_64bit += mem_size

    return mem_size_32bit, mem_size_64bit


def get_pci_resources(device_address):
    device_path = os.path.join(PCI_DEVICES_ROOT, device_address)
    return parse_resources(device_path)


def parse_resources(device_path):
    resources = {}
    try:
        with open(os.path.join(device_path, "resource"), "r") as f:
            for i, line in enumerate(f):
                start, end, flags = map(
                    lambda x: int(x, 16), line.strip().split())
                if start != 0 or end != 0:
                    resources[i] = MemoryResource(
                        start, end, flags, os.path.join(device_path, "resource"))
    except Exception as e:
        logger.warn(linux.get_exception_stacktrace())
        logger.warn("Error parsing resources for %s: %s" %
                    (device_path, str(e)))

    logger.info("get pci device[path: %s],resources: %s" %
                (device_path, resources))
    return resources


def get_pci_passthrough_mapping(vm_dom):
    pci_mapping = {}
    xml_tree = ET.fromstring(vm_dom.XMLDesc())
    for hostdev in xml_tree.find('devices').findall('hostdev'):
        source_address = hostdev.find('source/address')
        host_domain = source_address.get('domain').replace('0x', '')
        host_bus = source_address.get('bus').replace('0x', '')
        host_slot = source_address.get('slot').replace('0x', '')
        host_function = source_address.get('function').replace('0x', '')
        host_pci_address = "{}:{}:{}.{}".format(
            host_domain, host_bus, host_slot, host_function)

        vm_address = hostdev.find('address')
        vm_domain = vm_address.get('domain').replace('0x', '')
        vm_bus = vm_address.get('bus').replace('0x', '')
        vm_slot = vm_address.get('slot').replace('0x', '')
        vm_function = vm_address.get('function').replace('0x', '')
        vm_pci_address = "{}:{}:{}.{}".format(
            vm_domain, vm_bus, vm_slot, vm_function)
        pci_mapping[vm_pci_address] = host_pci_address

    return pci_mapping


def get_mdev_passthrough_mapping(vm_dom):
    mdev_mapping = {}
    xml_tree = ET.fromstring(vm_dom.XMLDesc())
    for hostdev in xml_tree.find('devices').findall('hostdev'):
        if hostdev.get('type') != 'mdev':
            continue

        source_uuid = hostdev.find('source/address')
        mdev_uuid = source_uuid.get('uuid').replace('-', '')

        vm_address = hostdev.find('address')
        vm_domain = vm_address.get('domain').replace('0x', '')
        vm_bus = vm_address.get('bus').replace('0x', '')
        vm_slot = vm_address.get('slot').replace('0x', '')
        vm_function = vm_address.get('function').replace('0x', '')
        vm_mdev_address = "{}:{}:{}.{}".format(
            vm_domain, vm_bus, vm_slot, vm_function)
        mdev_mapping[mdev_uuid] = vm_mdev_address

    return mdev_mapping


def get_vm_pci_device_address_by_host_address(vm_dom, host_address):
    pci_mapping = get_pci_passthrough_mapping(vm_dom)
    host_to_vm_mapping = {v: k for k, v in pci_mapping.items()}
    return host_to_vm_mapping.get(host_address)


def get_pci_device_ids():
    # Get IDs using -Dmmnv (without second 'n' to avoid truncation)
    return bash_roe("lspci -Dmmnv")


def get_pci_device_names():
    # Get names using -Dmmv (without 'nn' to get full names)
    return bash_roe("lspci -Dmmv")


def collect_pci_devices_with_dependencies(pciDeviceAddress):
    devices = []
    base_address = pciDeviceAddress.rsplit('.', 1)[0]
    r, o, e = bash_roe("lspci -s %s" % base_address)
    if r != 0:
        return devices

    for line in o.splitlines():
        device = line.split()[0]
        full_address = "{}:{}".format(pciDeviceAddress.split(':')[0], device)
        if full_address != pciDeviceAddress:
            devices.append(full_address)
    return devices
