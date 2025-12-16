# -*- coding: utf-8 -*-
"""
Template for New GPU Vendor Implementation

This file serves as a starting template for adding support for a new GPU vendor.
Follow the steps below to create your vendor implementation.

Steps to implement a new vendor:
1. Copy this file to <name>.py (e.g., mygpu.py)
2. Replace "NewVendor" with your vendor name (e.g., "MyGPU")
3. Fill in VENDOR_NAME, VENDOR_IDS, PCI_NAME_KEYWORDS, CLI_TOOL
4. Implement get_basic_info_cmd() and parse_basic_info()
5. Implement get_metric_cmd() and parse_metrics()
6. (Optional) Implement pre_detach hooks if needed
7. (Optional) Implement custom metrics if needed
8. Import your vendor file in __init__.py to register it:
   from zstacklib.gpu.vendors import mygpu

Refer to nvidia.py for a complete reference implementation.
"""

from typing import List, Dict, Optional, Tuple, Any

from zstacklib.utils import log
from zstacklib.utils.bash import bash_roe, bash_ro
from zstacklib.gpu.base import (
    GPUBase,
    GPUInfo,
    GPUMetrics,
    VGPUMetrics,
    register_gpu_vendor
)

logger = log.get_logger(__name__)


# Uncomment the @register_gpu_vendor decorator when ready
# @register_gpu_vendor
class NewVendor(GPUBase):
    """
    New Vendor GPU Implementation Template
    
    TODO: Replace "NewVendor" with actual vendor name
    TODO: Update all configuration values
    TODO: Implement required methods
    """
    
    # ==========================================================================
    # Vendor Identification (REQUIRED)
    # ==========================================================================
    
    # Unique vendor name - used for logging and registry
    # Example: "NVIDIA", "AMD", "Huawei", "Enflame"
    VENDOR_NAME = "NewVendor"
    
    # PCI Vendor IDs (from lspci -n)
    # Find with: lspci -nn | grep -i <vendor_keyword>
    # Example: {"10de"} for NVIDIA, {"1002"} for AMD
    VENDOR_IDS = {"xxxx"}  # TODO: Set correct vendor ID
    
    # Keywords to match in lspci vendor name output
    # Find with: lspci -Dmmnv | grep -i <vendor_keyword>
    # Example: {"NVIDIA Corporation"}, {"Advanced Micro Devices"}
    PCI_NAME_KEYWORDS = {"New Vendor Inc"}  # TODO: Set correct keywords
    
    # CLI tool name for GPU management
    # Example: "nvidia-smi", "rocm-smi", "npu-smi"
    CLI_TOOL = "newvendor-smi"  # TODO: Set correct tool name
    
    # (Optional) Full path to CLI tool if not in PATH
    CLI_TOOL_PATH = None  # e.g., "/usr/local/bin/newvendor-smi"
    
    # Device types recognized as GPU
    # Common types: "3D controller", "VGA compatible controller",
    #               "Processing accelerators", "Co-processor"
    DEVICE_TYPES = {"3D controller"}
    
    # Set to True if this vendor should be in gpu_vendors list
    # (for 3D controller type identification)
    IS_GPU_VENDOR = True
    
    # ==========================================================================
    # Basic Information Collection (REQUIRED)
    # ==========================================================================
    
    @classmethod
    def get_basic_info_cmd(cls, is_windows: bool = False) -> str:
        """
        Return command to get basic GPU information.
        
        The command output should contain (in parseable format):
        1. PCI Address (e.g., "00000000:3B:00.0")
        2. Memory Total (e.g., "15360 MiB")
        3. Power Limit (e.g., "70.00 W")
        4. Serial Number (e.g., "1322519087621")
        
        Args:
            is_windows: If True, replace spaces with "|" for Windows PowerShell
            
        Returns:
            Command string
            
        Examples:
            # CSV format (NVIDIA style)
            return "nvidia-smi --query-gpu=gpu_bus_id,memory.total,power.limit,gpu_serial --format=csv,noheader"
            
            # JSON format (AMD style)
            return "rocm-smi --showbus --showmeminfo vram --showpower --showserial --json"
            
            # Custom text format (requires custom parsing)
            return "newvendor-smi info -a"
        """
        # TODO: Replace with actual command
        cmd = "newvendor-smi --query=pci_addr,memory,power,serial --format=csv"
        
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_basic_info(cls, output: str) -> List[GPUInfo]:
        """
        Parse basic info command output into GPUInfo objects.
        
        Args:
            output: Raw command output string
            
        Returns:
            List of GPUInfo objects
            
        Example output formats:
        
        CSV format:
            00000000:3B:00.0, 15360 MiB, 70.00 W, 1322519087621
            00000000:86:00.0, 15360 MiB, 70.00 W, 1322519087622
            
        JSON format:
            {"card0": {"PCI Bus": "0000:3b:00.0", "VRAM Total Memory (B)": 16106127360, ...}}
            
        Text format:
            GPU 0:
                PCI Address: 0000:3b:00.0
                Memory: 15360 MiB
                ...
        """
        gpu_infos = []
        
        # TODO: Implement parsing logic for your command output
        # Example for CSV format:
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) < 4:
                continue
            
            # Normalize PCI address (remove 8-char domain prefix if present)
            pci_address = cls.normalize_pci_address(parts[0])
            
            gpu_info = GPUInfo(
                pci_address=pci_address,
                memory=parts[1].strip(),           # e.g., "15360 MiB"
                power=parts[2].strip(),            # e.g., "70.00 W"
                serial_number=parts[3].strip(),    # e.g., "ABC123"
            )
            gpu_infos.append(gpu_info)
        
        return gpu_infos
    
    # ==========================================================================
    # Prometheus Metrics Collection (REQUIRED)
    # ==========================================================================
    
    @classmethod
    def get_metric_cmd(cls, is_windows: bool = False) -> str:
        """
        Return command to get GPU metrics for Prometheus.
        
        The command output should contain:
        1. PCI Address
        2. GPU Utilization (%)
        3. Memory Utilization (%)
        4. Temperature (°C)
        5. Power Draw (W)
        6. Serial Number (for labels)
        7. (Optional) Fan Speed (%)
        8. (Optional) PCIe TX/RX throughput
        
        Args:
            is_windows: If True, replace spaces with "|" for Windows
            
        Returns:
            Command string
        """
        # TODO: Replace with actual command
        cmd = ("newvendor-smi --query=pci_addr,util_gpu,util_mem,temp,power,"
               "serial --format=csv,nounits")
        
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_metrics(cls, output: str) -> List[GPUMetrics]:
        """
        Parse metrics command output into GPUMetrics objects.
        
        Args:
            output: Raw command output string
            
        Returns:
            List of GPUMetrics objects
            
        Example output:
            0000:3B:00.0, 45, 62, 58, 65.23, ABC123
            0000:86:00.0, 30, 45, 52, 55.10, ABC124
        """
        gpu_metrics = []
        
        # TODO: Implement parsing logic for your metrics output
        # Example for CSV format (no units):
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) < 6:
                continue
            
            pci_address = cls.normalize_pci_address(parts[0])
            serial_number = parts[5].strip()
            
            # Parse numeric values (handle "N/A" or empty values)
            utilization = cls.parse_unit_value(parts[1])
            mem_utilization = cls.parse_unit_value(parts[2])
            temperature = cls.parse_unit_value(parts[3])
            power_draw = cls.parse_unit_value(parts[4])
            
            metrics = GPUMetrics(
                pci_address=pci_address,
                serial_number=serial_number,
                utilization=utilization,
                memory_utilization=mem_utilization,
                temperature=temperature,
                power_draw=power_draw,
                # fan_speed=None,       # Add if available
                # pcie_tx_bytes=None,   # Add if available
                # pcie_rx_bytes=None,   # Add if available
            )
            gpu_metrics.append(metrics)
        
        return gpu_metrics
    
    # ==========================================================================
    # Optional: Custom Prometheus Metrics
    # ==========================================================================
    
    @classmethod
    def get_custom_prometheus_metrics(cls) -> Dict[str, Tuple[str, str, List[str]]]:
        """
        Define vendor-specific custom metrics.
        
        Override this method to add metrics beyond the standard set.
        
        Returns:
            Dict of metric_name -> (help_text, metric_type, label_names)
        """
        # Example: Huawei adds DDR and HBM capacity metrics
        # return {
        #     "host_gpu_ddr_capacity": (
        #         "GPU DDR Capacity",
        #         "gauge",
        #         ["pci_device_address", "gpu_serial"]
        #     ),
        # }
        return {}
    
    # ==========================================================================
    # Optional: Pre-Detach Hooks
    # ==========================================================================
    
    @classmethod
    def pre_detach_from_vm(cls, domain, vm_uuid: str) -> Tuple[int, Optional[str]]:
        """
        Hook called before detaching GPU from VM.
        
        Override if special handling is needed before GPU is detached.
        For example, NVIDIA needs to stop nvidia-persistenced.
        
        Args:
            domain: libvirt domain object
            vm_uuid: VM UUID
            
        Returns:
            Tuple of (return_code, output_message)
        """
        # Default: no action needed
        return 0, None
    
    @classmethod
    def pre_detach_from_host(cls) -> Tuple[int, Optional[str]]:
        """
        Hook called before detaching GPU from host.
        
        Override if special handling is needed.
        
        Returns:
            Tuple of (return_code, output_message)
        """
        # Default: no action needed
        return 0, None
    
    # ==========================================================================
    # Optional: Post-Processing
    # ==========================================================================
    
    @classmethod
    def post_process_pci_device(cls, pci_device_to) -> None:
        """
        Post-process PCI device after collection.
        
        Override to modify the PCI device object.
        For example, Enflame sets virtStatus to UNVIRTUALIZABLE.
        
        Args:
            pci_device_to: The PCI device transfer object
        """
        # Example: mark device as not virtualizable
        # pci_device_to.virtStatus = "UNVIRTUALIZABLE"
        pass
    
    # ==========================================================================
    # Optional: Device Validation
    # ==========================================================================
    
    @classmethod
    def is_valid_device(cls, device_name: str, device_type: str) -> bool:
        """
        Validate if a PCI device should be recognized as GPU.
        
        Override for custom validation logic.
        
        Args:
            device_name: Device name from lspci (e.g., "Tesla T4")
            device_type: Device type (e.g., "3D controller")
            
        Returns:
            True if device should be recognized
        """
        # Example: filter out certain devices
        # invalid_keywords = {"iBMC", "Management"}
        # return not any(kw in device_name for kw in invalid_keywords)
        return True
    
    # ==========================================================================
    # Optional: vGPU/mdev Support
    # ==========================================================================
    
    @classmethod
    def collect_vgpu_metrics(cls) -> List[VGPUMetrics]:
        """
        Collect vGPU/mdev metrics.
        
        Override if vendor supports vGPU/mdev virtualization.
        
        Returns:
            List of VGPUMetrics objects
        """
        return []
    
    # ==========================================================================
    # Optional: VM Guest Tool Support
    # ==========================================================================
    
    @classmethod
    def get_vm_gpu_info_cmd(cls, is_windows: bool = False) -> str:
        """
        Get command to retrieve GPU info inside VM via guest agent.
        
        Override if different command is needed inside VM.
        Default uses get_basic_info_cmd.
        """
        return cls.get_basic_info_cmd(is_windows)
    
    @classmethod
    def parse_vm_gpu_info(cls, output: str) -> List[GPUInfo]:
        """
        Parse GPU info output from inside VM.
        
        Override if different parsing is needed inside VM.
        Default uses parse_basic_info.
        """
        return cls.parse_basic_info(output)


# =============================================================================
# Additional Helper Functions (if needed)
# =============================================================================

def _parse_newvendor_text_output(output: str) -> List[Dict[str, str]]:
    """
    Example helper function for parsing complex text output.
    
    Use this pattern for vendors with non-CSV output formats.
    
    Args:
        output: Raw text output
        
    Returns:
        List of parsed dictionaries
    """
    results = []
    current = {}
    
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            if current:
                results.append(current)
                current = {}
            continue
        
        if ':' in line:
            key, _, value = line.partition(':')
            current[key.strip()] = value.strip()
    
    if current:
        results.append(current)
    
    return results
