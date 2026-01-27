# -*- coding: utf-8 -*-
"""
AMD GPU Vendor Implementation (Python 2/3 Compatible)
"""

import json

from zstacklib.utils import log
from zstacklib.gpu.base import (
    GPUBase,
    GPUInfo,
    GPUMetrics,
    register_gpu_vendor
)

logger = log.get_logger(__name__)


@register_gpu_vendor
class AMD(GPUBase):
    """
    AMD GPU vendor implementation.
    """
    
    VENDOR_NAME = "AMD"
    VENDOR_ENUM_NAME = "AMD"
    VENDOR_IDS = {"1002"}
    PCI_NAME_KEYWORDS = {"Advanced Micro Devices", "AMD"}
    CLI_TOOL = "rocm-smi"
    DEVICE_TYPES = {"3D controller", "VGA compatible controller"}
    IS_GPU_VENDOR = True
    
    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        cmd = "rocm-smi --showbus --showmeminfo vram --showpower --showserial --json"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_basic_info(cls, output):
        gpu_infos = []
        if not output:
            return gpu_infos
            
        try:
            data = json.loads(output.strip())
        except Exception as e:
            logger.error("Failed to parse AMD basic info JSON: %s" % str(e))
            return gpu_infos
            
        for card_name, card_data in data.items():
            try:
                pci_bus = card_data.get('PCI Bus', '')
                pci_address = cls.normalize_pci_address(pci_bus)
                
                memory_bytes = card_data.get('VRAM Total Memory (B)')
                memory_str = None
                if memory_bytes:
                    try:
                        memory_mib = int(memory_bytes) // (1024 * 1024)
                        memory_str = "%d MiB" % memory_mib
                    except (ValueError, TypeError):
                        memory_str = str(memory_bytes)
                
                power = card_data.get('Average Graphics Package Power (W)',
                        card_data.get('Current Socket Graphics Package Power (W)'))
                
                gpu_infos.append(GPUInfo(
                    pci_address=pci_address,
                    memory=memory_str,
                    power=str(power) if power not in (None, '') else None,
                    serial_number=card_data.get('Serial Number')
                ))
            except Exception as e:
                logger.warn("Failed to parse AMD basic info for card %s: %s" % (card_name, str(e)))
                continue
            
        return gpu_infos

    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        cmd = "rocm-smi --showuse --showmeminfo vram --showtemp --showpower --showserial --json"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_metrics(cls, output):
        results = []
        if not output:
            return results
            
        try:
            data = json.loads(output.strip())
        except Exception as e:
            logger.error("Failed to parse AMD metrics JSON: %s" % str(e))
            return results
            
        for card_name, card_data in data.items():
            try:
                pci_bus = card_data.get('PCI Bus', '')
                pci_address = cls.normalize_pci_address(pci_bus)
                
                util = card_data.get('GPU use (%)')
                mem_util = card_data.get('VRAM Total Memory (B)') # Simplified
                temp = card_data.get('Temperature (Sensor edge) (C)')
                power = card_data.get('Average Graphics Package Power (W)')
                serial = card_data.get('Serial Number')
                
                results.append(GPUMetrics(
                    pci_address=pci_address,
                    serial_number=serial,
                    memory_utilization=float(mem_util) if mem_util not in (None, '') else None,
                    utilization=float(util) if util not in (None, '') else None,
                    temperature=float(temp) if temp not in (None, '') else None,
                    power_draw=float(power) if power not in (None, '') else None
                ))
            except Exception as e:
                logger.warn("Failed to parse AMD metrics for card %s: %s" % (card_name, str(e)))
                continue
            
        return results
