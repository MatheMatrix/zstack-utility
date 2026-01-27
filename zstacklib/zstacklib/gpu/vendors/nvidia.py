# -*- coding: utf-8 -*-
"""
NVIDIA GPU Vendor Implementation (Python 2/3 Compatible)
"""

import re
import threading

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


@register_gpu_vendor
class NVIDIA(GPUBase):
    """
    NVIDIA GPU vendor implementation.
    """
    
    # ==========================================================================
    # Vendor Identification
    # ==========================================================================
    
    VENDOR_NAME = "NVIDIA"
    VENDOR_ENUM_NAME = "NVIDIA"
    VENDOR_IDS = {"10de"}
    PCI_NAME_KEYWORDS = {"NVIDIA Corporation"}
    CLI_TOOL = "nvidia-smi"
    
    # Device types recognized as GPU
    DEVICE_TYPES = {"3D controller", "VGA compatible controller"}
    IS_GPU_VENDOR = True
    
    # ==========================================================================
    # Tool Availability
    # ==========================================================================
    
    # nvidia-persistenced state tracking
    _persistenced_active = False
    _persistenced_lock = threading.Lock()
    
    @classmethod
    def has_nvidia_gpu(cls):
        """Check if NVIDIA GPU is present"""
        if not cls.is_available():
            return False
        r, o, e = bash_roe("nvidia-smi -L")
        return r == 0 and o and len(o.strip()) > 0
    
    # ==========================================================================
    # Basic Information Collection
    # ==========================================================================
    
    @classmethod
    def get_basic_info_cmd(cls, is_windows=False):
        """
        nvidia-smi command to get basic GPU info.
        
        Output format (CSV):
        00000000:3B:00.0, 15360 MiB, 70.00 W, 1322519087621
        
        Fields:
        1. gpu_bus_id     - PCI address
        2. memory.total   - Total GPU memory
        3. power.limit    - Power limit
        4. gpu_serial     - Serial number
        """
        cmd = "nvidia-smi --query-gpu=gpu_bus_id,memory.total,power.limit,gpu_serial --format=csv,noheader"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_basic_info(cls, output):
        """
        Parse nvidia-smi basic info output.
        
        Input:
            00000000:3B:00.0, 15360 MiB, 70.00 W, 1322519087621
            
        Returns:
            List of GPUInfo objects
        """
        results = []
        if not output:
            return results
            
        for line in output.strip().split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
                
            pci_address = cls.normalize_pci_address(parts[0])
            # Keep original string format for memory and power (e.g., "15360 MiB", "70.00 W")
            memory = parts[1].strip()
            power = parts[2].strip()
            serial = parts[3].strip()
            
            results.append(GPUInfo(
                pci_address=pci_address,
                memory=memory,
                power=power,
                serial_number=serial
            ))
        return results

    # ==========================================================================
    # Prometheus Metrics Collection
    # ==========================================================================
    
    @classmethod
    def get_metric_cmd(cls, is_windows=False):
        """
        nvidia-smi command to get GPU metrics.
        
        Output format (CSV, no units):
        00000000:3B:00.0, 45, 62, 58, 65.23, 1322519087621
        
        Fields:
        1. gpu_bus_id          - PCI address
        2. utilization.gpu     - GPU utilization (%)
        3. utilization.memory  - Memory utilization (%)
        4. temperature.gpu     - GPU temperature (C)
        5. power.draw          - Current power draw (W)
        6. gpu_serial          - Serial number
        """
        cmd = "nvidia-smi --query-gpu=gpu_bus_id,utilization.gpu,utilization.memory,temperature.gpu,power.draw,gpu_serial --format=csv,noheader"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    @classmethod
    def parse_metrics(cls, output):
        """
        Parse nvidia-smi metrics output.
        
        Returns list of GPUMetrics objects.
        """
        results = []
        if not output:
            return results
            
        for line in output.strip().split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 6:
                continue
                
            pci_address = cls.normalize_pci_address(parts[0])
            util = cls.parse_unit_value(parts[1])
            mem_util = cls.parse_unit_value(parts[2])
            temp = cls.parse_unit_value(parts[3])
            power = cls.parse_unit_value(parts[4])
            serial = parts[5]
            
            metrics = GPUMetrics(
                pci_address=pci_address,
                serial_number=serial,
                utilization=util,
                memory_utilization=mem_util,
                temperature=temp,
                power_draw=power
            )
            
            # Try to get PCIe metrics if possible
            # ... (rest of the logic)
            results.append(metrics)
        return results

    @classmethod
    def collect_vgpu_metrics(cls):
        """
        Collect vGPU metrics from nvidia-smi vgpu command.
        
        Returns list of VGPUMetrics for each active vGPU.
        """
        r, output, _ = bash_roe("nvidia-smi vgpu -q")
        if r != 0 or "VM Name" not in output:
            return []
        
        vgpu_metrics = []
        vgpu_list = cls._parse_vgpu_output(output)
        
        for vgpu in vgpu_list:
            vm_uuid = vgpu.get("VM Name", "")
            mdev_uuid = vgpu.get("MDEV UUID", "").replace('-', '')
            
            utilization = None
            if vgpu.get("Gpu"):
                try:
                    utilization = float(vgpu["Gpu"].replace('%', '').strip())
                except ValueError:
                    pass
            
            mem_util = None
            if vgpu.get("Memory"):
                try:
                    mem_util = float(vgpu["Memory"].replace('%', '').strip())
                except ValueError:
                    pass
            
            metrics = VGPUMetrics(
                vm_uuid=vm_uuid,
                mdev_uuid=mdev_uuid,
                utilization=utilization,
                memory_utilization=mem_util,
            )
            vgpu_metrics.append(metrics)
        
        return vgpu_metrics
    
    @staticmethod
    def _parse_vgpu_output(output):
        """
        Parse nvidia-smi vgpu -q output into list of dicts.
        
        Output format:
            GPU 00000000:3B:00.0
                Active vGPUs: 1
                vGPU ID: 1
                    VM Name: test-vm
                    MDEV UUID: abc123
                    Gpu: 45%
                    Memory: 62%
        """
        vgpus = []
        current_vgpu = None
        
        for line in output.split('\n'):
            line = line.rstrip()
            if not line:
                continue
            
            # Detect vGPU section start
            if 'vGPU ID:' in line:
                if current_vgpu:
                    vgpus.append(current_vgpu)
                current_vgpu = {}
                continue
            
            # Parse key-value pairs
            if current_vgpu is not None and ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                if key and value:
                    current_vgpu[key] = value
        
        if current_vgpu:
            vgpus.append(current_vgpu)
        
        return vgpus
    
    # ==========================================================================
    # Pre-Detach Hooks
    # ==========================================================================
    
    @classmethod
    def pre_detach_from_vm(cls, domain, vm_uuid):
        """
        Stop nvidia-persistenced in VM before GPU detach.
        
        This prevents the VM from holding GPU resources.
        """
        from zstacklib.utils.qga import VmQga
        
        if not domain or not domain.isActive():
            logger.info("No need to shutdown nvidia-persistenced for VM %s, not running" % vm_uuid)
            return 0, None
        
        logger.info("Shutting down nvidia-persistenced for VM %s" % vm_uuid)
        
        qga = VmQga(domain)
        if qga.state != VmQga.QGA_STATE_RUNNING:
            return 0, "QGA not running for VM %s, skipping" % vm_uuid
        
        is_windows = "mswindows" in qga.os
        cmd = cls.get_shut_persistenced_cmd(is_windows)
        
        if is_windows:
            exitcode, ret_data = qga.guest_exec_powershell(cmd)
        else:
            exitcode, ret_data, _ = qga.guest_exec_bash(cmd)
        
        return exitcode, ret_data
    
    @classmethod
    def pre_detach_from_host(cls):
        """Stop nvidia-persistenced on host before GPU detach"""
        logger.info("Shutting down nvidia-persistenced on host")
        cmd = cls.get_shut_persistenced_cmd()
        r, o, _ = bash_roe(cmd)
        return r, o
    
    @classmethod
    def get_shut_persistenced_cmd(cls, is_windows=False):
        """Get command to shut down nvidia-persistenced"""
        cmd = "ps -ef | grep nvidia-persistenced | grep -v grep | awk '{print $2}' | xargs -r kill -15"
        if is_windows:
            cmd = cmd.replace(" ", "|")
        return cmd
    
    # ==========================================================================
    # Persistenced Management
    # ==========================================================================
    
    @classmethod
    def ensure_persistenced_running(cls, timeout=5):
        """
        Ensure nvidia-persistenced is running.
        
        This daemon keeps the GPU initialized and improves startup latency.
        """
        with cls._persistenced_lock:
            # Check if already running
            r, o, _ = bash_roe("pgrep -f nvidia-persistenced || true")
            is_running = bool(o and o.strip())
            
            if is_running:
                cls._persistenced_active = True
                return True
            
            if cls._persistenced_active:
                cls._persistenced_active = False
                logger.debug("nvidia-persistenced stopped, will retry next cycle")
                return True
            
            # Start persistenced
            start_cmd = "nohup nvidia-persistenced >/dev/null 2>&1 &"
            logger.info("Starting nvidia-persistenced: %s" % start_cmd)
            bash_roe(start_cmd)
            
            # Wait and verify
            import time
            time.sleep(timeout)
            r, o, _ = bash_roe("pgrep -f nvidia-persistenced || true")
            if o and o.strip():
                cls._persistenced_active = True
                return True
            else:
                logger.warn("nvidia-persistenced failed to start")
                return False
    
    # ==========================================================================
    # VM Guest Tool Support
    # ==========================================================================
    
    @classmethod
    def get_vm_gpu_info_cmd(cls, is_windows=False):
        """Same command works inside VM"""
        return cls.get_basic_info_cmd(is_windows)
    
    @classmethod
    def parse_vm_gpu_info(cls, output):
        """Same parsing works inside VM"""
        return cls.parse_basic_info(output)
