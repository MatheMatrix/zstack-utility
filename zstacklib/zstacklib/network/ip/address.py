# Copyright (c) ZStack.io, Inc.

"""
IP address classes for IPv4 and IPv6.

Provides IpAddress and Ipv6Address classes for parsing, comparing,
and manipulating IP addresses.
"""

import re
import socket
from typing import List, Optional

from .exceptions import InvalidIpAddress


class IpAddress(object):
    """
    IPv4 address class with comparison and CIDR support.
    
    Provides functionality to:
    - Parse and validate IPv4 addresses
    - Compare addresses (>, <, ==, etc.)
    - Convert to 32-bit integer
    - Calculate CIDR notation with netmask
    
    Example:
        >>> ip = IpAddress('192.168.1.100')
        >>> ip2 = IpAddress('192.168.1.50')
        >>> ip > ip2
        True
        >>> ip.toInt32()
        3232235876
    """
    
    def __init__(self, ip):
        # type: (str) -> None
        """
        Initialize IpAddress from dotted-decimal string.
        
        Args:
            ip: IPv4 address string in dotted-decimal notation (e.g., '192.168.1.1')
        
        Raises:
            InvalidIpAddress: If the IP address format is invalid
        """
        self.ip_list = ip.split('.', 3)
        self.ips = []  # type: List[int]
        
        if len(self.ip_list) != 4:
            raise InvalidIpAddress(ip, "IPv4 address must have 4 octets")
        
        for item in self.ip_list:
            if not item.isdigit():
                raise InvalidIpAddress(ip, "'%s' is not a digit" % item)
            value = int(item)
            if value > 255 or value < 0:
                raise InvalidIpAddress(ip, "'%s' must be between 0 and 255" % item)
            self.ips.append(value)
    
    def _compare(self, other):
        # type: (IpAddress) -> int
        """Compare two IP addresses. Returns -1, 0, or 1."""
        for i in range(4):
            if self.ips[i] > other.ips[i]:
                return 1
            elif self.ips[i] < other.ips[i]:
                return -1
        return 0
    
    def __gt__(self, other):
        # type: (IpAddress) -> bool
        return self._compare(other) > 0
    
    def __lt__(self, other):
        # type: (IpAddress) -> bool
        return self._compare(other) < 0
    
    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, IpAddress):
            return False
        return self._compare(other) == 0
    
    def __le__(self, other):
        # type: (IpAddress) -> bool
        return self._compare(other) <= 0
    
    def __ge__(self, other):
        # type: (IpAddress) -> bool
        return self._compare(other) >= 0
    
    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)
    
    def __str__(self):
        # type: () -> str
        return '.'.join(self.ip_list)
    
    def __repr__(self):
        # type: () -> str
        return self.__str__()
    
    def __hash__(self):
        # type: () -> int
        return hash(self.toInt32())
    
    def toInt32(self):
        # type: () -> int
        """
        Convert IP address to 32-bit integer.
        
        Returns:
            32-bit integer representation of the IP address
        """
        ip32 = self.ips[0]
        for item in self.ips[1:]:
            ip32 = ip32 << 8
            ip32 += item
        return ip32
    
    def toCidr(self, netmask):
        # type: (str) -> str
        """
        Convert IP address with netmask to CIDR notation.
        
        Args:
            netmask: Netmask in dotted-decimal notation (e.g., '255.255.255.0')
        
        Returns:
            CIDR notation string (e.g., '192.168.1.0/24')
        """
        ip32 = self.toInt32()
        mask32 = IpAddress(netmask).toInt32()
        cidr32 = ip32 & mask32
        cidr = [
            cidr32 >> 24,
            (cidr32 & 0x00FF0000) >> 16,
            (cidr32 & 0x0000FF00) >> 8,
            cidr32 & 0x000000FF
        ]
        
        maskbits = netmask_to_cidr(netmask)
        
        return '%s.%s.%s.%s/%s' % (cidr[0], cidr[1], cidr[2], cidr[3], maskbits)


