# -*- coding: utf-8 -*-
"""
Kunlunxin XPU Vendor Implementation (Python 2/3 Compatible)
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

    DEVICE_TYPES = {"Processing accelerators", "3D controller"}
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

        Output format example:
            Serial Number                         : 02K0MA0258D0007R
            Bus Id                            : 00000000:21:00.0
            Memory Usage
                Total                             : 98304 MiB
                Used                              : 0 MiB
            Utilization
                Xpu                               : 0 %
            Enforced Power Limit              : 350.00 W
            Power Draw                        : 75.00 W
            XPU Current Temp                  : 40 C
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

            if "Serial Number" in line:
                gpu_info_dict["serial_number"] = line.split(":")[1].strip()
            elif "Bus Id" in line:
                parts = line.split(":", 1)
                if len(parts) >= 2:
                    pci_addr = parts[1].strip().lower()
                    gpu_info_dict["pci_address"] = cls.normalize_pci_address(
                        pci_addr)
            elif current_section == "Memory Usage":
                if "Total" in line:
                    total_memory = line.split(":")[1].strip()
                    gpu_info_dict["memory"] = total_memory
                elif "Used" in line:
                    used_memory = line.split(":")[1].strip()
                    gpu_info_dict["memoryUsage"] = used_memory
            elif "Enforced Power Limit" in line:
                gpu_info_dict["power"] = line.split(":")[1].strip()
            elif "Power Draw" in line:
                gpu_info_dict["powerDraw"] = line.split(":")[1].strip()
            elif "XPU Current Temp" in line:
                gpu_info_dict["temperature"] = line.split(":")[1].strip()

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
