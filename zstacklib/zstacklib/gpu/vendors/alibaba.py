# -*- coding: utf-8 -*-
import os
import re

from zstacklib.gpu.base import GPUBase, GPUInfo, GPUMetrics, register_gpu_vendor
from zstacklib.utils import log
from zstacklib.utils.bash import bash_roe

logger = log.get_logger(__name__)


@register_gpu_vendor
class Alibaba(GPUBase):
    VENDOR_NAME = "Alibaba"
    VENDOR_ENUM_NAME = "Alibaba"
    VENDOR_IDS = {"1ded"}
    PCI_NAME_KEYWORDS = {"Alibaba"}
    CLI_TOOL = "ppu-smi"

    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        return "ppu-smi --query-ppu=bus_id,memory.total,power.limit,serial --format=csv,noheader"

    @classmethod
    def parse_basic_info(cls, output):
        gpu_infos = []
        if not output:
            return gpu_infos
            
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) < 4:
                continue
            
            pci_address = cls.normalize_pci_address(parts[0].strip())
                
            gpu_infos.append(GPUInfo(
                pci_address=pci_address,
                memory=parts[1].strip(),
                power=parts[2].strip(),
                serial_number=parts[3].strip()
            ))
        return gpu_infos

    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        """
        Return command to get Alibaba PPU metrics.
        
        Command returns CSV format:
        gpu_bus_id, utilization.ppu, temperature.ppu, power.draw, 
        utilization.memory, pcie.throughput.tx, pcie.throughput.rx, gpu_serial
        """
        cmd = "ppu-smi --query-ppu=gpu_bus_id,utilization.ppu,temperature.ppu,power.draw,utilization.memory,pcie.throughput.tx,pcie.throughput.rx,gpu_serial --format=csv,noheader"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd

    @classmethod
    def parse_metrics(cls, output):
        """
        Parse Alibaba PPU metrics output.
        
        Input format (CSV):
        00000000:08:00.0, 45 %, 62 C, 70.00 W, 58 %, 100 KB/s, 200 KB/s, 02A8B95253C002B8
        
        Returns list of GPUMetrics objects.
        """
        results = []
        if not output:
            return results
        
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(',')
            # Command returns: gpu_bus_id, utilization.ppu, temperature.ppu, power.draw, 
            # utilization.memory, pcie.throughput.tx, pcie.throughput.rx, gpu_serial
            if len(parts) < 8:
                continue

            pci_address = cls.normalize_pci_address(parts[0].strip())
            if not pci_address:
                continue

            # Parse values, removing units
            utilization = cls.parse_unit_value(parts[1].strip())
            temperature = cls.parse_unit_value(parts[2].strip())
            power_draw = cls.parse_unit_value(parts[3].strip())
            memory_utilization = cls.parse_unit_value(parts[4].strip())
            pcie_tx = cls._parse_ppu_throughput_to_bytes(parts[5].strip())
            pcie_rx = cls._parse_ppu_throughput_to_bytes(parts[6].strip())
            gpu_serial = parts[7].strip()

            metrics = GPUMetrics(
                pci_address=pci_address,
                serial_number=gpu_serial,
                utilization=utilization,
                memory_utilization=memory_utilization,
                temperature=temperature,
                power_draw=power_draw,
                pcie_tx_bytes=pcie_tx,
                pcie_rx_bytes=pcie_rx
            )
            results.append(metrics)
        
        return results

    @classmethod
    def enrich_addon_info(cls, gpu_info_map, pci_addresses):
        """Add productName for Alibaba PPUs."""
        if not pci_addresses:
            return
        from zstacklib.utils.gpu import get_alibaba_ppu_product_name_cmd, get_alibaba_ppu_product_name
        r, o, e = bash_roe(get_alibaba_ppu_product_name_cmd())
        if r == 0 and o:
            product_name = get_alibaba_ppu_product_name(o)
            if product_name:
                for pci_addr in pci_addresses:
                    if pci_addr in gpu_info_map:
                        gpu_info_map[pci_addr]["productName"] = product_name

    @classmethod
    def _parse_ppu_throughput_to_bytes(cls, value):
        """
        Parse PPU PCIe throughput value to bytes.
        
        Examples:
        - '0 KB/s' -> 0
        - '1024 KB/s' -> 1048576
        - '1 MB/s' -> 1048576
        - '1 GB/s' -> 1073741824
        
        Args:
            value: Throughput string (e.g., '1024 KB/s')
            
        Returns:
            int: Bytes per second, or None if parsing fails
        """
        if not value:
            return None
        value = value.strip()
        match = re.match(r'([\d.]+)\s*(KB|MB|GB)/s', value, re.IGNORECASE)
        if not match:
            logger.debug("[ALIBABA PPU] Failed to parse throughput value: %s" % value)
            return None
        num = float(match.group(1))
        unit = match.group(2).upper()
        if unit == 'KB':
            return int(num * 1024)
        elif unit == 'MB':
            return int(num * 1024 * 1024)
        elif unit == 'GB':
            return int(num * 1024 * 1024 * 1024)

    @classmethod
    def is_available(cls):
        """
        Check if ppu-smi tool is available.
        
        Returns:
            bool: True if ppu-smi is available, False otherwise
        """
        r, o, _ = bash_roe("which ppu-smi")
        if r == 0:
            logger.debug("[ALIBABA PPU] ppu-smi found at: %s" % o.strip())
            return True
        # Also check common installation path
        if os.path.exists("/usr/local/bin/ppu-smi"):
            logger.debug("[ALIBABA PPU] ppu-smi found at /usr/local/bin/ppu-smi")
            return True
        logger.debug("[ALIBABA PPU] ppu-smi not found")
        return False