class Ipv6Address(object):
    """
    IPv6 address class for parsing and manipulation.
    
    Supports compressed IPv6 notation (with ::) and provides
    utilities for solicited-node multicast addresses and prefixes.
    
    Example:
        >>> ip = Ipv6Address('fe80::1')
        >>> ip.get_prefix(64)
        'fe80::/64'
    """
    
    def __init__(self, ip):
        # type: (str) -> None
        """
        Initialize Ipv6Address from string.
        
        Args:
            ip: IPv6 address string (can be compressed with ::)
        """
        # IPv6 address includes 8 groups
        self.ips = ["", "", "", "", "", "", "", ""]  # type: List[str]
        self.prefix = ["", "", "", "", "", "", "", ""]  # type: List[str]
        
        temp = ip.split('::')
        pos = 0
        
        for item in temp[0].split(":"):
            if pos < 8:
                self.ips[pos] = item
                self.prefix[pos] = item
                pos += 1
        
        if len(temp) == 2:
            addr = temp[1].split(":")
            addr_len = len(addr)
            pos = 8 - addr_len
            for item in addr:
                if pos < 8:
                    self.ips[pos] = item
                    pos += 1
    
    def get_solicited_node_multicast_address(self):
        # type: () -> str
        """
        Get the solicited-node multicast address for this IPv6 address.
        
        The solicited-node multicast address is derived from the last 24 bits
        of the IPv6 address and is used for Neighbor Discovery Protocol.
        
        Returns:
            Solicited-node multicast address string
        """
        ip = "ff02::1:ff"
        if len(self.ips[6]) >= 2:
            ip += self.ips[6][-2:]
        else:
            ip += self.ips[6]
        return ip + ":" + self.ips[7]
    
    def get_prefix(self, prefixlen):
        # type: (int) -> str
        """
        Get the network prefix with the specified length.
        
        Args:
            prefixlen: Prefix length in bits
        
        Returns:
            Network prefix in CIDR notation (e.g., 'fe80::/64')
        """
        temp = []
        for item in self.prefix:
            if item != "":
                temp.append(item)
        
        return ":".join(temp) + "::/" + str(prefixlen)
    
    def __str__(self):
        # type: () -> str
        return ":".join(self.ips)
    
    def __repr__(self):
        # type: () -> str
        return self.__str__()


def netmask_to_cidr(netmask):
    # type: (str) -> int
    """
    Convert netmask to CIDR prefix length.
    
    Args:
        netmask: Netmask in dotted-decimal notation (e.g., '255.255.255.0')
    
    Returns:
        CIDR prefix length (e.g., 24 for '255.255.255.0')
    """
    try:
        # Pack the netmask as binary
        packed = socket.inet_aton(netmask)
        # Count the number of 1 bits
        binary = ''.join(format(b, '08b') for b in packed)
        return binary.count('1')
    except socket.error:
        raise InvalidIpAddress(netmask, "Invalid netmask format")


def get_link_local_address(mac):
    # type: (str) -> str
    """
    Get IPv6 link-local address from a MAC address.
    
    Converts a 48-bit MAC address to an IPv6 link-local address
    following RFC 4291 Section 2.5.1.
    
    Process:
    1. Invert the universal/local bit of the MAC address
    2. Insert 'fffe' in the middle of the MAC address
    3. Prepend with fe80::/64 prefix
    
    Example:
        >>> get_link_local_address('00:01:02:aa:bb:cc')
        'fe80::201:2ff:feaa:bbcc'
    
    Args:
        mac: MAC address in colon-separated format (e.g., '00:01:02:aa:bb:cc')
    
    Returns:
        IPv6 link-local address string
    """
    macs = mac.strip("\n").split(":")
    
    # Step 1: Invert the "u" bit (bit 6) of the first octet
    macs[0] = hex(int(macs[0], 16) ^ 2)[2:]
    
    # Step 2: Insert "fffe" in the middle
    part1 = macs[0] + macs[1] + ":"
    part2 = macs[2] + "ff" + ":"
    part3 = "fe" + macs[3] + ":"
    part4 = macs[4] + macs[5]
    
    # Step 3: Strip leading zeros and construct the address
    return "fe80::" + part1.lstrip("0") + part2.lstrip("0") + part3.lstrip("0") + part4.lstrip("0")


def remove_zero_from_mac_address(mac):
    # type: (str) -> str
    """
    Remove leading zeros from MAC address octets.
    
    iptables represents MAC addresses without leading zeros,
    e.g., '00:01:aa:b0:02:04' becomes '0:1:aa:b0:2:4'
    
    Args:
        mac: MAC address in colon-separated format
    
    Returns:
        MAC address with leading zeros removed
    """
    new_mac = mac.replace(":0", ":")
    if new_mac[0] == '0':
        new_mac = new_mac[1:]
    return new_mac


# Backward compatibility alias
removeZeroFromMacAddress = remove_zero_from_mac_address
