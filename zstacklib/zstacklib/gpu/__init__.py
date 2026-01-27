# -*- coding: utf-8 -*-
"""
GPU Vendor Plugin System

A pure data layer providing plugin-based architecture for GPU vendor support.
This module provides:
  - Abstract base class for GPU vendors
  - Data models (GPUInfo, GPUMetrics, VGPUMetrics)
  - Plugin registration and discovery mechanism
  - Vendor identification utilities

Usage in kvmagent (host_plugin, prometheus, etc.):
  from zstacklib.gpu import get_all_gpu_vendors, get_gpu_vendor
  
  # Get all registered GPU vendors
  for vendor_class in get_all_gpu_vendors():
      if vendor_class.is_available():
          metrics = vendor_class.collect_metrics()

To add a new vendor:
  1. Copy vendor_template.py to vendor_<name>.py
  2. Implement all abstract methods
  3. Set VENDOR_NAME, VENDOR_IDS, etc.
  4. Uncomment @register_gpu_vendor decorator
  5. Import vendor file below to auto-register

Architecture:
                    ┌─────────────────────┐
                    │   GPUVendorBase     │ (Abstract)
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────▼────┐          ┌─────▼─────┐         ┌─────▼─────┐
    │ NVIDIA  │          │   AMD     │         │ NewVendor │
    └─────────┘          └───────────┘         └───────────┘
"""

# =============================================================================
# Core exports: Base classes, data models, and registry
# =============================================================================
from zstacklib.gpu.base import (
    # Vendor enumeration
    VendorEnum,
    
    # Abstract base class
    GPUBase,
    
    # Data models
    GPUInfo,
    GPUMetrics,
    VGPUMetrics,
    
    # Registration decorator
    register_gpu_vendor,
    
    # Registry query functions
    get_gpu_vendor,
    get_all_gpu_vendors,
    get_gpu_vendor_names,
    get_vendor_enum_mapping,
    
    # Vendor identification (core utilities)
    get_vendor_by_id,
    get_vendor_by_pci_name,
    identify_vendor,
)

# =============================================================================
# Auto-register vendor implementations
# Import each vendor file to trigger @register_gpu_vendor decorator
# =============================================================================

# NVIDIA - Reference implementation (CSV format parsing)
from zstacklib.gpu.vendors import nvidia

# AMD - JSON output format example
from zstacklib.gpu.vendors import amd

# Huawei - Multi-device enumeration example
from zstacklib.gpu.vendors import huawei

# Tianshu
from zstacklib.gpu.vendors import tianshu

# Enflame
from zstacklib.gpu.vendors import enflame

# Vastai
from zstacklib.gpu.vendors import vastai

# Alibaba
from zstacklib.gpu.vendors import alibaba

# Haiguang
from zstacklib.gpu.vendors import haiguang

# Kunlunxin
from zstacklib.gpu.vendors import kunlunxin


__all__ = [
    # Vendor enumeration
    'VendorEnum',
    
    # Abstract base class
    'GPUBase',
    
    # Data models
    'GPUInfo',
    'GPUMetrics',
    'VGPUMetrics',
    
    # Registration
    'register_gpu_vendor',
    
    # Registry query
    'get_gpu_vendor',
    'get_all_gpu_vendors',
    'get_gpu_vendor_names',
    'get_vendor_enum_mapping',
    
    # Vendor identification
    'get_vendor_by_id',
    'get_vendor_by_pci_name',
    'identify_vendor',
]
