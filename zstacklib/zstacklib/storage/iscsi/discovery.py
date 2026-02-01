"""iSCSI target discovery operations.

This module provides functions for discovering iSCSI targets:

- discover_targets(): Discover targets on a portal using sendtargets
- list_discovered_targets(): List previously discovered targets
- parse_discovery_output(): Parse iscsiadm discovery output
"""

import logging
from typing import List, Optional, Tuple

from zstacklib.utils import bash, lock

from .exceptions import DiscoveryError, TargetNotFoundError
from .models import IscsiPortal, IscsiTarget, DiscoveryResult


logger = logging.getLogger(__name__)

# Default timeout for discovery operations
DEFAULT_DISCOVERY_TIMEOUT = 10


@lock.lock('iscsiadm')
def discover_targets(
    ip: str,
    port: int = 3260,
    timeout: int = DEFAULT_DISCOVERY_TIMEOUT
) -> List[IscsiTarget]:
    """Discover iSCSI targets on a portal using sendtargets.
    
    This function performs iSCSI target discovery by sending a SendTargets
    request to the specified portal.
    
    Args:
        ip: iSCSI portal IP address
        port: iSCSI portal port (default 3260)
        timeout: Command timeout in seconds (default 10)
        
    Returns:
        List of IscsiTarget objects discovered on the portal
        
    Raises:
        DiscoveryError: If discovery fails
        
    Example:
        >>> targets = discover_targets('192.168.1.100', 3260)
        >>> for t in targets:
        ...     print(t.iqn)
        iqn.2020-01.com.example:storage
    """
    portal = IscsiPortal(ip=ip, port=port)
    portal_str = str(portal)
    
    logger.debug("Discovering iSCSI targets on portal %s", portal_str)
    
    cmd = "timeout {} iscsiadm -m discovery --type sendtargets --portal {}".format(
        timeout, portal_str
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        logger.error("iSCSI discovery failed on %s: %s", portal_str, e)
        raise DiscoveryError(
            portal=portal_str,
            message="Failed to discover targets: {}".format(e.strip() if e else "unknown error"),
            return_code=r
        )
    
    targets = parse_discovery_output(o, portal)
    logger.info("Discovered %d targets on portal %s", len(targets), portal_str)
    
    return targets


def discover_targets_safe(
    ip: str,
    port: int = 3260,
    timeout: int = DEFAULT_DISCOVERY_TIMEOUT
) -> DiscoveryResult:
    """Discover iSCSI targets with error handling (no exceptions).
    
    This is a safe version of discover_targets that returns a DiscoveryResult
    instead of raising exceptions.
    
    Args:
        ip: iSCSI portal IP address
        port: iSCSI portal port (default 3260)
        timeout: Command timeout in seconds (default 10)
        
    Returns:
        DiscoveryResult with targets list and success status
        
    Example:
        >>> result = discover_targets_safe('192.168.1.100')
        >>> if result.success:
        ...     for t in result.targets:
        ...         print(t.iqn)
        ... else:
        ...     print(f"Discovery failed: {result.error}")
    """
    portal = IscsiPortal(ip=ip, port=port)
    
    try:
        targets = discover_targets(ip, port, timeout)
        return DiscoveryResult(portal=portal, targets=targets, success=True)
    except DiscoveryError as e:
        return DiscoveryResult(portal=portal, success=False, error=str(e))


def parse_discovery_output(output: str, portal: IscsiPortal) -> List[IscsiTarget]:
    """Parse iscsiadm discovery output.
    
    Parses output like:
        192.168.1.100:3260,1 iqn.2020-01.com.example:storage
        192.168.1.100:3260,1 iqn.2020-01.com.example:backup
    
    Args:
        output: Raw output from iscsiadm -m discovery command
        portal: Portal that was queried
        
    Returns:
        List of IscsiTarget objects
    """
    targets = []
    portal_prefix = "{}:{},".format(portal.ip, portal.port)
    
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        
        # Format: "portal,tpgt iqn"
        # Example: "192.168.1.100:3260,1 iqn.2020-01.com.example:storage"
        parts = line.split()
        if len(parts) < 2:
            continue
        
        # Only include targets from the queried portal
        if not line.startswith(portal_prefix):
            continue
        
        iqn = parts[-1]
        target = IscsiTarget(iqn=iqn, portal=portal)
        targets.append(target)
    
    return targets


def get_discovered_iqns(
    ip: str,
    port: int = 3260,
    timeout: int = DEFAULT_DISCOVERY_TIMEOUT
) -> List[str]:
    """Get list of discovered target IQNs.
    
    Convenience function that returns just the IQN strings.
    
    Args:
        ip: iSCSI portal IP address
        port: iSCSI portal port (default 3260)
        timeout: Command timeout in seconds
        
    Returns:
        List of IQN strings
        
    Raises:
        DiscoveryError: If discovery fails
        
    Example:
        >>> iqns = get_discovered_iqns('192.168.1.100')
        >>> print(iqns)
        ['iqn.2020-01.com.example:storage', 'iqn.2020-01.com.example:backup']
    """
    targets = discover_targets(ip, port, timeout)
    return [t.iqn for t in targets]


def find_target_by_iqn(
    ip: str,
    iqn: str,
    port: int = 3260,
    timeout: int = DEFAULT_DISCOVERY_TIMEOUT
) -> IscsiTarget:
    """Find a specific target by IQN on a portal.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN to find
        port: iSCSI portal port (default 3260)
        timeout: Command timeout in seconds
        
    Returns:
        IscsiTarget if found
        
    Raises:
        DiscoveryError: If discovery fails
        TargetNotFoundError: If target with specified IQN is not found
        
    Example:
        >>> target = find_target_by_iqn('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> print(target.iqn)
        iqn.2020-01.com.example:storage
    """
    portal_str = "{}:{}".format(ip, port)
    targets = discover_targets(ip, port, timeout)
    
    for target in targets:
        if target.iqn == iqn:
            return target
    
    raise TargetNotFoundError(
        portal=portal_str,
        target=iqn,
        message="Target '{}' not found on portal {}".format(iqn, portal_str)
    )
