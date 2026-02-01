# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch bond configuration utilities.
"""

from __future__ import annotations

import os
import yaml

from .config import CONF_PATH, BOND_CONFIG_FILE
from .models import Bond


def get_bond_from_file(bond_name: str) -> Bond | None:
    """Get bond configuration from dpdk-bond.yaml file.

    Args:
        bond_name: Name of the bond to find.

    Returns:
        Bond object if found, None otherwise.
    """
    try:
        bond_file = os.path.join(CONF_PATH, BOND_CONFIG_FILE)

        if not os.path.exists(bond_file):
            return None

        with open(bond_file, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        for d in data:
            if d['bond']['name'] == bond_name:
                dpdk_bond = Bond(name=d['bond']['name'])
                dpdk_bond.mode = d['bond']['mode']
                dpdk_bond.id = d['bond']['id']

                if 'lacp' in d['bond']:
                    dpdk_bond.lacp = d['bond']['lacp']
                if 'options' in d['bond']:
                    dpdk_bond.options = d['bond']['options']
                if 'policy' in d['bond']:
                    dpdk_bond.policy = d['bond']['policy']

                for slave in d['bond']['slaves']:
                    dpdk_bond.slaves.append(str(slave))

                return dpdk_bond

        return None
    except Exception:
        return None


def get_all_bonds_from_file() -> list[Bond]:
    """Get all bond configurations from dpdk-bond.yaml file.

    Returns:
        List of Bond objects.
    """
    try:
        bond_file = os.path.join(CONF_PATH, BOND_CONFIG_FILE)
        dpdk_bonds = []

        if not os.path.exists(bond_file):
            return dpdk_bonds

        with open(bond_file, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            return dpdk_bonds

        for d in data:
            dpdk_bond = Bond(name=d['bond']['name'])
            dpdk_bond.mode = d['bond']['mode']
            dpdk_bond.id = d['bond']['id']

            if 'lacp' in d['bond']:
                dpdk_bond.lacp = d['bond']['lacp']
            if 'options' in d['bond']:
                dpdk_bond.options = d['bond']['options']
            if 'policy' in d['bond']:
                dpdk_bond.policy = d['bond']['policy']

            for slave in d['bond']['slaves']:
                dpdk_bond.slaves.append(str(slave))

            dpdk_bonds.append(dpdk_bond)

        return dpdk_bonds
    except Exception:
        return []
