# Copyright (c) ZStack.io, Inc.

"""
Ceph NBD (Network Block Device) remote storage.

This module provides NBD-based remote storage access for Ceph RBD images.
"""

import os
from typing import Optional

from zstacklib.utils import shell
from zstacklib.utils import linux
from zstacklib.utils import remoteStorage
from zstacklib.utils.linux import get_fs_type, check_nbd

from .models import QEMU_NBD_SOCKET_DIR, QEMU_NBD_SOCKET_PREFIX, NBD_DEV_PREFIX
from .config import get_ceph_client_conf
from .utils import get_ceph_manufacturer
from .exceptions import CephNbdError


class NbdRemoteStorage(remoteStorage.RemoteStorage):
    """
    NBD-based remote storage for Ceph RBD images.
    
    Provides mount/umount operations using qemu-nbd to expose
    Ceph RBD images as local block devices.
    """
    
    # Constants for path parsing
    POOL_NAME = 1
    IMAGE = 2
    DEVICE = 4
    
    def __init__(self, volume_install_path, mount_path, volume_mounted_device, ps_uuid=None):
        # type: (str, str, Optional[str], Optional[str]) -> None
        """
        Initialize NBD remote storage.
        
        Args:
            volume_install_path: Ceph volume path (ceph://pool/image).
            mount_path: Local mount point path.
            volume_mounted_device: Previously mounted device path (if any).
            ps_uuid: Primary storage UUID.
        """
        super(NbdRemoteStorage, self).__init__(mount_path, volume_mounted_device)
        self.normalize_install_path = volume_install_path.replace('ceph://', '')
        self.ps_uuid = ps_uuid
        self.nbd_dev = None  # type: Optional[str]
        self.cmd = None  # type: Optional[str]
    
    @staticmethod
    def check_nbd_dev_empty(nbd_id):
        # type: (int) -> bool
        """
        Check if an NBD device is empty (not connected).
        
        Args:
            nbd_id: NBD device ID number.
            
        Returns:
            True if device is empty, False if in use.
        """
        with open('/sys/block/nbd{}/size'.format(nbd_id), 'r') as f:
            size = f.read()
        return int(size) == 0
    
    def get_available_nbd_dev(self):
        # type: () -> Optional[str]
        """
        Find an available NBD device.
        
        Returns:
            Path to available NBD device, or None if none available.
            
        Raises:
            CephNbdError: If no NBD devices are available.
        """
        block_devices = os.listdir('/sys/block/')
        all_nbd_ids = []
        for dev in block_devices:
            if dev.startswith('nbd'):
                all_nbd_ids.append(int(dev.split('nbd')[-1]))
        available_nbd_ids = sorted(set(all_nbd_ids))
        
        if not available_nbd_ids:
            raise CephNbdError(
                'Cannot find available nbd device. Try increasing `nbds_max` param during modprobe nbd'
            )
        
        for nbd_id in available_nbd_ids:
            if self.check_nbd_dev_empty(nbd_id):
                return NBD_DEV_PREFIX + str(nbd_id)
        return None
    
    def get_cmd(self):
        # type: () -> None
        """Build the qemu-nbd command for connecting to Ceph RBD."""
        self.nbd_dev = self.get_available_nbd_dev()
        conf_path, _, username = get_ceph_client_conf(self.ps_uuid, get_ceph_manufacturer())
        
        if username is not None:
            name = username.split(".")[-1]
            self.cmd = 'qemu-nbd -f raw -c %s rbd:%s:id=%s:conf=%s' % (
                self.nbd_dev, self.normalize_install_path, name, conf_path
            )
        else:
            self.cmd = 'qemu-nbd -f raw -c %s rbd:%s:conf=%s' % (
                self.nbd_dev, self.normalize_install_path, conf_path
            )
    
    def qemu_nbd_socket_is_exists(self, qemu_nbd_socket):
        # type: (str) -> Optional[str]
        """
        Check if a qemu-nbd socket exists.
        
        Args:
            qemu_nbd_socket: Socket name to check.
            
        Returns:
            Mounted device path if socket exists, None otherwise.
        """
        for nbd_socket in os.listdir(QEMU_NBD_SOCKET_DIR):
            if qemu_nbd_socket == nbd_socket:
                return self.volume_mounted_device
        return None
    
    def build_qemu_nbd_socket_name(self):
        # type: () -> str
        """Build the qemu-nbd socket name for this device."""
        nbd_id = self.volume_mounted_device.split(NBD_DEV_PREFIX)[-1]
        return QEMU_NBD_SOCKET_PREFIX + str(nbd_id)
    
    def do_mount(self, fstype=None):
        # type: (Optional[str]) -> str
        """
        Perform the actual mount operation.
        
        Args:
            fstype: Filesystem type to create (if creating new filesystem).
            
        Returns:
            NBD device path that was mounted.
            
        Raises:
            Exception: If mount fails (cleans up NBD connection).
        """
        try:
            check_nbd()
            self.get_cmd()
            shell.call(self.cmd)
            if fstype is not None:
                shell.call('mkfs -F -t %s %s' % (fstype, self.nbd_dev))
            linux.mount(self.nbd_dev, self.mount_path)
        except Exception as e:
            if self.nbd_dev is not None:
                shell.call('qemu-nbd -d %s' % self.nbd_dev)
            raise e
        return self.nbd_dev
    
    def mount(self):
        # type: () -> str
        """
        Mount the Ceph RBD image via NBD.
        
        Handles various scenarios:
        - Already mounted
        - Socket exists but not mounted
        - Fresh mount required
        
        Returns:
            NBD device path.
        """
        if self.volume_mounted_device is not None:
            cmd = shell.ShellCmd("mountpoint %s" % self.mount_path)
            cmd(is_exception=False)
            if cmd.return_code == 0:
                return self.volume_mounted_device
            if self.qemu_nbd_socket_is_exists(self.build_qemu_nbd_socket_name()) is not None:
                linux.mount(self.volume_mounted_device, self.mount_path)
                return self.volume_mounted_device
            else:
                return self.do_mount()
        
        if not os.path.isdir(self.mount_path):
            linux.mkdir(self.mount_path)
        
        fstype = get_fs_type(self.mount_path)
        return self.do_mount(fstype)
    
    def umount(self):
        # type: () -> None
        """
        Unmount the Ceph RBD image and disconnect NBD.
        
        Unmounts the filesystem and disconnects the qemu-nbd connection.
        """
        from zstacklib.utils import bash
        device_and_mount_path = bash.bash_o("mount | grep %s" % self.mount_path)
        if len(device_and_mount_path) != 0:
            shell.call('umount -f %s' % self.mount_path)
        shell.call("qemu-nbd -d %s" % self.volume_mounted_device)
