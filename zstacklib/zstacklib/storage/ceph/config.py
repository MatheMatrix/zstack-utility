# Copyright (c) ZStack.io, Inc.

"""
Ceph client configuration management.

This module handles Ceph client configuration including keyring
and ceph.conf file management.
"""

import os
from typing import Tuple, Optional

from zstacklib.utils import linux

from .models import (
    CEPH_CONF_ROOT, CEPH_KEYRING_CONFIG_NAME, CEPH_CONF_FILENAME,
    MANUFACTURER_XSKY
)


def get_ceph_client_conf(ps_uuid, manufacturer=None):
    # type: (str, Optional[str]) -> Tuple[str, Optional[str], Optional[str]]
    """
    Get Ceph client configuration paths.
    
    Args:
        ps_uuid: Primary storage UUID.
        manufacturer: Ceph manufacturer (xsky, sandstone, open-source).
        
    Returns:
        Tuple of (conf_path, keyring_path, username).
        keyring_path may be None if no keyring file exists.
        username may be None for xsky (uses admin).
    """
    ceph_client_config_dir = os.path.join(CEPH_CONF_ROOT, ps_uuid)
    
    # xsky uses admin to access mon node
    # other ceph storages (e.g., open-source) use client.zstack
    username = None  # type: Optional[str]
    if manufacturer != MANUFACTURER_XSKY:
        username = "client.zstack"
    
    key_path = os.path.join(ceph_client_config_dir, CEPH_KEYRING_CONFIG_NAME)
    # set key_path to None if no keyring config file exists
    if not os.path.exists(key_path):
        key_path = None
    
    return os.path.join(ceph_client_config_dir, "ceph.conf"), key_path, username


def update_ceph_client_access_conf(ps_uuid, mon_urls, user_key, manufacturer, fsid, ceph_conf=CEPH_CONF_FILENAME):
    # type: (str, list, Optional[str], str, str, str) -> Tuple[str, Optional[str], Optional[str]]
    """
    Update Ceph client access configuration.
    
    Creates or updates the ceph.conf and keyring files for client access.
    
    Args:
        ps_uuid: Primary storage UUID.
        mon_urls: List of monitor URLs.
        user_key: User key for authentication.
        manufacturer: Ceph manufacturer.
        fsid: Ceph cluster FSID.
        ceph_conf: Configuration filename (default: ceph.conf).
        
    Returns:
        Tuple of (conf_path, keyring_path, username).
    """
    conf_folder = os.path.join(CEPH_CONF_ROOT, ps_uuid)
    if not os.path.exists(conf_folder):
        linux.mkdir(conf_folder)
    
    conf_content = '[global]\nfsid = %s\nmon_host=%s\n' % (fsid, ','.join(mon_urls))
    
    # key used for ceph client keyring configuration
    keyring_path = None  # type: Optional[str]
    username = None  # type: Optional[str]
    
    if user_key:
        keyring_content = None  # type: Optional[str]
        # xsky keyring file just contains the keyring string
        # but other ceph storages use formatted keyring file:
        # [client.zstack]
        #     key = your user key for client.zstack
        if manufacturer == MANUFACTURER_XSKY:
            keyring_content = user_key
        else:
            username = "client.zstack"
            keyring_content = """[client.zstack]
    key = %s
""" % user_key
        
        keyring_path = os.path.join(conf_folder, CEPH_KEYRING_CONFIG_NAME)
        with open(keyring_path, 'w') as fd:
            fd.write(keyring_content)
        
        # add \n because of ZSTAC-43092
        conf_content = conf_content + "keyring=%s\n" % keyring_path
    
    conf_path = os.path.join(conf_folder, ceph_conf)
    with open(conf_path, 'w') as fd:
        fd.write(conf_content)
    
    return conf_path, keyring_path, username


def get_heartbeat_object_name(primary_storage_uuid, host_uuid):
    # type: (str, str) -> str
    """
    Generate heartbeat object name for host health monitoring.
    
    Args:
        primary_storage_uuid: Primary storage UUID.
        host_uuid: Host UUID.
        
    Returns:
        Heartbeat object name.
    """
    return 'ceph-ps-%s-host-hb-%s' % (primary_storage_uuid, host_uuid)
