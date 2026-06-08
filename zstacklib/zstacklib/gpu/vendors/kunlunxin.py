# -*- coding: utf-8 -*-
"""
Kunlunxin XPU Vendor Implementation (Python 2/3 Compatible)

xpu-smi -q full output sample (single XPU block, xpu-smi -q --id=00000000:01:00.0):
--------
==============XPUSMI LOG==============

Timestamp                                 : Tue Feb  3 18:20:01 2026
Driver Version                            : 5.0.21.26
XPU-RT Version                            : 10.2

Attached XPUs                             : 2
XPU 00000000:01:00.0
    Product Name                          : P800 PCIe
    Product Brand                         : KUNLUNXIN
    Product Architecture                  : KL3
    Serial Number                         : 02K0MA0258D0007R
    XPU UUID                              : GPU-420716f2-9928-5108-a5b2-e6b7cf36b37c
    Minor Number                          : 0
    PCIe Id                               : 3
    XPU Part Number                       : B00100300110211
    Firmware Version
        PBL Version                       : 1.0
        PCIE Version                      : 2.14
        SBL Version                       : 1.54
        ALL Version                       : 1.0.2.14.1.54
        CPLD Version                      : 2.0
    PCI
        Bus                               : 0x01
        Device                            : 0x00
        Function                          : 0x0
        Domain                            : 0x0000
        Device Id                         : 0x36862057
        Bus Id                            : 00000000:01:00.0
        Sub System Id                     : 0x00010001
        XPU Link Info
            PCIe Generation
                Max                       : 4
                Current                   : 3
            Link Width
                Max                       : 16x
                Current                   : 16x
    Memory Usage
        Total                             : 98304 MiB
        Reserved                          : 0 MiB
        Used                              : 0 MiB
        Free                              : 98304 MiB
    L3 Usage
        Total                             : 96 MiB
        Reserved                          : 0 MiB
        Used                              : 0 MiB
        Free                              : 96 MiB
    Utilization
        Xpu                               : 0 %
    Ecc Mode
        Current                           : Enabled
        Pending                           : Enabled
    ECC Errors
        Volatile
            DRAM Correctable              : 0
            DRAM Uncorrectable            : 0
        Aggregate
            DRAM Correctable              : 0
            DRAM Uncorrectable            : 0
    Temperature
        XPU Current Temp                  : 46 C
    Power Readings
        Enforced Power Limit              : 350.00 W
        Power Draw                        : 76.00 W
    Clocks
        Cluster                           : 1450 MHz
        CDNN                              : 1450 MHz
    Processes                             : None
--------
Parse by key: value (key = line.split(":", 1)[0].strip()). Fields we use:
Product Name, Serial Number, Bus Id (under PCI), Memory Usage Total/Used,
Enforced Power Limit, Power Draw, XPU Current Temp.
"""

import re

from zstacklib.utils import log
from zstacklib.utils.bash import bash_roe, bash_ro
from zstacklib.gpu.base import (
    GPUBase,
    GPUInfo,
    GPUMetrics,
    register_gpu_vendor
)

logger = log.get_logger(__name__)


