# -*- coding: utf-8 -*-
"""
Huawei NPU Vendor Implementation (Python 2/3 Compatible)
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
class Huawei(GPUBase):
    """
    Huawei NPU vendor implementation.
    """
    
    # ==========================================================================
    # Vendor Identification
    # ==========================================================================
    
    VENDOR_NAME = "Huawei"
    VENDOR_ENUM_NAME = "Huawei"
    VENDOR_IDS = {"19e5"}
    PCI_NAME_KEYWORDS = {"Huawei Technologies", "HUAWEI"}
    CLI_TOOL = "npu-smi"
    
    DEVICE_TYPES = {"Processing accelerators"}
    IS_GPU_VENDOR = True
    
    # ==========================================================================
    # Multi-Device Enumeration
    # ==========================================================================
    
    @classmethod
    def get_npu_ids(cls):
        r, o, _ = bash_roe("npu-smi info -l")
        if r != 0:
            return []
        
        npu_ids = []
        for line in o.splitlines():
            line = line.strip()
            if "NPU ID" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    npu_ids.append(parts[1].strip())
        return npu_ids
    
    # ==========================================================================
    # Basic Information Collection
    # ==========================================================================
    
    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        """
        This is not used directly - we override get_basic_info.
        """
        return "npu-smi info -l"
    
    @classmethod
    def get_basic_info_cmd_for_npu(cls, npu_id, is_windows=False):
        """Get command for specific NPU ID"""
        cmd = "npu-smi info -t board -i {0};npu-smi info -i {0} -t memory;npu-smi info -t power -i {0}".format(npu_id)
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_basic_info(cls, output):
        """
        Parse npu-smi output for a single NPU.
        """
        gpu_infos = []
        gpu_info_dict = {}
        
        total_memory = 0
        total_ddr_memory = 0
        found_total_memory = False
        
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            if "Serial Number" in line:
                gpu_info_dict["serial_number"] = line.split(":")[1].strip()
            elif "PCIe Bus Info" in line:
                pci_addr = line.partition(": ")[-1].strip()
                gpu_info_dict["pci_address"] = cls.normalize_pci_address(pci_addr)
            elif line.startswith("Total DDR Capacity(MB)"):
                try:
                    memory_value = int(line.split(":")[1].strip().split()[0])
                    total_ddr_memory += memory_value
                    found_total_memory = True
                except (ValueError, IndexError):
                    logger.debug("Failed to parse Total DDR Capacity: %s" % line)
            elif (line.startswith("DDR Capacity(MB)") or line.startswith("HBM Capacity")) and not found_total_memory:
                try:
                    memory_value = int(line.split(":")[1].strip().split()[0])
                    total_memory += memory_value
                except (ValueError, IndexError):
                    logger.debug("Failed to parse DDR/HBM Capacity: %s" % line)
            elif "Power Dissipation" in line or "Real-time Power(W)" in line:
                gpu_info_dict["power"] = line.split(":")[1].strip()
        
        total_memory = total_ddr_memory if found_total_memory else total_memory
        if total_memory > 0:
            gpu_info_dict["memory"] = "%s MB" % total_memory
        
        if gpu_info_dict.get("pci_address"):
            gpu_info = GPUInfo(
                pci_address=gpu_info_dict.get("pci_address", ""),
                memory=gpu_info_dict.get("memory"),
                power=gpu_info_dict.get("power"),
                serial_number=gpu_info_dict.get("serial_number"),
            )
            gpu_infos.append(gpu_info)
        
        return gpu_infos
    
    @classmethod
    def get_basic_info(cls):
        """
        Override to handle multi-device enumeration.
        
        Steps:
        1. Get NPU ID list
        2. Query each NPU individually
        3. Combine results
        """
        if not cls.is_available():
            return []
        
        npu_ids = cls.get_npu_ids()
        if not npu_ids:
            logger.debug("No NPU IDs found")
            return []
        
        all_gpu_infos = []
        npu_id_map = {}  # pci_address -> npu_id
        
        for npu_id in npu_ids:
            cmd = cls.get_basic_info_cmd_for_npu(npu_id)
            r, o, e = bash_roe(cmd)
            if r != 0:
                logger.error("Failed to get NPU %s info: %s" % (npu_id, e))
                continue
            
            gpu_infos = cls.parse_basic_info(o)
            
            # Store NPU ID mapping
            for info in gpu_infos:
                if info.pci_address:
                    npu_id_map[info.pci_address.lower()] = npu_id
                    # Store NPU ID in extra field
                    info.extra["npuId"] = npu_id
                    
                    # Check isolation status
                    try:
                        is_isolated = cls.check_npu_isolation(npu_id, npu_ids)
                        info.extra["isIsolated"] = is_isolated
                    except Exception as ex:
                        logger.debug("Failed to check isolation for NPU %s: %s" % (npu_id, ex))
                        info.extra["isIsolated"] = False
            
            all_gpu_infos.extend(gpu_infos)
        
        return all_gpu_infos
    
    # ==========================================================================
    # Prometheus Metrics Collection
    # ==========================================================================
    
    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        """Not used directly - we override collect_metrics"""
        return "npu-smi info -l"
    
    @classmethod
    def get_metric_cmd_for_npu(cls, npu_id):
        """Get metrics command for specific NPU"""
        return ("npu-smi info -t usages -i {0};"
                "npu-smi info -t memory -i {0};"
                "npu-smi info -t temp -i {0};"
                "npu-smi info -t power -i {0}".format(npu_id))
    
    @classmethod
    def parse_metrics(cls, output):
        """
        Parse npu-smi metrics output.
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
        
        npu_ids = cls.get_npu_ids()
        if not npu_ids:
            return []
        
        all_metrics = []
        
        for npu_id in npu_ids:
            metrics = cls._collect_metrics_for_npu(npu_id)
            if metrics:
                all_metrics.append(metrics)
        
        return all_metrics
    
    @classmethod
    def _collect_metrics_for_npu(cls, npu_id):
        """Collect metrics for a single NPU"""
        cmd = cls.get_metric_cmd_for_npu(npu_id)
        r, o, _ = bash_roe(cmd)
        if r != 0:
            return None
        
        pci_address = ""
        serial_number = ""
        utilization = None
        mem_util = None
        temperature = None
        power_draw = None
        
        # Extra metrics for Huawei
        ddr_capacity = None
        ddr_usage_rate = None
        hbm_capacity = None
        hbm_usage_rate = None
        
        for line in o.splitlines():
            line = line.strip()
            if not line:
                continue
            
            if "PCIe Bus Info" in line:
                pci_address = cls.normalize_pci_address(line.partition(": ")[-1])
            elif "Serial Number" in line:
                serial_number = line.split(":")[1].strip()
            elif "Aicore Usage Rate" in line or "NPU Usage" in line:
                match = re.search(r'(\d+(?:\.\d+)?)\s*%?', line.split(":")[1])
                if match:
                    utilization = float(match.group(1))
            elif "Memory Usage Rate" in line:
                match = re.search(r'(\d+(?:\.\d+)?)\s*%?', line.split(":")[1])
                if match:
                    mem_util = float(match.group(1))
            elif "Temperature" in line or "NPU Temp" in line:
                match = re.search(r'(\d+(?:\.\d+)?)', line.split(":")[1])
                if match:
                    temperature = float(match.group(1))
            elif "Real-time Power" in line or "Power Dissipation" in line:
                match = re.search(r'(\d+(?:\.\d+)?)', line.split(":")[1])
                if match:
                    power_draw = float(match.group(1))
            elif "DDR Capacity" in line:
                match = re.search(r'(\d+)', line.split(":")[1])
                if match:
                    ddr_capacity = float(match.group(1))
            elif "DDR Usage Rate" in line:
                match = re.search(r'(\d+(?:\.\d+)?)', line.split(":")[1])
                if match:
                    ddr_usage_rate = float(match.group(1))
            elif "HBM Capacity" in line:
                match = re.search(r'(\d+)', line.split(":")[1])
                if match:
                    hbm_capacity = float(match.group(1))
            elif "HBM Usage Rate" in line:
                match = re.search(r'(\d+(?:\.\d+)?)', line.split(":")[1])
                if match:
                    hbm_usage_rate = float(match.group(1))
        
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
        
        # Add extra Huawei-specific metrics
        if ddr_capacity is not None:
            metrics.extra["host_gpu_ddr_capacity"] = ddr_capacity
        if ddr_usage_rate is not None:
            metrics.extra["host_gpu_ddr_usage_rate"] = ddr_usage_rate
        if hbm_capacity is not None:
            metrics.extra["host_gpu_hbm_capacity"] = hbm_capacity
        if hbm_usage_rate is not None:
            metrics.extra["host_gpu_hbm_rate"] = hbm_usage_rate
        
        return metrics
    
    # ==========================================================================
    # Custom Prometheus Metrics
    # ==========================================================================
    
    @classmethod
    def get_custom_prometheus_metrics(cls):
        """
        Define Huawei-specific metrics.
        """
        return {
            "host_gpu_ddr_capacity": (
                "GPU DDR Capacity (MB)",
                "gauge",
                ["pci_device_address", "gpu_serial"]
            ),
            "host_gpu_ddr_usage_rate": (
                "GPU DDR Usage Rate (%)",
                "gauge",
                ["pci_device_address", "gpu_serial"]
            ),
            "host_gpu_hbm_capacity": (
                "GPU HBM Capacity (MB)",
                "gauge",
                ["pci_device_address", "gpu_serial"]
            ),
            "host_gpu_hbm_rate": (
                "GPU HBM Usage Rate (%)",
                "gauge",
                ["pci_device_address", "gpu_serial"]
            ),
        }
    
    # ==========================================================================
    # Isolation Detection
    # ==========================================================================
    
    @classmethod
    def check_npu_isolation(cls, npu_id, all_npu_ids):
        """
        Check if NPU is isolated using hccs health status.
        
        An isolated NPU should not be used for computation.
        """
        if not npu_id or not all_npu_ids or len(all_npu_ids) <= 1:
            return False
        
        cmd = "npu-smi info -t hccs -i %s -c 0" % npu_id
        r, o, e = bash_roe(cmd)
        
        if r != 0 or not o:
            logger.debug("Failed to check isolation for NPU %s: %s" % (npu_id, e))
            return False
        
        for line in o.splitlines():
            line = line.strip().lower()
            if "hccs health status" in line:
                parts = line.split(":", 1)
                status = parts[1].strip().upper() if len(parts) > 1 else ""
                if status != "OK":
                    logger.debug("NPU %s health status: %s (isolated)" % (npu_id, status))
                    return True
                return False
        
        return False
    
    # ==========================================================================
    # AIOS Rank Table (for cluster interconnect)
    # ==========================================================================
    
    @classmethod
    def get_aios_rank_table(cls, npu_ids):
        """
        Get AIOS rank table for cluster interconnect.
        
        This is stored in addonInfo["opaque"]["aiosRankTable"].
        """
        if not npu_ids:
            return None
        
        device_ips = {}
        device_netmasks = {}
        
        for npu_id in npu_ids:
            if not npu_id.isdigit():
                continue
            
            r, o, _ = bash_roe("hccn_tool -i %s -ip -g" % npu_id)
            
            ip = None
            netmask = None
            
            if r == 0 and o:
                # Parse IP address
                ip_match = re.search(r'ipaddr:(\d+\.\d+\.\d+\.\d+)', o)
                if ip_match:
                    ip = ip_match.group(1)
                
                # Parse netmask
                netmask_match = re.search(r'netmask:(\d+\.\d+\.\d+\.\d+)', o)
                if netmask_match:
                    netmask = netmask_match.group(1)
            
            # Fallback defaults
            if not ip:
                ip = "10.20.0.%s" % (int(npu_id) + 2)
            if not netmask:
                netmask = "255.255.0.0"
            
            device_ips[npu_id] = ip
            device_netmasks[npu_id] = netmask
        
        rank_table = {
            "server_count": len(npu_ids),
            "server_list": []
        }
        
        for npu_id in npu_ids:
            server_info = {
                "device_id": npu_id,
                "host": device_ips.get(npu_id, ""),
                "device_ip": device_ips.get(npu_id, ""),
                "netmask": device_netmasks.get(npu_id, "")
            }
            rank_table["server_list"].append(server_info)
        
        return rank_table
