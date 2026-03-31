"""Linux system models.

This module defines data models for Linux system information.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DistroInfo:
    """Linux distribution information."""
    
    name: str
    """Distribution name (e.g., 'centos', 'ubuntu', 'kylin10')."""
    
    version: str = ""
    """Distribution version string."""
    
    version_id: str = ""
    """Distribution version ID (e.g., '7', '20.04')."""
    
    pretty_name: str = ""
    """Human-readable distribution name."""
    
    id_like: list[str] = field(default_factory=list)
    """List of similar distributions (e.g., ['rhel', 'fedora'])."""
    
    def is_redhat_based(self) -> bool:
        """Check if this is a Red Hat based distribution."""
        redhat_distros = {'redhat', 'centos', 'alibaba', 'alinux', 'kylin10', 'rocky', 'rhel', 'fedora', 'openeuler'}
        return self.name.lower() in redhat_distros or any(d in redhat_distros for d in self.id_like)
    
    def is_debian_based(self) -> bool:
        """Check if this is a Debian based distribution."""
        debian_distros = {'uos', 'kylin4.0.2', 'debian', 'ubuntu', 'uniontech'}
        return self.name.lower() in debian_distros or 'debian' in self.id_like or 'ubuntu' in self.id_like


@dataclass
class KernelInfo:
    """Linux kernel information."""
    
    version: str
    """Full kernel version string (e.g., '5.4.0-150-generic')."""
    
    release: str = ""
    """Kernel release string."""
    
    major: int = 0
    """Major version number."""
    
    minor: int = 0
    """Minor version number."""
    
    patch: int = 0
    """Patch version number."""
    
    def __post_init__(self):
        """Parse version string to extract major, minor, patch."""
        if self.version and not (self.major or self.minor or self.patch):
            parts = self.version.split('.')
            if len(parts) >= 1:
                try:
                    self.major = int(parts[0])
                except ValueError:
                    pass
            if len(parts) >= 2:
                try:
                    self.minor = int(parts[1])
                except ValueError:
                    pass
            if len(parts) >= 3:
                # Handle versions like "5.4.0-150-generic"
                patch_str = parts[2].split('-')[0]
                try:
                    self.patch = int(patch_str)
                except ValueError:
                    pass
    
    def is_at_least(self, major: int, minor: int = 0, patch: int = 0) -> bool:
        """Check if kernel version is at least the specified version."""
        return (self.major, self.minor, self.patch) >= (major, minor, patch)


@dataclass
class SystemInfo:
    """Combined Linux system information."""
    
    distro: DistroInfo
    """Distribution information."""
    
    kernel: KernelInfo
    """Kernel information."""
    
    arch: str
    """CPU architecture (e.g., 'x86_64', 'aarch64')."""
    
    hostname: str = ""
    """System hostname."""
    
    fqdn: str = ""
    """Fully qualified domain name."""


# Supported architectures
SUPPORTED_ARCH = ['x86_64', 'aarch64', 'mips64el', 'loongarch64']

# Red Hat based distributions
RPM_BASED_OS = ['redhat', 'centos', 'alibaba', 'alinux', 'kylin10', 'rocky']

# Debian based distributions
DEB_BASED_OS = ['uos', 'kylin4.0.2', 'debian', 'ubuntu', 'uniontech']

# ARM ACPI support OS
ARM_ACPI_SUPPORT_OS = ['kylin10', 'openEuler20.03']

# Distributions that support both RPM and DEB
DIST_WITH_RPM_DEB = ['kylin']
