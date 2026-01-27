# -*- coding: utf-8 -*-
from zstacklib.gpu.base import GPUBase, GPUInfo, register_gpu_vendor

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
        return ""

    @classmethod
    def parse_metrics(cls, output):
        return []
