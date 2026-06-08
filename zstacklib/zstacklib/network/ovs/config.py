# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch configuration paths and constants.
"""

# OVS runtime paths
OVS_RUN_PATH = '/var/run/openvswitch/'
LOG_PATH = '/var/log/zstack/openvswitch/'
SOCK_PATH = '/var/run/zstack/'
CONF_PATH = '/usr/local/etc/zstack-ovs/'

# OVS database and daemon paths
CONF_DB = '/usr/local/etc/zstack-ovs/conf.db'
DB_SOCK = '/var/run/openvswitch/db.sock'
DB_PID_PATH = '/var/run/openvswitch/ovsdb-server.pid'
SWITCH_PID_PATH = '/var/run/openvswitch/ovs-vswitchd.pid'
DB_LOG_PATH = '/var/log/zstack/openvswitch/ovsdb-server.log'
SWITCH_LOG_PATH = '/var/log/zstack/openvswitch/ovs-vswitchd.log'
DB_CTL_FILE_PATH = '/var/run/openvswitch/ovsdb-server.zs.ctl'
SWITCH_CTL_FILE_PATH = '/var/run/openvswitch/ovs-vswitchd.zs.ctl'

# OVS control command
CTL_BIN = f'ovs-vsctl --db=unix:{DB_SOCK} '

# Supported vNIC types for DPDK
OVS_DPDK_SUPPORT_VNIC = ['vDPA', 'dpdkvhostuserclient']
OVS_DPDK_SUPPORT_BOND_TYPE = ['dpdkBond', 'ovsBond']

# Bond configuration file
BOND_CONFIG_FILE = 'dpdk-bond.yaml'
SMART_NIC_CONFIG_FILE = 'smart-nics.yaml'

# Hugepages configuration
DEFAULT_HUGEPAGE_SIZE = 2048  # 2MB hugepages
DEFAULT_NR_HUGEPAGES = 1024
HUGEPAGES_PATHS = {
    2048: 'hugepages/hugepages-2048kB/',
    1048576: 'hugepages/hugepages-1048576kB/',  # 1GB hugepages
}

# Logrotate configuration
LOGROTATE_FILE = '/etc/logrotate.d/openvswitch-zstack'
LOGROTATE_CONF = '''
/var/log/zstack/openvswitch/*.log {
    daily
    compress
    sharedscripts
    missingok
    postrotate
        # Tell Open vSwitch daemons to reopen their log files
        if [ -d /var/run/openvswitch ]; then
            for ctl in /var/run/openvswitch/*.ctl; do
                ovs-appctl -t "$ctl" vlog/reopen 2>/dev/null || :
            done
        fi
    endscript
}
'''