@register_gpu_vendor
class Kunlunxin(GPUBase):
    """
    Kunlunxin XPU vendor implementation.
    """

    # ==========================================================================
    # Vendor Identification
    # ==========================================================================

    VENDOR_NAME = "Kunlunxin"
    VENDOR_ENUM_NAME = "Kunlunxin"
    VENDOR_IDS = {"2057"}
    PCI_NAME_KEYWORDS = {"2057", "Kunlunxin", "KUNLUNXIN"}
    CLI_TOOL = "xpu-smi"

    DEVICE_TYPES = {"Processing accelerators", "3D controller", "Communication controller"}
    IS_GPU_VENDOR = True

    # ==========================================================================
    # PCI-only fallback (no xpu-smi): match by vendor_id + class
    # ==========================================================================

    @classmethod
    def get_pci_only_candidates(cls, device_ids, device_names):
        """
        When xpu-smi is not available, identify Kunlunxin XPU by PCI: vendor 2057,
        class Processing accelerators or 3D controller.
        """
        from zstacklib.utils.pci import normalize_pci_address

        result = []
        vendor_ids_lower = {v.lower() for v in cls.VENDOR_IDS}
        for slot in device_ids:
            if slot not in device_names or not slot.endswith('.0'):
                continue
            ids = device_ids[slot]
            names = device_names[slot]
            vendor_id = (ids.get('Vendor') or '').strip().lower()
            class_name = (names.get('Class') or '').strip()
            if vendor_id not in vendor_ids_lower:
                continue
            if class_name not in cls.DEVICE_TYPES:
                continue
            normalized = normalize_pci_address(slot)
            if normalized:
                result.append((normalized, {"isDriverLoaded": False}))
        return result

    # ==========================================================================
    # Multi-Device Enumeration
    # ==========================================================================

    @classmethod
    def get_xpu_ids(cls):
        """
        Get list of XPU IDs from xpu-smi -L output.

        Output format:
            XPU 0: 00000000:21:00.0
            XPU 1: 00000000:22:00.0
        """
        r, o, _ = bash_roe("xpu-smi -L")
        if r != 0:
            return []

        xpu_ids = []
        for line in o.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^XPU\s+(\d+):', line)
            if match:
                xpu_ids.append(match.group(1))
        return xpu_ids

    # ==========================================================================
    # Basic Information Collection
    # ==========================================================================

    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        """
        This is not used directly - we override get_basic_info.
        """
        return "xpu-smi -L"

    @classmethod
    def get_basic_info_cmd_for_xpu(cls, xpu_id, is_windows=False):
        """Get command for specific XPU ID"""
        cmd = "xpu-smi -q --id={0}".format(xpu_id)
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd

    @classmethod
    def parse_basic_info(cls, output):
        """
        Parse xpu-smi -q output for a single XPU.
        Full output sample: see module docstring at top of this file.
        """
        gpu_infos = []
        gpu_info_dict = {}
        current_section = None

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Track current section (lines without ':' are section headers)
            if ":" not in line:
                current_section = line
                continue

            parts = line.split(":", 1)
            if len(parts) < 2:
                continue
            key = parts[0].strip()
            value = parts[1].strip()

            if key == "Serial Number":
                gpu_info_dict["serial_number"] = value
            elif key == "Bus Id":
                gpu_info_dict["pci_address"] = cls.normalize_pci_address(
                    value.lower())
            elif current_section == "Memory Usage":
                if key == "Total":
                    gpu_info_dict["memory"] = value
                elif key == "Used":
                    gpu_info_dict["memoryUsage"] = value
            elif key == "Enforced Power Limit":
                gpu_info_dict["power"] = value
            elif key == "Power Draw":
                gpu_info_dict["powerDraw"] = value
            elif key == "XPU Current Temp":
                gpu_info_dict["temperature"] = value

        if gpu_info_dict.get("pci_address"):
            gpu_info = GPUInfo(
                pci_address=gpu_info_dict.get("pci_address", ""),
                memory=gpu_info_dict.get("memory"),
                power=gpu_info_dict.get(
                    "power") or gpu_info_dict.get("powerDraw"),
                serial_number=gpu_info_dict.get("serial_number"),
            )
            gpu_infos.append(gpu_info)

        return gpu_infos

    @classmethod
    def get_basic_info(cls):
        """
        Override to handle multi-device enumeration.

        Steps:
        1. Get XPU ID list
        2. Query each XPU individually
        3. Combine results
        """
        if not cls.is_available():
            return []

        xpu_ids = cls.get_xpu_ids()
        if not xpu_ids:
            logger.debug("No XPU IDs found")
            return []

        all_gpu_infos = []

        for xpu_id in xpu_ids:
            cmd = cls.get_basic_info_cmd_for_xpu(xpu_id)
            r, o, e = bash_roe(cmd)
            if r != 0:
                logger.error("Failed to get XPU %s info: %s" % (xpu_id, e))
                continue

            gpu_infos = cls.parse_basic_info(o)
            all_gpu_infos.extend(gpu_infos)

        return all_gpu_infos

    # ==========================================================================
    # Addon Info Enrichment (productName)
    # ==========================================================================

    @classmethod
    def enrich_addon_info(cls, gpu_info_map, pci_addresses):
        """Add productName for Kunlunxin XPUs by querying each XPU individually."""
        if not pci_addresses:
            return

        pci_set = set(pci_addresses)
        for xpu_id in cls.get_xpu_ids():
            r, o, _ = bash_roe(cls.get_basic_info_cmd_for_xpu(xpu_id))
            if r != 0 or not o:
                continue

            product_name = None
            pci_addr = None
            for line in o.splitlines():
                line = line.strip()
                if "Product Name" in line:
                    product_name = line.split(":", 1)[1].strip()
                elif "Bus Id" in line:
                    pci_addr = cls.normalize_pci_address(
                        line.split(":", 1)[1].strip().lower())

            if product_name and pci_addr in pci_set and pci_addr in gpu_info_map:
                gpu_info_map[pci_addr]["productName"] = product_name

    # ==========================================================================
    # Prometheus Metrics Collection
    # ==========================================================================

    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        """Not used directly - we override collect_metrics"""
        return "xpu-smi -L"

    @classmethod
    def get_metric_cmd_for_xpu(cls, xpu_id):
        """Get metrics command for specific XPU"""
        return "xpu-smi -q --id={0}".format(xpu_id)

    @classmethod
    def parse_metrics(cls, output):
        """
        Parse xpu-smi metrics output.
        """
        # This would need to parse the combined output
        # For simplicity, we override collect_metrics
        return []

    @classmethod
    def collect_metrics(cls):
        """
        Override to handle multi-device enumeration for metrics.
        """
        if not cls.is_available():
            return []

        xpu_ids = cls.get_xpu_ids()
        if not xpu_ids:
            return []

        all_metrics = []

        for xpu_id in xpu_ids:
            metrics = cls._collect_metrics_for_xpu(xpu_id)
            if metrics:
                all_metrics.append(metrics)

        return all_metrics

    @classmethod
    def _collect_metrics_for_xpu(cls, xpu_id):
        """Collect metrics for a single XPU"""
        cmd = cls.get_metric_cmd_for_xpu(xpu_id)
        r, o, _ = bash_roe(cmd)
        if r != 0:
            return None

        pci_address = ""
        serial_number = ""
        utilization = None
        mem_util = None
        temperature = None
        power_draw = None
        memory_total = None
        memory_used = None

        current_section = None

        for line in o.splitlines():
            line = line.strip()
            if not line:
                continue

            # Track current section
            if ":" not in line:
                current_section = line
                continue

            if "Serial Number" in line:
                serial_number = line.split(":")[1].strip()
            elif "Bus Id" in line:
                parts = line.split(":", 1)
                if len(parts) >= 2:
                    pci_address = cls.normalize_pci_address(
                        parts[1].strip().lower())
            elif current_section == "Memory Usage":
                if "Total" in line:
                    memory_total = cls.parse_unit_value(
                        line.split(":")[1].strip(), "MiB")
                elif "Used" in line:
                    memory_used = cls.parse_unit_value(
                        line.split(":")[1].strip(), "MiB")
            elif current_section == "Utilization":
                if "Xpu" in line and "%" in line:
                    util_str = line.split(":")[1].strip().rstrip("%")
                    utilization = cls.parse_unit_value(util_str)
            elif "Power Draw" in line:
                power_str = line.split(":")[1].strip().rstrip("W")
                power_draw = cls.parse_unit_value(power_str)
            elif "XPU Current Temp" in line:
                temp_str = line.split(":")[1].strip().rstrip("C")
                temperature = cls.parse_unit_value(temp_str)

        # 统一计算内存利用率，避免对输出顺序的依赖
        if memory_total is not None and memory_used is not None:
            mem_util = (memory_used / memory_total *
                        100) if memory_total > 0 else None

        if not pci_address:
            return None

        metrics = GPUMetrics(
            pci_address=pci_address,
            serial_number=serial_number,
            utilization=utilization,
            memory_utilization=mem_util,
            temperature=temperature,
            power_draw=power_draw,
        )

        return metrics

    # ==========================================================================
    # Post-Processing Hooks
    # ==========================================================================

    @classmethod
    def post_process_pci_device(cls, pci_device_to):
        """Clean up lspci misidentified names for Kunlunxin devices.

        lspci may show wrong names like 'SafeNet (wrong ID)_Device 3686'
        because the device ID is not registered in the PCI ID database.
        When productName is already set by enrich_addon_info, this is a no-op
        (name/device were already overridden). Otherwise, fall back to a
        clean 'Kunlunxin_<deviceId>' format.
        """
        if not hasattr(pci_device_to, 'name') or not pci_device_to.name:
            return
        if 'wrong ID' not in pci_device_to.name:
            return

        device_id = getattr(pci_device_to, 'deviceId', '') or ''
        clean_name = "Kunlunxin_%s" % device_id if device_id else "Kunlunxin_XPU"
        pci_device_to.name = clean_name
        pci_device_to.device = clean_name

    # ==========================================================================
    # VM Guest Tool Support
    # ==========================================================================

    @classmethod
    def get_vm_gpu_info_cmd(cls, is_windows=False):
        """
        Get command to retrieve GPU info inside VM via guest agent.

        For Kunlunxin, we need to:
        1. Get XPU ID list
        2. Query each XPU
        """
        # This is handled in vm_config.py via get_vm_kunlunxin_gpu_info_by_guesttool
        # which calls get_kunlunxin_gpu_xpu_id_cmd() and get_kunlunxin_gpu_basic_info_cmd()
        # For now, return the list command
        return cls.get_basic_info_cmd(is_windows)

    @classmethod
    def parse_vm_gpu_info(cls, output):
        """
        Parse GPU info output from inside VM.

        Same parsing as basic info.
        """
        return cls.parse_basic_info(output)
