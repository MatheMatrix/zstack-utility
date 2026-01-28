# -*- coding: utf-8 -*-
import re
from zstacklib.gpu.base import GPUBase, GPUInfo, GPUMetrics, register_gpu_vendor
from zstacklib.utils import log

logger = log.get_logger(__name__)

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
        """
        Return command to get Enflame GPU metrics.
        
        Command: efsmi -q
        """
        cmd = "efsmi -q"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd

    @classmethod
    def _extract_number(cls, text):
        """
        Extract numeric value from text, handling various formats.
        
        Examples:
            "102 W" -> 102.0
            "45 C" -> 45.0
            "58.5 %" -> 58.5
            "100 MiB/s" -> 104857600 (converted to bytes)
        """
        if not text:
            return None
        text = str(text).strip()
        
        # Handle MB/s or MiB/s format and convert to bytes
        match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|MiB)/s', text, flags=re.IGNORECASE)
        if match:
            num = float(match.group(1))
            return int(num * 1024 * 1024)  # Convert to bytes
        
        # Extract any number (integer or float)
        match = re.search(r'(\d+(?:\.\d+)?)', text)
        return float(match.group(1)) if match else None

    @classmethod
    def _is_number(cls, s):
        """Check if string is a number"""
        if s is None or s == "":
            return False
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False

    @classmethod
    def _calculate_percentage(cls, part, total):
        """Calculate percentage from part and total"""
        if not cls._is_number(part) or not cls._is_number(total):
            return None
        try:
            part_val = float(part)
            total_val = float(total)
            if total_val == 0:
                return None
            return (part_val / total_val) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @classmethod
    def parse_metrics(cls, output):
        """
        Parse efsmi -q output to extract GPU metrics.
        
        Uses the same parsing logic as parse_enflame_gpu_output from gpu.py
        """
        results = []
        if not output:
            return results
        
        # Parse using same logic as parse_enflame_gpu_output
        for dev in output.split("DEV ID")[1:]:
            gpuinfo = {}
            domain = bus = dev_id = func = None
            
            for line in dev.strip().splitlines():
                line = line.strip()
                if ':' in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()
                else:
                    key = line
                    value = ''
                
                if key == "Domain":
                    domain = value.zfill(4)
                elif key == "Bus":
                    bus = value.zfill(2)
                elif key == "Dev":
                    dev_id = value.zfill(2)
                elif key == "Func":
                    func = value
                elif key == "Mem Size" or key == "Total Size":
                    gpuinfo["memory"] = value
                elif key == "Mem Usage" or key == "Used Size":
                    gpuinfo["memoryUsage"] = value
                elif key == "Cur Power":
                    gpuinfo["power"] = value
                elif key == "Power Capa":
                    gpuinfo["powerCap"] = value
                elif key == "GCU Temp":
                    # Handle temperature with special characters (e.g., "45 'C")
                    gpuinfo["temperature"] = value
                elif key == "GCU Usage":
                    gpuinfo["gcuUsage"] = value
                elif key == "Dev SN":
                    gpuinfo["serialNumber"] = value
                elif key == "Tx Throughput":
                    gpuinfo["txThroughput"] = value
                elif key == "Rx Throughput":
                    gpuinfo["rxThroughput"] = value
            
            if domain and bus and dev_id and func:
                pci_address = cls.normalize_pci_address("{}:{}:{}.{}".format(
                    domain, bus, dev_id, func))
                serial_number = gpuinfo.get("serialNumber", "").strip()
                
                # Parse power (remove W unit)
                power = gpuinfo.get("power", "").replace(" ", "").strip().rstrip("W")
                power_value = cls._extract_number(power) if power else None
                
                # Parse temperature (remove C unit and special chars)
                temp = gpuinfo.get("temperature", "").replace(" ", "").strip()
                # Remove degree Celsius sign and C
                temp = re.sub(r"['\u00b0\u2103]?\s*C", "", temp, flags=re.IGNORECASE)
                temperature_value = cls._extract_number(temp) if temp else None
                
                # Parse GCU usage (remove % unit)
                gcu_usage = gpuinfo.get("gcuUsage", "").replace(" ", "").strip().rstrip("%")
                utilization_value = cls._extract_number(gcu_usage) if gcu_usage else None
                
                # Calculate memory utilization
                memory_usage = gpuinfo.get("memoryUsage", "").strip().rstrip("MiB")
                memory_total = gpuinfo.get("memory", "").strip().rstrip("MiB")
                memory_utilization_value = None
                if cls._is_number(memory_usage) and cls._is_number(memory_total):
                    memory_utilization_value = cls._calculate_percentage(memory_usage, memory_total)
                
                # Parse PCIe throughput (MiB/s -> bytes)
                rx_throughput = gpuinfo.get("rxThroughput", "").strip().rstrip("MiB/s")
                tx_throughput = gpuinfo.get("txThroughput", "").strip().rstrip("MiB/s")
                rx_bytes = cls._extract_number(rx_throughput + " MiB/s") if rx_throughput else None
                tx_bytes = cls._extract_number(tx_throughput + " MiB/s") if tx_throughput else None
                
                results.append(GPUMetrics(
                    pci_address=pci_address,
                    serial_number=serial_number,
                    utilization=utilization_value,
                    memory_utilization=memory_utilization_value,
                    temperature=temperature_value,
                    power_draw=power_value,
                    pcie_rx_bytes=rx_bytes,
                    pcie_tx_bytes=tx_bytes
                ))
        
        return results
    
    @classmethod
    def post_process_pci_device(cls, pci_device_to):
        """
        Post-process PCI device after collection.
        
        Enflame GPUs are not virtualizable, so set virtStatus to UNVIRTUALIZABLE.
        
        Args:
            pci_device_to: The PCI device transfer object
        """
        pci_device_to.virtStatus = "UNVIRTUALIZABLE"
