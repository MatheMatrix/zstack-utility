# -*- coding: utf-8 -*-
import re
from zstacklib.gpu.base import GPUBase, GPUInfo, register_gpu_vendor

@register_gpu_vendor
class Enflame(GPUBase):
    VENDOR_NAME = "Enflame"
    VENDOR_ENUM_NAME = "Enflame"
    VENDOR_IDS = {"1e36"}
    PCI_NAME_KEYWORDS = {"Enflame"}
    CLI_TOOL = "efsmi"

    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        return "efsmi -a"

    @classmethod
    def parse_basic_info(cls, output):
        gpu_infos = []
        if not output:
            return gpu_infos
            
        current_gpu = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("DEV ID"):
                if current_gpu and "pciAddress" in current_gpu:
                    gpu_infos.append(GPUInfo(
                        pci_address=current_gpu["pciAddress"],
                        memory=current_gpu.get("memory"),
                        power=current_gpu.get("power"),
                        serial_number=current_gpu.get("serialNumber"),
                        device_name=current_gpu.get("deviceName")
                    ))
                current_gpu = {}
            elif "Dev Name" in line:
                current_gpu["deviceName"] = line.split(":")[1].strip()
            elif "Dev SN" in line:
                current_gpu["serialNumber"] = line.split(":")[1].strip()
            elif "Domain" in line:
                current_gpu["domain"] = line.split(":")[1].strip()
            elif "Bus" in line:
                current_gpu["bus"] = line.split(":")[1].strip()
            elif "Dev" in line and ":" in line:
                current_gpu["dev"] = line.split(":")[1].strip()
            elif "Func" in line:
                current_gpu["func"] = line.split(":")[1].strip()
                if all(k in current_gpu for k in ["domain", "bus", "dev", "func"]):
                    # Normalize domain: if 8 chars, take last 4; otherwise pad to 4
                    domain = current_gpu["domain"].strip()
                    if len(domain) == 8:
                        domain = domain[-4:]
                    else:
                        domain = domain.zfill(4)
                    addr = "%s:%s:%s.%s" % (
                        domain,
                        current_gpu["bus"],
                        current_gpu["dev"],
                        current_gpu["func"]
                    )
                    current_gpu["pciAddress"] = cls.normalize_pci_address(addr)
            elif "Power Capa" in line:
                current_gpu["power"] = line.split(":")[1].strip()
            elif "Mem Size" in line:
                current_gpu["memory"] = line.split(":")[1].strip()

        if current_gpu and "pciAddress" in current_gpu:
            gpu_infos.append(GPUInfo(
                pci_address=current_gpu["pciAddress"],
                memory=current_gpu.get("memory"),
                power=current_gpu.get("power"),
                serial_number=current_gpu.get("serialNumber"),
                device_name=current_gpu.get("deviceName")
            ))
            
        return gpu_infos

    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        return ""

    @classmethod
    def parse_metrics(cls, output):
        return []
