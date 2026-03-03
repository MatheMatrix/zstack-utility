# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch environment preparation.

Provides the OvsVenv class for preparing OVS workspace and environment.
"""

from __future__ import annotations

import glob
import logging
import os
import time
import yaml

from zstacklib.utils import shell

from .config import (
    CONF_PATH, LOG_PATH, OVS_RUN_PATH, SOCK_PATH,
    SMART_NIC_CONFIG_FILE, DEFAULT_HUGEPAGE_SIZE, DEFAULT_NR_HUGEPAGES,
    HUGEPAGES_PATHS,
)
from .exceptions import OvsError
from .models import OvsVersionInfo
from .utils import read_sysfs, write_sysfs, probe_module, get_numa_nodes


logger = logging.getLogger(__name__)


class OvsVenv:
    """OVS environment manager with singleton-like caching.

    Prepares OVS workspace and environment including:
    - Mellanox OFED driver
    - Hugepages (created during vswitchd starting process)
    - SmartNIC offload status
    - Configuration/log/sock directories

    Attributes:
        version_info: OVS version information.
        offload_status: SmartNIC offload status mapping.
        numa_nodes: Number of NUMA nodes.
        hugepage_size: Hugepage size in KB.
        nr_hugepages: Number of hugepages to allocate.
    """

    __cache__: list = []  # [timestamp, OvsVenv instance]

    def __new__(cls):
        """New."""
        # Return cached instance if less than 60 seconds old
        if len(cls.__cache__) == 2 and (time.time() - cls.__cache__[0]) <= 60:
            cls.__cache__[0] = time.time()
            return cls.__cache__[1]

        obj = super().__new__(cls)
        obj._init()
        cls.__cache__ = [int(time.time()), obj]
        return obj

    def _init(
        self,
        hugepage_size: int = DEFAULT_HUGEPAGE_SIZE,
        nr_hugepages: int = DEFAULT_NR_HUGEPAGES
    ) -> None:
        """Initialize the OVS environment."""
        self.version_info = OvsVersionInfo()
        self.offload_status: dict[str, str] = {}
        self.numa_nodes = get_numa_nodes()
        self.hugepage_size = hugepage_size
        self.nr_hugepages = nr_hugepages

        if self._has_openvswitch():
            probe_module('bonding')
            self._get_openvswitch_version()
            self._fill_nic_offload_status()
            self._make_dir_for_ovs()

    def _has_openvswitch(self) -> bool:
        """Check if OVS binaries are installed."""
        return (
            os.path.exists('/usr/bin/ovs-vsctl') and
            os.path.exists('/usr/sbin/ovs-vswitchd') and
            os.path.exists('/usr/sbin/ovsdb-server')
        )

    def _get_openvswitch_version(self) -> None:
        """Get OVS version information."""
        ver_list = shell.call(
            "ovs-vswitchd --version | grep -E 'DPDK|vSwitch'"
        ).splitlines()

        if len(ver_list) > 0 and ver_list[0] != '':
            self.version_info.vswitch_ver = ver_list[0].split()[-1]
        if len(ver_list) > 1 and ver_list[1] != '':
            self.version_info.dpdk_ver = ver_list[1].split()[-1]

        self.version_info.ovsdb_ver = shell.call(
            "ovsdb-server --version | awk 'NR==1{print $NF}'"
        ).strip()

        if os.path.exists('/usr/bin/ofed_info'):
            self.version_info.ofed_ver = shell.call('ofed_info -n').strip()

    def _fill_nic_offload_status(self) -> None:
        """Load SmartNIC offload status from config file."""
        nic_info_path = os.path.join(CONF_PATH, SMART_NIC_CONFIG_FILE)
        if not os.path.exists(nic_info_path):
            logger.debug(f'SmartNIC config not found: {nic_info_path}')
            return

        with open(nic_info_path, 'r') as f:
            data = yaml.safe_load(f)

        if data:
            for item in data:
                self.offload_status[str(item['nic']['vendor_device'])] = '|'.join(
                    str(x) for x in item['nic']['offloadstatus']
                )

    def _get_hugepage_info_by_node(self, numa_node_path: str) -> tuple[int, int]:
        """Get hugepage info for a NUMA node.

        Returns:
            Tuple of (free_hugepages, nr_hugepages).
        """
        hugepages_path = os.path.join(
            numa_node_path, HUGEPAGES_PATHS[self.hugepage_size]
        )

        free_hugepages = int(
            read_sysfs(os.path.join(hugepages_path, 'free_hugepages'))
        )
        nr_hugepages = int(
            read_sysfs(os.path.join(hugepages_path, 'nr_hugepages'))
        )
        return free_hugepages, nr_hugepages

    def _get_free_mem_by_node(self, numa_node_path: str) -> int:
        """Get free memory for a NUMA node in KB."""
        meminfo = {}
        with open(os.path.join(numa_node_path, 'meminfo'), 'r') as f:
            for line in f:
                parts = line.split(':')
                meminfo[parts[0].split()[-1].strip()] = parts[1].strip()

        mem_free = int(meminfo['MemFree'].split()[0])
        return mem_free

    def _make_dir_for_ovs(self) -> None:
        """Create required directories for OVS."""
        for path in [OVS_RUN_PATH, LOG_PATH, SOCK_PATH, CONF_PATH]:
            if not os.path.isdir(path):
                os.makedirs(path, 0o755)

    def allocate_hugepage_mem(self) -> None:
        """Prepare hugepages for DPDK.

        Allocates hugepages in all NUMA nodes since we can't determine
        which node the DPDK device is located in. 2GB is enough for
        shared memory mode.

        Raises:
            OvsError: If unable to allocate enough hugepages.
        """
        numa_node_paths = glob.glob('/sys/devices/system/node/node*/')
        if self.numa_nodes < 1:
            raise OvsError('can not find numa node.')

        for numa_node_path in numa_node_paths:
            free_hugepages, nr_hugepages = self._get_hugepage_info_by_node(
                numa_node_path
            )
            mem_free = self._get_free_mem_by_node(numa_node_path)

            # Free hugepages are enough for DPDK
            if free_hugepages >= self.nr_hugepages:
                continue

            pages_need_allocate = self.nr_hugepages + (nr_hugepages - free_hugepages)
            need_free_mem = self.nr_hugepages - free_hugepages

            # Check if current free memory is enough
            if mem_free < need_free_mem * self.hugepage_size:
                raise OvsError(
                    f'could not malloc enough hugepage for ovs dpdk, '
                    f'{pages_need_allocate * self.hugepage_size} expected but {mem_free} left.'
                )

            write_sysfs(
                os.path.join(
                    numa_node_path,
                    HUGEPAGES_PATHS[self.hugepage_size],
                    'nr_hugepages'
                ),
                str(pages_need_allocate)
            )

    def is_dpdk_support(self) -> bool:
        """Check if DPDK is supported."""
        return self.version_info.is_dpdk_support()

    def is_mellanox_support(self) -> bool:
        """Check if Mellanox OFED is available."""
        return self.version_info.is_mellanox_support()
