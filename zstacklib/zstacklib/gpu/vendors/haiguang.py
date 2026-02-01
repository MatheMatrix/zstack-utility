# -*- coding: utf-8 -*-
import json
from zstacklib.utils import log
from zstacklib.gpu.base import GPUBase, GPUInfo, GPUMetrics, register_gpu_vendor

logger = log.get_logger(__name__)

@register_gpu_vendor
class Haiguang(GPUBase):
    VENDOR_NAME = "Haiguang"
    VENDOR_ENUM_NAME = "Haiguang"
    VENDOR_IDS = {"1d94"}
    PCI_NAME_KEYWORDS = {"Haiguang"}
    CLI_TOOL = "hy-smi"
    DEVICE_TYPES = {"3D controller", "VGA compatible controller", "Processing accelerators"}

    @classmethod
    def get_pci_only_candidates(cls, device_ids, device_names):
        """
        When hy-smi is not available, identify Haiguang DCU/GPU by PCI: vendor 1d94,
        class 3D controller, VGA compatible controller, or Processing accelerators.
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

    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        """Same as 5.5.0 / gpu.get_hy_gpu_basic_info_cmd(); exact flags ensure JSON keys match parse_basic_info."""
        cmd = "hy-smi --showserial --showmaxpower --showmemavailable --showbus --json"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd

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
        """
        Return command to get Haiguang GPU metrics.
        
        Command: hy-smi --showuse --showmemuse --showpower --showtemp --showserial --showbus --json
        """
        cmd = "hy-smi --showuse --showmemuse --showpower --showtemp --showserial --showbus --json"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd

    @classmethod
    def parse_metrics(cls, output):
        """
        Parse hy-smi metrics output.
        
        Input format (JSON):
        {
            "card_name": {
                "PCI Bus": "0000:3b:00.0",
                "Serial Number": "SN123456",
                "Average Graphics Package Power (W)": 75.5,
                "Temperature (Sensor junction) (C)": 62,
                "Fan speed (%)": 45,
                "DCU use (%)": 58,
                "HCU use (%)": 60,
                "DCU memory use (%)": 65,
                "HCU memory use (%)": 70
            }
        }
        """
        results = []
        if not output:
            return results
            
        try:
            data = json.loads(output.strip())
        except Exception as e:
            logger.error("Failed to parse Haiguang metrics JSON: %s" % str(e))
            return results
            
        for card_name, card_data in data.items():
            try:
                pci_bus = card_data.get('PCI Bus', '')
                pci_address = cls.normalize_pci_address(pci_bus)
                serial = card_data.get('Serial Number', '')
                
                # Power draw
                power = card_data.get('Average Graphics Package Power (W)')
                
                # Temperature
                temp = card_data.get('Temperature (Sensor junction) (C)')
                
                # Fan speed
                fan_speed = card_data.get('Fan speed (%)')
                
                # Utilization - prefer DCU use, fallback to HCU use
                dcu_util = card_data.get('DCU use (%)')
                utilization = dcu_util if dcu_util is not None else card_data.get('HCU use (%)')
                
                # Memory utilization - prefer DCU memory use, fallback to HCU memory use
                dcu_mem_util = card_data.get('DCU memory use (%)')
                mem_util = dcu_mem_util if dcu_mem_util is not None else card_data.get('HCU memory use (%)')
                
                # Parse values
                power_value = None
                if power not in (None, ''):
                    try:
                        power_value = float(power)
                    except (ValueError, TypeError):
                        pass
                
                temp_value = None
                if temp not in (None, ''):
                    try:
                        temp_value = float(temp)
                    except (ValueError, TypeError):
                        pass
                
                fan_speed_value = None
                if fan_speed not in (None, ''):
                    try:
                        fan_speed_str = str(fan_speed).replace('%', '').strip()
                        fan_speed_value = float(fan_speed_str)
                    except (ValueError, TypeError):
                        pass
                
                util_value = None
                if utilization not in (None, ''):
                    try:
                        util_str = str(utilization).replace('%', '').strip()
                        util_value = float(util_str)
                    except (ValueError, TypeError):
                        pass
                
                mem_util_value = None
                if mem_util not in (None, ''):
                    try:
                        mem_util_str = str(mem_util).replace('%', '').strip()
                        mem_util_value = float(mem_util_str)
                    except (ValueError, TypeError):
                        pass
                
                results.append(GPUMetrics(
                    pci_address=pci_address,
                    serial_number=serial,
                    utilization=util_value,
                    memory_utilization=mem_util_value,
                    temperature=temp_value,
                    power_draw=power_value,
                    fan_speed=fan_speed_value
                ))
            except Exception as e:
                logger.warn("Failed to parse Haiguang metrics for card %s: %s" % (card_name, str(e)))
                continue
                
        return results
