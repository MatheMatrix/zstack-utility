"""Multipath configuration management.

This module provides functions for managing multipath.conf:

- parse_config(): Parse multipath.conf file
- write_config(): Write multipath.conf file
- update_config(): Update multipath.conf with defaults
- add_blacklist(): Add blacklist entries
"""

import logging
import os
from typing import List, Dict, Any, Optional, Iterator

from .models import DeviceConfig, DEFAULT_DEVICE_CONFIG
from .exceptions import MultipathConfigError


logger = logging.getLogger(__name__)

# Default paths
MULTIPATH_CONF_PATH = "/etc/multipath.conf"

# Feature to remove from config
FEATURE_TO_REMOVE = "queue_if_no_path"


def parse_config(conf_lines: Iterator[str]) -> List[Dict[str, Any]]:
    """Parse multipath.conf content.
    
    Recursively parses the configuration file into a list of dicts.
    
    Args:
        conf_lines: Iterator of configuration lines
        
    Returns:
        List of configuration sections as dicts
        
    Example:
        >>> with open('/etc/multipath.conf') as f:
        ...     config = parse_config(f)
    """
    config = []  # type: List[Dict[str, Any]]
    
    for line in conf_lines:
        line = line.rstrip().strip()
        
        # Skip comments
        if line.startswith('#'):
            continue
        
        # Section start
        if line.endswith('{'):
            section_name = line.replace(' ', '').split("{")[0]
            config.append({section_name: parse_config(conf_lines)})
        else:
            # Section end
            if line.endswith('}'):
                break
            else:
                # Key-value pair
                parts = line.split()
                if len(parts) > 1:
                    key = parts[0]
                    value = " ".join(parts[1:]).strip('"')
                    config.append({key: value})
    
    return config


