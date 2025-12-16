# -*- coding: utf-8 -*-
import json
from zstacklib.utils import log
from zstacklib.gpu.base import GPUBase, GPUInfo, register_gpu_vendor

logger = log.get_logger(__name__)

@register_gpu_vendor
class Haiguang(GPUBase):
    VENDOR_NAME = "Haiguang"
    VENDOR_ENUM_NAME = "Haiguang"
    VENDOR_IDS = {"1d94"}
    PCI_NAME_KEYWORDS = {"Haiguang"}
    CLI_TOOL = "hy-smi"

    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        return "hy-smi -a --json"

    @classmethod
    def parse_basic_info(cls, output):
        gpu_infos = []
        if not output:
            return gpu_infos
            
        try:
            data = json.loads(output)
            for card_name, card_data in data.items():
                pci_address = cls.normalize_pci_address(card_data.get('PCI Bus', ''))
                
                # Handle memory field - only add " MiB" suffix if value exists
                memory_value = card_data.get('Available memory size (MiB)')
                memory_str = None
                if memory_value is not None and memory_value != '':
                    memory_str = str(memory_value) + " MiB"
                
                # Handle power field - only convert to string if value exists
                power_value = card_data.get('Max Graphics Package Power (W)')
                power_str = None
                if power_value is not None and power_value != '':
                    power_str = str(power_value)
                
                gpu_infos.append(GPUInfo(
                    pci_address=pci_address,
                    memory=memory_str,
                    power=power_str,
                    serial_number=card_data.get('Serial Number', '')
                ))
        except Exception as e:
            logger.error("Failed to parse Haiguang basic info: %s" % str(e))
        return gpu_infos

    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        return ""

    @classmethod
    def parse_metrics(cls, output):
        return []
