# Copyright (c) ZStack.io, Inc.

"""
Network namespace operations.

Provides functions for creating, deleting, and managing network namespaces.
"""

import os
from typing import List, Optional

from .decorators import log_iproute_call, no_error_do
from .exceptions import NamespaceAlreadyExists, NoSuchNamespace

# Path where network namespaces are stored
NETNS_RUN_DIR = '/var/run/netns'


def query_all_namespaces():
    # type: () -> List[str]
    """
    List all network namespaces.
    
    Equivalent to: ip netns list
    
    Returns:
        List of namespace names
    
    Note:
        Caller requires elevated privileges to list namespaces.
    """
    import pyroute2.netns
    return pyroute2.netns.listnetns()


def is_namespace_exists(namespace):
    # type: (str) -> bool
    """
    Check if a network namespace exists.
    
    Args:
        namespace: Namespace name to check
    
    Returns:
        True if the namespace exists, False otherwise
    """
    for name in query_all_namespaces():
        if name == namespace:
            return True
    return False


@log_iproute_call("netns add")
def add_namespace(namespace):
    # type: (str) -> None
    """
    Create a network namespace.
    
    Equivalent to: ip netns add {namespace}
    
    This is adapted from openstack/neutron.
    
    Args:
        namespace: Name for the new namespace
    
    Raises:
        NamespaceAlreadyExists: If the namespace already exists
        OSError: If namespace creation fails for other reasons
    """
    import pyroute2.netns
    import errno
    
    try:
        pyroute2.netns.create(namespace)
    except OSError as e:
        if e.errno == errno.EEXIST:
            raise NamespaceAlreadyExists(namespace)
        raise


@no_error_do
def add_namespace_no_error(namespace):
    # type: (str) -> bool
    """
    Create a namespace, returning False on error instead of raising.
    
    Args:
        namespace: Name for the new namespace
    
    Returns:
        True on success, False on error
    """
    add_namespace(namespace)
    return True


@log_iproute_call("netns delete")
def delete_namespace(namespace):
    # type: (str) -> None
    """
    Delete a network namespace.
    
    Equivalent to: ip netns del {namespace}
    
    This is adapted from openstack/neutron.
    
    Args:
        namespace: Name of the namespace to delete
    
    Raises:
        NoSuchNamespace: If the namespace does not exist
        OSError: If namespace deletion fails for other reasons
    """
    import pyroute2.netns
    import errno
    
    try:
        pyroute2.netns.remove(namespace)
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise NoSuchNamespace(namespace)
        raise


def delete_namespace_if_exists(namespace):
    # type: (str) -> bool
    """
    Delete a network namespace if it exists.
    
    This is adapted from openstack/neutron.
    
    Args:
        namespace: Name of the namespace to delete
    
    Returns:
        True if the namespace was deleted, False if it didn't exist
    """
    if is_namespace_exists(namespace):
        try:
            delete_namespace(namespace)
            return True
        except NoSuchNamespace:
            # Someone else deleted it
            return False
    return False


@no_error_do
def delete_namespace_no_error(namespace):
    # type: (str) -> bool
    """
    Delete a namespace, returning False on error instead of raising.
    
    Args:
        namespace: Name of the namespace to delete
    
    Returns:
        True on success, False on error
    """
    delete_namespace(namespace)
    return True


def list_namespace_pids(namespace):
    # type: (str) -> List[int]
    """
    List PIDs of processes in a network namespace.
    
    This is adapted from openstack/neutron.
    
    Args:
        namespace: Name of the namespace
    
    Returns:
        List of process IDs running in the namespace
    """
    ns_pids = []  # type: List[int]
    
    try:
        ns_path = os.path.join(NETNS_RUN_DIR, namespace)
        ns_inode = os.stat(ns_path).st_ino
    except OSError:
        return ns_pids
    
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        try:
            pid_path = os.path.join('/proc', pid, 'ns', 'net')
            if os.stat(pid_path).st_ino == ns_inode:
                ns_pids.append(int(pid))
        except OSError:
            continue
    
    return ns_pids


# Backward compatibility aliases
create_namespace = add_namespace
remove_namespace = delete_namespace
