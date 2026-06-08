"""Linux distribution detection.

This module provides functions to detect Linux distribution information.
"""
from __future__ import annotations

import os
import re

from .models import DistroInfo, RPM_BASED_OS, DEB_BASED_OS
from .exceptions import DistroError


def get_distro() -> DistroInfo:
    """Detect the current Linux distribution.
    
    Returns:
        DistroInfo object with distribution details.
        
    Raises:
        DistroError: If distribution cannot be detected.
    """
    # Try /etc/os-release first (modern method)
    if os.path.exists('/etc/os-release'):
        return _parse_os_release('/etc/os-release')
    
    # Fallback to /etc/redhat-release
    if os.path.exists('/etc/redhat-release'):
        return _parse_redhat_release('/etc/redhat-release')
    
    # Fallback to /etc/debian_version
    if os.path.exists('/etc/debian_version'):
        return _parse_debian_version('/etc/debian_version')
    
    raise DistroError("Cannot detect Linux distribution")


def _parse_os_release(path: str) -> DistroInfo:
    """Parse /etc/os-release file.
    
    Args:
        path: Path to os-release file.
        
    Returns:
        DistroInfo object.
    """
    data = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                key, _, value = line.partition('=')
                # Remove quotes
                value = value.strip('"\'')
                data[key] = value
    
    name = data.get('ID', 'unknown')
    version = data.get('VERSION', '')
    version_id = data.get('VERSION_ID', '')
    pretty_name = data.get('PRETTY_NAME', name)
    id_like = data.get('ID_LIKE', '').split()
    
    return DistroInfo(
        name=name,
        version=version,
        version_id=version_id,
        pretty_name=pretty_name,
        id_like=id_like
    )


def _parse_redhat_release(path: str) -> DistroInfo:
    """Parse /etc/redhat-release file.
    
    Args:
        path: Path to redhat-release file.
        
    Returns:
        DistroInfo object.
    """
    with open(path, 'r') as f:
        content = f.read().strip()
    
    # Parse lines like "CentOS Linux release 7.9.2009 (Core)"
    name = 'redhat'
    version = ''
    
    if 'centos' in content.lower():
        name = 'centos'
    elif 'rocky' in content.lower():
        name = 'rocky'
    elif 'alibaba' in content.lower():
        name = 'alibaba'
    
    # Extract version
    match = re.search(r'release\s+(\d+(?:\.\d+)*)', content)
    if match:
        version = match.group(1)
    
    return DistroInfo(
        name=name,
        version=version,
        version_id=version.split('.')[0] if version else '',
        pretty_name=content,
        id_like=['rhel', 'fedora']
    )


def _parse_debian_version(path: str) -> DistroInfo:
    """Parse /etc/debian_version file.
    
    Args:
        path: Path to debian_version file.
        
    Returns:
        DistroInfo object.
    """
    with open(path, 'r') as f:
        version = f.read().strip()
    
    return DistroInfo(
        name='debian',
        version=version,
        version_id=version.split('.')[0] if version else '',
        pretty_name=f'Debian {version}',
        id_like=[]
    )


def is_redhat_based(distro: DistroInfo | None = None) -> bool:
    """Check if the current system is Red Hat based.
    
    Args:
        distro: Optional DistroInfo. If None, detects current distro.
        
    Returns:
        True if Red Hat based.
    """
    if distro is None:
        try:
            distro = get_distro()
        except DistroError:
            return False
    return distro.is_redhat_based()


def is_debian_based(distro: DistroInfo | None = None) -> bool:
    """Check if the current system is Debian based.
    
    Args:
        distro: Optional DistroInfo. If None, detects current distro.
        
    Returns:
        True if Debian based.
    """
    if distro is None:
        try:
            distro = get_distro()
        except DistroError:
            return False
    return distro.is_debian_based()


def get_distro_name() -> str:
    """Get the distribution name.
    
    Returns:
        Distribution name string.
    """
    try:
        return get_distro().name
    except DistroError:
        return 'unknown'