def _sort_config(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort configuration sections for consistent output.
    
    Args:
        sections: List of configuration sections
        
    Returns:
        Sorted list of sections
    """
    if not sections:
        return []
    
    result = []  # type: List[Dict[str, Any]]
    
    # Sort by section/key name
    sorted_sections = sorted(sections, key=lambda s: list(s.keys())[0])
    
    for section in sorted_sections:
        section_name = list(section.keys())[0]
        section_value = section[section_name]
        
        if isinstance(section_value, list):
            result.append({section_name: _sort_config(section_value)})
        else:
            result.append({section_name: section_value})
    
    return result


def _config_to_string(config: List[Dict[str, Any]]) -> str:
    """Convert configuration to string format.
    
    Args:
        config: Parsed configuration
        
    Returns:
        Configuration as string
    """
    lines = []
    
    for section in config:
        section_name = list(section.keys())[0]
        section_value = section[section_name]
        
        lines.append("{} {{".format(section_name))
        
        for child in _sort_config(section_value) if isinstance(section_value, list) else []:
            child_name = list(child.keys())[0]
            child_value = child[child_name]
            
            # Child is attribute
            if isinstance(child_value, str):
                lines.append('\t{} "{}"'.format(child_name.strip('"'), child_value.strip('"')))
                continue
            
            # Child is subsection
            lines.append('\t{} {{'.format(child_name))
            for attr in child_value:
                attr_name = list(attr.keys())[0]
                attr_value = attr[attr_name]
                lines.append('\t\t{} "{}"'.format(attr_name.strip('"'), attr_value.strip('"')))
            lines.append("\t}")
        
        lines.append("}")
    
    return "\n".join(lines) + "\n"


def read_config(path: str = MULTIPATH_CONF_PATH) -> List[Dict[str, Any]]:
    """Read and parse multipath.conf file.
    
    Args:
        path: Path to multipath.conf
        
    Returns:
        Parsed configuration
        
    Raises:
        MultipathConfigError: If file cannot be read
    """
    if not os.path.exists(path):
        return []
    
    try:
        with open(path, 'r') as f:
            return parse_config(iter(f))
    except Exception as e:
        raise MultipathConfigError(path, "Failed to read config: {}".format(e))


def write_config(
    config: List[Dict[str, Any]],
    path: str = MULTIPATH_CONF_PATH
) -> None:
    """Write configuration to multipath.conf.
    
    Args:
        config: Configuration to write
        path: Path to multipath.conf
        
    Raises:
        MultipathConfigError: If file cannot be written
    """
    try:
        content = _config_to_string(config)
        with open(path, 'w') as f:
            f.write(content)
        logger.info("Wrote multipath configuration to %s", path)
    except Exception as e:
        raise MultipathConfigError(path, "Failed to write config: {}".format(e))


def update_config(
    path: str = MULTIPATH_CONF_PATH,
    blacklist: Optional[List[Dict[str, Any]]] = None,
    ensure_default_device: bool = True
) -> bool:
    """Update multipath.conf with ZStack defaults.
    
    This function:
    1. Ensures devices section has default device config
    2. Removes queue_if_no_path feature
    3. Replaces '*' with '.*' in vendor/product patterns
    4. Optionally updates blacklist
    
    Args:
        path: Path to multipath.conf
        blacklist: New blacklist configuration (None to keep existing)
        ensure_default_device: Whether to ensure default device exists
        
    Returns:
        True if configuration was modified
        
    Raises:
        MultipathConfigError: If configuration update fails
    """
    if not os.path.exists(path):
        logger.warning("multipath.conf not found at %s", path)
        return False
    
    modified = False
    
    try:
        with open(path, 'r+') as fd:
            config = parse_config(iter(fd))
            
            has_devices_section = False
            has_default_device = False
            blacklist_changed = False
            
            # Default device config as list of dicts
            default_device = {
                'device': [
                    {'features': '0'},
                    {'no_path_retry': 'fail'},
                    {'product': '.*'},
                    {'vendor': '.*'}
                ]
            }
            
            for section in config:
                # Check blacklist
                if 'blacklist' in section and blacklist is not None:
                    current = _sort_config(section['blacklist'])
                    new = _sort_config(blacklist)
                    blacklist_changed = current != new
                
                # Process devices section
                if 'devices' in section:
                    has_devices_section = True
                    
                    for subsection in section['devices']:
                        if 'device' not in subsection:
                            continue
                        
                        device_attrs = subsection['device']
                        
                        for attribute in device_attrs[:]:
                            attr_name = list(attribute.keys())[0]
                            attr_value = attribute[attr_name]
                            
                            # Replace '*' with '.*'
                            if attr_value.strip().strip('"') == '*':
                                attribute[attr_name] = '.*'
                                modified = True
                            
                            # Remove queue_if_no_path feature
                            if attr_name == 'features' and FEATURE_TO_REMOVE in attr_value:
                                device_attrs.remove(attribute)
                                modified = True
                        
                        # Check if this is the default device
                        sorted_current = sorted(device_attrs, key=lambda x: list(x.keys())[0])
                        sorted_default = sorted(default_device['device'], key=lambda x: list(x.keys())[0])
                        if sorted_current == sorted_default:
                            has_default_device = True
                    
                    # Add default device if missing
                    if ensure_default_device and not has_default_device:
                        section['devices'].append(default_device)
                        modified = True
            
            # Update blacklist if changed
            if blacklist is not None and blacklist_changed:
                config = [cfg for cfg in config if 'blacklist' not in cfg]
                config.append({'blacklist': blacklist})
                modified = True
            
            # Add devices section if missing
            if not has_devices_section and ensure_default_device:
                config.append({'devices': [default_device]})
                modified = True
            
            # Write back if modified
            if modified:
                fd.seek(0)
                fd.truncate()
                fd.write(_config_to_string(config))
                logger.info("Updated multipath configuration at %s", path)
    
    except Exception as e:
        raise MultipathConfigError(path, "Failed to update config: {}".format(e))
    
    return modified


def get_blacklist(path: str = MULTIPATH_CONF_PATH) -> List[Dict[str, Any]]:
    """Get current blacklist configuration.
    
    Args:
        path: Path to multipath.conf
        
    Returns:
        Blacklist configuration or empty list
    """
    config = read_config(path)
    
    for section in config:
        if 'blacklist' in section:
            return section['blacklist']
    
    return []


def add_blacklist_wwid(
    wwid: str,
    path: str = MULTIPATH_CONF_PATH
) -> bool:
    """Add a WWID to the blacklist.
    
    Args:
        wwid: WWID to blacklist
        path: Path to multipath.conf
        
    Returns:
        True if configuration was modified
    """
    config = read_config(path)
    modified = False
    
    # Find or create blacklist section
    blacklist_section = None
    for section in config:
        if 'blacklist' in section:
            blacklist_section = section
            break
    
    if blacklist_section is None:
        blacklist_section = {'blacklist': []}
        config.append(blacklist_section)
        modified = True
    
    # Check if WWID already exists
    for entry in blacklist_section['blacklist']:
        if 'wwid' in entry and entry['wwid'] == wwid:
            return False  # Already blacklisted
    
    # Add WWID
    blacklist_section['blacklist'].append({'wwid': wwid})
    modified = True
    
    if modified:
        write_config(config, path)
    
    return modified
