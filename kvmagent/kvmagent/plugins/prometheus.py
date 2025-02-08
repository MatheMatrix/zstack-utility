import os.path
import pyudev  # installed by ansible
import threading
import time
from collections import defaultdict

import typing
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
import psutil

from kvmagent import kvmagent
from zstacklib.utils import http, debug
from zstacklib.utils import jsonobject
from zstacklib.utils import linux
from zstacklib.utils import lock
from zstacklib.utils import lvm
from zstacklib.utils import shell
from zstacklib.utils import misc
from zstacklib.utils import thread
from zstacklib.utils import gpu
from zstacklib.utils.bash import *
from zstacklib.utils.ip import get_host_physicl_nics
from zstacklib.utils.ip import get_nic_supported_max_speed
from zstacklib.utils.linux import is_virtual_machine

logger = log.get_logger(__name__)
collector_dict = {}  # type: Dict[str, threading.Thread]
collectd_dir = "/var/lib/zstack/collectd/"
latest_collect_result = {}
collectResultLock = threading.RLock()
asyncDataCollectorLock = threading.RLock()
QEMU_CMD = os.path.basename(kvmagent.get_qemu_path())
ALARM_CONFIG = None
PAGE_SIZE = None
disk_list_record = None
hba_port_state_list_record_map = {}
nvme_serial_numbers_record = None
is_hygon = True if 'hygon' in linux.get_cpu_model()[1].lower() else False
dump_stack_and_objects = True
kvmagent_physical_memory_usage_alarm_time = None

gpu_devices = {
    'NVIDIA': set(),
    'AMD': set(),
    'HY': set(),
    'HUAWEI': set(),
    'TIANSHU': set()
}

hw_status_abnormal_list_record = {
    'cpu': set(),
    'memory': set(),
    'fan': set(),
    'powerSupply': set(),
    'gpu': set(),
    'disk': set(),
    'raid': set()
}

# collect domain max memory
domain_max_memory = {}


def read_number(fname):
    res = linux.read_file(fname)
    return 0 if not res else int(res)


class PhysicalStatusAlarm:
    def __init__(self, host=None, alarm_type=None, **kwargs):
        self.host = host
        self.type = alarm_type
        self.additionalProperties = kwargs

    def to_dict(self):
        result = {
            "host": self.host,
            "type": self.type,
            "additionalProperties": self.additionalProperties
        }
        return result


def send_alarm_to_mn(alarm_type, unique_id, **kwargs):
    if ALARM_CONFIG is None:
        return

    url = ALARM_CONFIG.get(kvmagent.SEND_COMMAND_URL)
    if not url:
        logger.warn("Cannot find SEND_COMMAND_URL, unable to transmit {alarm_type} alarm info to management node"
                    .format(alarm_type=alarm_type))
        return

    global hw_status_abnormal_list_record
    record_list = hw_status_abnormal_list_record.get(alarm_type, set())
    if unique_id not in record_list:
        alarm = PhysicalStatusAlarm(
            host=ALARM_CONFIG.get(kvmagent.HOST_UUID),
            alarm_type=alarm_type,
            **kwargs
        )
        http.json_dump_post(url, alarm.to_dict(), {'commandpath': '/host/physical/hardware/status/alarm'})
        record_list.add(unique_id)
        hw_status_abnormal_list_record[alarm_type] = record_list


def remove_abnormal_status(alarm_type, unique_id):
    global hw_status_abnormal_list_record
    record_list = hw_status_abnormal_list_record.get(alarm_type)
    if record_list is not None:
        record_list.discard(unique_id)
        hw_status_abnormal_list_record[alarm_type] = record_list


def is_abnormal_status(alarm_type, unique_id):
    global hw_status_abnormal_list_record
    record_list = hw_status_abnormal_list_record.get(alarm_type, set())
    return unique_id in record_list


def is_cpu_status_abnormal(unique_id):
    return is_abnormal_status('cpu', unique_id)


def remove_cpu_status_abnormal(unique_id):
    remove_abnormal_status('cpu', unique_id)


def remove_physical_volume_state_abnormal(unique_id):
    remove_abnormal_status('physical_volume', unique_id)


def is_memory_status_abnormal(unique_id):
    return is_abnormal_status('memory', unique_id)


def remove_memory_status_abnormal(unique_id):
    remove_abnormal_status('memory', unique_id)


def is_fan_status_abnormal(unique_id):
    return is_abnormal_status('fan', unique_id)


def remove_fan_status_abnormal(unique_id):
    remove_abnormal_status('fan', unique_id)


def is_power_supply_status_abnormal(unique_id):
    return is_abnormal_status('powerSupply', unique_id)


def remove_power_supply_status_abnormal(unique_id):
    remove_abnormal_status('powerSupply', unique_id)


def is_gpu_status_abnormal(unique_id):
    return is_abnormal_status('gpu', unique_id)


def remove_gpu_status_abnormal(unique_id):
    remove_abnormal_status('gpu', unique_id)


def is_disk_status_abnormal(unique_id):
    return is_abnormal_status('disk', unique_id)


def remove_disk_status_abnormal(unique_id):
    remove_abnormal_status('disk', unique_id)


def is_raid_status_abnormal(unique_id):
    return is_abnormal_status('raid', unique_id)


def remove_raid_status_abnormal(unique_id):
    remove_abnormal_status('raid', unique_id)


@thread.AsyncThread
def send_cpu_status_alarm_to_mn(cpu_id, status):
    send_alarm_to_mn('cpu', cpu_id, cpuName=cpu_id, status=status)


@thread.AsyncThread
def send_physical_gpu_status_alarm_to_mn(pcideviceAddress, status):
    send_alarm_to_mn('gpu', pcideviceAddress, pcideviceAddress=pcideviceAddress, status=status)


@thread.AsyncThread
def send_physical_memory_status_alarm_to_mn(locator, status):
    send_alarm_to_mn('memory', locator, locator=locator, status=status)


@thread.AsyncThread
def send_physical_power_supply_status_alarm_to_mn(name, status):
    send_alarm_to_mn('powerSupply', name, name=name, status=status)


@thread.AsyncThread
def send_physical_fan_status_alarm_to_mn(fan_name, status):
    send_alarm_to_mn('fan', fan_name, name=fan_name, status=status)


@thread.AsyncThread
def send_physical_disk_status_alarm_to_mn(serial_number, slot_number, enclosure_device_id, drive_state):
    send_alarm_to_mn('disk', serial_number, serial_number=serial_number, slot_number=slot_number,
                     enclosure_device_id=enclosure_device_id, drive_state=drive_state)

@thread.AsyncThread
def send_physical_volume_status_alarm_to_mn(disk_name, pv_identities, state, vg):
    send_alarm_to_mn('physical_volume', disk_name, name=disk_name, diskUuids=pv_identities, state=state, volumeGroup=vg)


@thread.AsyncThread
def send_raid_state_alarm_to_mn(target_id, state):
    send_alarm_to_mn('raid', target_id, target_id=target_id, status=state)


def send_disk_insert_or_remove_alarm_to_mn(alarm_type, serial_number, slot):
    if ALARM_CONFIG is None:
        return

    url = ALARM_CONFIG.get(kvmagent.SEND_COMMAND_URL)
    if not url:
        logger.warn(
            "Cannot find SEND_COMMAND_URL, unable to transmit {alarm_type} alarm info to management node".format(
                alarm_type=alarm_type))
        return

    alarm = PhysicalStatusAlarm(
        host=ALARM_CONFIG.get(kvmagent.HOST_UUID),
        serial_number=serial_number,
        enclosure_device_id=slot.split("-")[0],
        slot_number=slot.split("-")[1]
    )
    http.json_dump_post(url, alarm,
                        {'commandpath': '/host/physical/disk/{alarm_type}/alarm'.format(alarm_type=alarm_type)})

@thread.AsyncThread
def send_hba_port_state_abnormal_alarm_to_mn(name, port_name, port_state):
    class HBAPortStateAbnormalAlarm(object):
        def __init__(self):
            self.portName = None
            self.portState = None
            self.host = None
            self.name = None

    if ALARM_CONFIG is None:
        return

    url = ALARM_CONFIG.get(kvmagent.SEND_COMMAND_URL)
    if not url:
        logger.warn(
            "cannot find SEND_COMMAND_URL, unable to transmit hba port state abnormal alarm info to management node")
        return

    if port_name in hba_port_state_list_record_map.keys():
        hba_port_state_abnormal_alarm = HBAPortStateAbnormalAlarm()
        hba_port_state_abnormal_alarm.host = ALARM_CONFIG.get(kvmagent.HOST_UUID)
        hba_port_state_abnormal_alarm.portName = port_name
        hba_port_state_abnormal_alarm.portState = port_state
        hba_port_state_abnormal_alarm.name = name
        http.json_dump_post(url, hba_port_state_abnormal_alarm,
                            {'commandpath': '/storagedevice/hba/state/alarm'})


@thread.AsyncThread
def send_physical_disk_insert_alarm_to_mn(serial_number, slot):
    send_disk_insert_or_remove_alarm_to_mn('insert', serial_number, slot)


@thread.AsyncThread
def send_physical_disk_remove_alarm_to_mn(serial_number, slot):
    send_disk_insert_or_remove_alarm_to_mn('remove', serial_number, slot)


def collect_memory_locator():
    memory_locator_list = []
    r, infos = bash_ro("dmidecode -q -t memory | grep -E 'Serial Number|Locator'")
    if r != 0:
        return memory_locator_list
    locator = "unknown"
    for line in infos.splitlines():
        k = line.split(":")[0].strip()
        v = ":".join(line.split(":")[1:]).strip()
        if "Locator" == k:
            locator = v
        elif "Serial Number" == k:
            if v.lower() == "no dimm" or v.lower() == "unknown" or v == "":
                continue
            memory_locator_list.append(locator)

    return memory_locator_list


@thread.AsyncThread
def check_disk_insert_and_remove(disk_list):
    global disk_list_record
    if disk_list_record is None:
        disk_list_record = disk_list
        return

    if cmp(disk_list_record, disk_list) == 0:
        return

    # check disk insert
    for sn in disk_list.keys():
        if sn not in disk_list_record.keys():
            send_physical_disk_insert_alarm_to_mn(sn, disk_list[sn])

    # check disk remove
    for sn in disk_list_record.keys():
        if sn not in disk_list.keys():
            send_physical_disk_remove_alarm_to_mn(sn, disk_list_record[sn])

    disk_list_record = disk_list


# use lazy loading to avoid re-registering global configuration when other modules are initialized
host_network_interface_service_type_map = None


@lock.lock('serviceTypeMapLock')
def get_service_type_map():
    global host_network_interface_service_type_map
    if host_network_interface_service_type_map is None:
        host_network_interface_service_type_map = {}
    return host_network_interface_service_type_map


@lock.lock('serviceTypeMapLock')
def register_service_type(dev_name, service_type):
    host_network_interface_service_type_map = get_service_type_map()
    host_network_interface_service_type_map[dev_name] = service_type


def collect_host_network_statistics():
    all_eths = os.listdir("/sys/class/net/")
    virtual_eths = os.listdir("/sys/devices/virtual/net/")

    interfaces = []
    for eth in all_eths:
        eth = eth.strip(' \t\n\r')
        if eth in virtual_eths:
            continue
        elif eth == 'bonding_masters':
            continue
        elif not eth:
            continue
        else:
            interfaces.append(eth)

    all_in_bytes = 0
    all_in_packets = 0
    all_in_errors = 0
    all_out_bytes = 0
    all_out_packets = 0
    all_out_errors = 0
    for intf in interfaces:
        all_in_bytes += read_number("/sys/class/net/{}/statistics/rx_bytes".format(intf))
        all_in_packets += read_number("/sys/class/net/{}/statistics/rx_packets".format(intf))
        all_in_errors += read_number("/sys/class/net/{}/statistics/rx_errors".format(intf))
        all_out_bytes += read_number("/sys/class/net/{}/statistics/tx_bytes".format(intf))
        all_out_packets += read_number("/sys/class/net/{}/statistics/tx_packets".format(intf))
        all_out_errors += read_number("/sys/class/net/{}/statistics/tx_errors".format(intf))

    host_network_interface_service_type_map = get_service_type_map()
    service_types = set()
    for types in host_network_interface_service_type_map.values():
        service_types.update(types)

    all_in_bytes_by_service_type = {service_type: 0 for service_type in service_types}
    all_in_packets_by_service_type = {service_type: 0 for service_type in service_types}
    all_in_errors_by_service_type = {service_type: 0 for service_type in service_types}
    all_out_bytes_by_service_type = {service_type: 0 for service_type in service_types}
    all_out_packets_by_service_type = {service_type: 0 for service_type in service_types}
    all_out_errors_by_service_type = {service_type: 0 for service_type in service_types}

    host_network_service_type_interface_map = defaultdict(list)
    for interface, types in host_network_interface_service_type_map.items():
        for service_type in types:
            host_network_service_type_interface_map[service_type].append(interface)

    for service_type in service_types:
        eths = sorted(host_network_service_type_interface_map.get(service_type, []))
        eths_filter_subinterfaces = []
        eths_filter_bridges = []

        # Filter out the corresponding sub interface zsn0.10 of interface like zsn0
        for eth in eths:
            if '.' in eth:
                interface_name = eth.split('.')[0]
                if interface_name in eths_filter_subinterfaces:
                    continue
            eths_filter_subinterfaces.append(eth)

        # Filter out the corresponding bridge interface br_zsn0_1987 of interface like zsn0.1987
        for eth in eths_filter_subinterfaces:
            if eth.startswith('br_'):
                eth_interface = eth[3:].replace('_', '.')
                if eth_interface in eths_filter_subinterfaces:
                    continue
            eths_filter_bridges.append(eth)

        for eth in eths_filter_bridges:
            all_in_bytes_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/rx_bytes".format(eth))
            all_in_packets_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/rx_packets".format(eth))
            all_in_errors_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/rx_errors".format(eth))
            all_out_bytes_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/tx_bytes".format(eth))
            all_out_packets_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/tx_packets".format(eth))
            all_out_errors_by_service_type[service_type] += read_number(
                "/sys/class/net/{}/statistics/tx_errors".format(eth))

    metrics = {
        'host_network_all_in_bytes': GaugeMetricFamily('host_network_all_in_bytes',
                                                       'Host all inbound traffic in bytes'),
        'host_network_all_in_packages': GaugeMetricFamily('host_network_all_in_packages',
                                                          'Host all inbound traffic in packages'),
        'host_network_all_in_errors': GaugeMetricFamily('host_network_all_in_errors',
                                                        'Host all inbound traffic errors'),
        'host_network_all_out_bytes': GaugeMetricFamily('host_network_all_out_bytes',
                                                        'Host all outbound traffic in bytes'),
        'host_network_all_out_packages': GaugeMetricFamily('host_network_all_out_packages',
                                                           'Host all outbound traffic in packages'),
        'host_network_all_out_errors': GaugeMetricFamily('host_network_all_out_errors',
                                                         'Host all outbound traffic errors'),
        'host_network_all_in_bytes_by_service_type': GaugeMetricFamily('host_network_all_in_bytes_by_service_type',
                                                                       'Host all inbound traffic in bytes by service type',
                                                                       None, ['service_type']),
        'host_network_all_in_packages_by_service_type': GaugeMetricFamily(
            'host_network_all_in_packages_by_service_type',
            'Host all inbound traffic in packages by service type',
            None, ['service_type']),
        'host_network_all_in_errors_by_service_type': GaugeMetricFamily('host_network_all_in_errors_by_service_type',
                                                                        'Host all inbound traffic errors by service type',
                                                                        None, ['service_type']),
        'host_network_all_out_bytes_by_service_type': GaugeMetricFamily('host_network_all_out_bytes_by_service_type',
                                                                        'Host all outbound traffic in bytes by service type',
                                                                        None, ['service_type']),
        'host_network_all_out_packages_by_service_type': GaugeMetricFamily(
            'host_network_all_out_packages_by_service_type',
            'Host all outbound traffic in packages by service type',
            None, ['service_type']),
        'host_network_all_out_errors_by_service_type': GaugeMetricFamily('host_network_all_out_errors_by_service_type',
                                                                         'Host all outbound traffic errors by service type',
                                                                         None, ['service_type']),
    }

    metrics['host_network_all_in_bytes'].add_metric([], float(all_in_bytes))
    metrics['host_network_all_in_packages'].add_metric([], float(all_in_packets))
    metrics['host_network_all_in_errors'].add_metric([], float(all_in_errors))
    metrics['host_network_all_out_bytes'].add_metric([], float(all_out_bytes))
    metrics['host_network_all_out_packages'].add_metric([], float(all_out_packets))
    metrics['host_network_all_out_errors'].add_metric([], float(all_out_errors))
    for service_type in service_types:
        metrics['host_network_all_in_bytes_by_service_type'].add_metric([service_type], float(
            all_in_bytes_by_service_type[service_type]))
        metrics['host_network_all_in_packages_by_service_type'].add_metric([service_type], float(
            all_in_packets_by_service_type[service_type]))
        metrics['host_network_all_in_errors_by_service_type'].add_metric([service_type], float(
            all_in_errors_by_service_type[service_type]))
        metrics['host_network_all_out_bytes_by_service_type'].add_metric([service_type], float(
            all_out_bytes_by_service_type[service_type]))
        metrics['host_network_all_out_packages_by_service_type'].add_metric([service_type], float(
            all_out_packets_by_service_type[service_type]))
        metrics['host_network_all_out_errors_by_service_type'].add_metric([service_type], float(
            all_out_errors_by_service_type[service_type]))

    return metrics.values()


collect_node_disk_capacity_last_time = None
collect_node_disk_capacity_last_result = None


def collect_host_capacity_statistics():
    default_zstack_path = '/usr/local/zstack/apache-tomcat/webapps/zstack'

    zstack_env_path = os.environ.get('ZSTACK_HOME', None)
    if zstack_env_path and zstack_env_path != default_zstack_path:
        default_zstack_path = zstack_env_path

    zstack_dir = ['/var/lib/zstack', '%s/../../../' % default_zstack_path, '/opt/zstack-dvd/',
                  '/var/log/zstack', '/var/lib/mysql', '/var/lib/libvirt', '/tmp/zstack']

    metrics = {
        'zstack_used_capacity_in_bytes': GaugeMetricFamily('zstack_used_capacity_in_bytes',
                                                           'ZStack used capacity in bytes'),
        'block_device_used_capacity_in_bytes': GaugeMetricFamily('block_device_used_capacity_in_bytes',
                                                                 'block device used capacity in bytes', None, ['disk']),
        'block_device_used_capacity_in_percent': GaugeMetricFamily('block_device_used_capacity_in_percent',
                                                                   'block device used capacity in percent', None,
                                                                   ['disk'])
    }

    global collect_node_disk_capacity_last_time
    global collect_node_disk_capacity_last_result

    if collect_node_disk_capacity_last_time is None or (time.time() - collect_node_disk_capacity_last_time) >= 60:
        collect_node_disk_capacity_last_time = time.time()
    elif (
            time.time() - collect_node_disk_capacity_last_time) < 60 and collect_node_disk_capacity_last_result is not None:
        return collect_node_disk_capacity_last_result

    zstack_used_capacity = 0
    for d in zstack_dir:
        if not os.path.exists(d):
            continue
        res = bash_o("du -bs %s" % d)  # split()[0] is far cheaper than awk
        zstack_used_capacity += int(res.split()[0])

    metrics['zstack_used_capacity_in_bytes'].add_metric([], float(zstack_used_capacity))

    r1, dfInfo = bash_ro("df | awk '{print $3,$6}' | tail -n +2")
    r2, lbkInfo = bash_ro("lsblk -e 43 -db -oname,size | tail -n +2")
    if r1 != 0 or r2 != 0:
        collect_node_disk_capacity_last_result = metrics.values()
        return collect_node_disk_capacity_last_result

    df_map = {}
    for df in dfInfo.splitlines():
        df_size = long(df.split()[0].strip()) * 1024
        df_name = df.split()[-1].strip()
        df_map[df_name] = df_size

    for lbk in lbkInfo.splitlines():
        lbk_name = lbk.split()[0].strip()
        lbk_size = long(lbk.split()[-1].strip())

        lbk_used_size = 0L
        ds = bash_o("lsblk -lb /dev/%s -omountpoint |awk '{if(length($1)>0) print $1}' | tail -n +2" % lbk_name)
        for d in ds.splitlines():
            if df_map.get(d.strip(), None) != None:
                lbk_used_size += df_map.get(d.strip())

        metrics['block_device_used_capacity_in_bytes'].add_metric([lbk_name], float(lbk_used_size))
        metrics['block_device_used_capacity_in_percent'].add_metric([lbk_name], float(lbk_used_size * 100) / lbk_size)

    collect_node_disk_capacity_last_result = metrics.values()
    return collect_node_disk_capacity_last_result


def collect_lvm_capacity_statistics():
    metrics = {
        'vg_size': GaugeMetricFamily('vg_size',
                                     'volume group size', None, ['vg_name']),
        'vg_avail': GaugeMetricFamily('vg_avail',
                                      'volume group and thin pool free size', None, ['vg_name']),
    }

    if linux.file_has_config("/etc/multipath/wwids"):
        linux.set_fail_if_no_path()

    vg_sizes = lvm.get_all_vg_size()
    for name, tpl in vg_sizes.items():
        metrics['vg_size'].add_metric([name], float(tpl[0]))
        metrics['vg_avail'].add_metric([name], float(tpl[1]))

    return metrics.values()


def convert_raid_state_to_int(state):
    """

    :type state: str
    """
    state = state.lower().strip()
    if "optimal" in state or "optl" == state:
        return 0
    # dgrd and pdgd
    elif "degraded" in state or "dgrd" == state or "pdgd" == state or "interim recovery" in state:
        return 5
    elif "ready for recovery" in state or "rebuilding" in state or "rec" == state:
        return 10
    else:
        return 100


def convert_disk_state_to_int(state):
    """

    :type state: str
    """
    state = state.lower().strip()
    if "online" in state or "jbod" in state or "ready" in state or "optimal" in state or "hot-spare" in state \
            or "hot spare" in state or "raw" in state or "onln" == state or "ghs" == state or "dhs" == state \
            or "ugood" == state or "cpybck" == state:
        return 0
    elif "rebuild" in state or "rbld" == state:
        return 5
    elif "failed" in state or "offline" in state or "offln" == state:
        return 10
    elif "missing" in state:
        return 20
    else:
        return 100


def collect_raid_state():
    metrics = {
        'raid_state': GaugeMetricFamily('raid_state',
                                        'raid state', None, ['target_id']),
        'physical_disk_state': GaugeMetricFamily('physical_disk_state',
                                                 'physical disk state', None,
                                                 ['slot_number', 'disk_group']),
    }

    r, o = bash_ro("sas3ircu list | grep -A 8 'Index' | awk '{print $1}'")
    if r == 0 and o.strip() != "":
        return collect_sas_raid_state(metrics, o)

    r, o = bash_ro("/opt/MegaRAID/storcli/storcli64 /call/vall show all J")
    if r == 0 and jsonobject.loads(o)['Controllers'][0]['Command Status']['Status'] == "Success":
        return collect_mega_raid_state(metrics, o)

    r, o = bash_ro("arcconf list | grep -A 8 'Controller ID' | awk '{print $2}'")
    if r == 0 and o.strip() != "":
        return collect_arcconf_raid_state(metrics, o)

    return metrics.values()


def handle_raid_state(target_id, state_int, origin_state):
    if state_int != 0:
        send_raid_state_alarm_to_mn(target_id, origin_state)
        return
    remove_raid_status_abnormal(target_id)


def collect_arcconf_raid_state(metrics, infos):
    disk_list = {}
    for line in infos.splitlines():
        if line.strip() == "":
            continue
        adapter = line.split(":")[0].strip()
        if not adapter.isdigit():
            continue

        r, device_info = bash_ro("arcconf getconfig %s AL" % adapter)
        if r != 0 or device_info.strip() == "":
            continue

        # Contain at least raid controller into and a hardDisk info
        device_arr = device_info.split("Device #")
        if len(device_arr) < 3:
            continue

        target_id = "unknown"
        for l in device_arr[0].splitlines():
            if l.strip() == "":
                continue
            if "Logical Device number" in l:
                target_id = l.strip().split(" ")[-1]
            elif "Status of Logical Device" in l and target_id != "unknown":
                state = l.strip().split(":")[-1].strip()
                state_int = convert_raid_state_to_int(state)
                metrics['raid_state'].add_metric([target_id], state_int)
                handle_raid_state(target_id, state_int, state)

        for infos in device_arr[1:]:
            drive_state = serial_number = slot_number = enclosure_device_id = "unknown"
            is_hard_drive = False
            for l in infos.splitlines():
                if l.strip() == "":
                    continue
                if l.strip().lower() == "device is a hard drive":
                    is_hard_drive = True
                    continue
                k = l.split(":")[0].strip().lower()
                v = ":".join(l.split(":")[1:]).strip()
                if "state" == k:
                    drive_state = v.split(" ")[0].strip()
                elif "serial number" in k:
                    serial_number = v
                elif "reported location" in k and "Enclosure" in v and "Slot" in v:
                    enclosure_device_id = v.split(",")[0].split(" ")[1].strip()
                    slot_number = v.split("Slot ")[1].split("(")[0].strip()

            if not is_hard_drive or serial_number.lower() == "unknown" or enclosure_device_id == "unknown" or slot_number == "unknown" or drive_state == "unknown":
                continue
            disk_status = convert_disk_state_to_int(drive_state)
            metrics['physical_disk_state'].add_metric([slot_number, enclosure_device_id], disk_status)
            disk_list[serial_number] = "%s-%s" % (enclosure_device_id, slot_number)
            if is_disk_status_abnormal(serial_number):
                remove_disk_status_abnormal(serial_number)
            elif disk_status != 0:
                send_physical_disk_status_alarm_to_mn(serial_number, slot_number, enclosure_device_id, drive_state)

    check_disk_insert_and_remove(disk_list)
    return metrics.values()


def collect_sas_raid_state(metrics, infos):
    disk_list = {}
    for line in infos.splitlines():
        if not line.strip().isdigit():
            continue
        raid_info = bash_o("sas3ircu %s status | grep -E 'Volume ID|Volume state'" % line.strip())
        target_id = "unknown"
        for info in raid_info.splitlines():
            if "Volume ID" in info:
                target_id = info.strip().split(":")[-1].strip()
            else:
                state = info.strip().split(":")[-1].strip()
                if "Inactive" in state:
                    continue
                state_int = convert_raid_state_to_int(state)
                metrics['raid_state'].add_metric([target_id], state_int)
                handle_raid_state(target_id, state_int, state)

        disk_info = bash_o(
            "sas3ircu %s display | grep -E 'Enclosure #|Slot #|State|Serial No|Drive Type'" % line.strip())
        enclosure_device_id = slot_number = state = serial_number = "unknown"
        for info in disk_info.splitlines():
            k = info.split(":")[0].strip()
            v = info.split(":")[1].strip()
            if "Enclosure #" == k:
                enclosure_device_id = v
            elif "Slot #" == k:
                slot_number = v
            elif "State" == k:
                state = v.split(" ")[0].strip()
            elif "Serial No" == k:
                serial_number = v
            elif "Drive Type" == k:
                drive_status = convert_disk_state_to_int(state)
                metrics['physical_disk_state'].add_metric([slot_number, enclosure_device_id], drive_status)
                if drive_status != 20:
                    disk_list[serial_number] = "%s-%s" % (enclosure_device_id, slot_number)
                if drive_status == 0 and is_disk_status_abnormal(serial_number):
                    remove_disk_status_abnormal(serial_number)
                elif drive_status != 0:
                    send_physical_disk_status_alarm_to_mn(serial_number, slot_number, enclosure_device_id, state)

    check_disk_insert_and_remove(disk_list)
    return metrics.values()


def collect_mega_raid_state(metrics, infos):
    disk_list = {}
    vd_infos = jsonobject.loads(infos.strip())

    # collect raid vd state
    for controller in vd_infos["Controllers"]:
        controller_id = controller["Command Status"]["Controller"]
        data = controller["Response Data"]
        for attr in dir(data):
            match = re.match(r"/c%s/v(\d+)" % controller_id, attr)
            if not match:
                continue
            vd_state = data[attr][0]["State"]
            disk_group = data[attr][0]["DG/VD"].split("/")[0]
            converted_vd_state = convert_raid_state_to_int(vd_state)
            metrics['raid_state'].add_metric([disk_group], converted_vd_state)
            handle_raid_state(disk_group, converted_vd_state, vd_state)

    # collect disk state
    o = bash_o("/opt/MegaRAID/storcli/storcli64 /call/eall/sall show all J").strip()
    pd_infos = jsonobject.loads(o.strip())
    for controller in pd_infos["Controllers"]:
        controller_id = controller["Command Status"]["Controller"]
        data = controller["Response Data"]
        for attr in dir(data):
            match = re.match(r"^Drive /c%s/e(\d+)/s(\d+)$" % controller_id, attr)
            if not match:
                continue
            enclosure_id = match.group(1)
            slot_id = match.group(2)
            pd_state = data[attr][0]["State"]
            converted_pd_status = convert_disk_state_to_int(pd_state)
            metrics['physical_disk_state'].add_metric([slot_id, enclosure_id], converted_pd_status)
            pd_path = "/c%s/e%s/s%s" % (controller_id, enclosure_id, slot_id)
            pd_attributes = data["Drive %s - Detailed Information" % pd_path]["Drive %s Device attributes" % pd_path]
            serial_number = pd_attributes["SN"].replace(" ", "")
            disk_list[serial_number] = "%s-%s" % (enclosure_id, slot_id)
            if converted_pd_status == 0 and is_disk_status_abnormal(serial_number):
                remove_disk_status_abnormal(serial_number)
            elif converted_pd_status != 0:
                send_physical_disk_status_alarm_to_mn(serial_number, slot_id, enclosure_id, converted_pd_status)

    check_disk_insert_and_remove(disk_list)
    return metrics.values()


def collect_mini_raid_state():
    metrics = {
        'raid_state': GaugeMetricFamily('raid_state',
                                        'raid state', None, ['target_id']),
        'physical_disk_state': GaugeMetricFamily('physical_disk_state',
                                                 'physical disk state', None,
                                                 ['slot_number', 'disk_group']),
        'physical_disk_temperature': GaugeMetricFamily('physical_disk_temperature',
                                                       'physical disk temperature', None,
                                                       ['slot_number', 'disk_group']),
    }
    if bash_r("/opt/MegaRAID/MegaCli/MegaCli64 -LDInfo -LALL -aAll") != 0:
        return metrics.values()

    raid_info = bash_o(
        "/opt/MegaRAID/MegaCli/MegaCli64 -LDInfo -LALL -aAll | grep -E 'Target Id|State'").strip().splitlines()
    target_id = state = "unknown"
    for info in raid_info:
        if "Target Id" in info:
            target_id = info.strip().strip(")").split(" ")[-1]
        else:
            state = info.strip().split(" ")[-1]
            metrics['raid_state'].add_metric([target_id], convert_raid_state_to_int(state))

    disk_info = bash_o(
        "/opt/MegaRAID/MegaCli/MegaCli64 -PDList -aAll | grep -E 'Slot Number|DiskGroup|Firmware state|Drive Temperature'").strip().splitlines()
    slot_number = state = disk_group = "unknown"
    for info in disk_info:
        if "Slot Number" in info:
            slot_number = info.strip().split(" ")[-1]
        elif "DiskGroup" in info:
            kvs = info.replace("Drive's position: ", "").split(",")
            disk_group = filter(lambda x: "DiskGroup" in x, kvs)[0]
            disk_group = disk_group.split(" ")[-1]
        elif "Drive Temperature" in info:
            temp = info.split(":")[1].split("C")[0]
            metrics['physical_disk_temperature'].add_metric([slot_number, disk_group], int(temp))
        else:
            disk_group = "JBOD" if disk_group == "unknown" and info.count("JBOD") > 0 else disk_group
            disk_group = "unknown" if disk_group is None else disk_group

            state = info.strip().split(":")[-1]
            metrics['physical_disk_state'].add_metric([slot_number, disk_group], convert_disk_state_to_int(state))

    return metrics.values()


def collect_ssd_state():
    metrics = {
        'ssd_life_left': GaugeMetricFamily('ssd_life_left', 'ssd life left', None, ['disk', 'serial_number']),
        'ssd_temperature': GaugeMetricFamily('ssd_temperature', 'ssd temperature', None, ['disk', 'serial_number']),
    }

    nvme_serial_numbers = set()
    r, o = bash_ro("lsblk -d -o name,type,rota | grep -w disk | awk '$3 == 0 {print $1}'")  # type: (int, str)
    if r != 0 or o.strip() == "":
        return metrics.values()

    for line in o.splitlines():
        disk_name = line.strip()
        r, o = bash_ro("smartctl -i /dev/%s | grep 'Serial Number' | awk '{print $3}'" % disk_name)
        if r != 0 or o.strip() == "":
            continue
        serial_number = o.strip()

        if disk_name.startswith('nvme'):
            nvme_serial_numbers.add(serial_number)
            r, o = bash_ro("smartctl -A /dev/%s | grep -E '^Percentage Used:|^Temperature:'" % disk_name)
            if r != 0 or o.strip() == "":
                continue

            for info in o.splitlines():
                info = info.strip()
                if info.startswith("Percentage Used:") and info.split(":")[1].split("%")[0].strip().isdigit():
                    metrics['ssd_life_left'].add_metric([disk_name, serial_number], float(
                        float(100) - float(info.split(":")[1].split("%")[0].strip())))
                elif info.startswith("Temperature:") and info.split(":")[1].split()[0].strip().isdigit():
                    metrics['ssd_temperature'].add_metric([disk_name, serial_number],
                                                          float(info.split(":")[1].split()[0].strip()))
        else:
            r, o = bash_ro("smartctl -A /dev/%s | grep -E 'Media_Wearout_Indicator|Temperature_Celsius'" % disk_name)
            if r != 0 or o.strip() == "":
                continue
            for info in o.splitlines():
                info = info.strip()
                if "Media_Wearout_Indicator" in info and info.split()[4].strip().isdigit():
                    metrics['ssd_life_left'].add_metric([disk_name, serial_number], float(info.split()[4].strip()))
                elif "Temperature_Celsius" in info and info.split()[9].strip().isdigit():
                    metrics['ssd_temperature'].add_metric([disk_name, serial_number], float(info.split()[9].strip()))
    check_nvme_disk_insert_and_remove(nvme_serial_numbers)
    return metrics.values()


def check_nvme_disk_insert_and_remove(nvme_serial_numbers):
    global nvme_serial_numbers_record
    if nvme_serial_numbers_record is None:
        nvme_serial_numbers_record = nvme_serial_numbers
        return

    if nvme_serial_numbers_record == nvme_serial_numbers:
        return

    for serial_number in nvme_serial_numbers:
        if serial_number not in nvme_serial_numbers_record:
            send_physical_disk_insert_alarm_to_mn(serial_number, "unknown-unknown")

    for serial_number in nvme_serial_numbers_record:
        if serial_number not in nvme_serial_numbers:
            send_physical_disk_remove_alarm_to_mn(serial_number, "unknown-unknown")

    nvme_serial_numbers_record = nvme_serial_numbers


collect_equipment_state_last_time = None
collect_equipment_state_last_result = None


def collect_ipmi_state():
    metrics = {
        'power_supply': GaugeMetricFamily('power_supply',
                                          'power supply', None, ['ps_id']),
        "power_supply_current_output_power": GaugeMetricFamily('power_supply_current_output_power',
                                                               'power supply current output power', None, ['ps_id']),
        'ipmi_status': GaugeMetricFamily('ipmi_status', 'ipmi status', None, []),
        "fan_speed_rpm": GaugeMetricFamily('fan_speed_rpm', 'fan speed rpm', None, ['fan_speed_name']),
        "fan_speed_state": GaugeMetricFamily('fan_speed_state', 'fan speed state', None, ['fan_speed_name']),
        "cpu_temperature": GaugeMetricFamily('cpu_temperature', 'cpu temperature', None, ['cpu']),
        "cpu_status": GaugeMetricFamily('cpu_status', 'cpu status', None, ['cpu']),
        "physical_memory_status": GaugeMetricFamily('physical_memory_status', 'physical memory status', None,
                                                    ['slot_number']),
    }

    global collect_equipment_state_last_time
    global collect_equipment_state_last_result

    if collect_equipment_state_last_time is None or (time.time() - collect_equipment_state_last_time) >= 25:
        collect_equipment_state_last_time = time.time()
    elif (time.time() - collect_equipment_state_last_time) < 25 and collect_equipment_state_last_result is not None:
        return collect_equipment_state_last_result

    # get ipmi status
    metrics['ipmi_status'].add_metric([], bash_r("ipmitool mc info"))

    # get cpu info
    if not is_hygon:
        r, cpu_temps = bash_ro("sensors")
        if r == 0:
            count = 0
            for info in cpu_temps.splitlines():
                match = re.search(r'^(Physical|Package) id[^+]*\+(\d*\.\d+)', info)
                if match:
                    cpu_id = "CPU" + str(count)
                    metrics['cpu_temperature'].add_metric([cpu_id], float(match.group(2).strip()))
                    count = count + 1

            if count == 0:
                for info in cpu_temps.splitlines():
                    match = re.search(r'^temp[^+]*\+(\d*\.\d+)', info)
                    if match:
                        cpu_id = "CPU" + str(count)
                        metrics['cpu_temperature'].add_metric([cpu_id], float(match.group(1).strip()))
                        count = count + 1

    # get cpu status
    r, cpu_infos = bash_ro("hd_ctl -c cpu")
    if r == 0:
        infos = jsonobject.loads(cpu_infos)
        for info in infos:
            cpu_id = "CPU" + info.Processor
            if "populated" in info.Status.lower() and "enabled" in info.Status.lower():
                metrics['cpu_status'].add_metric([cpu_id], 0)
                if is_cpu_status_abnormal(cpu_id):
                    remove_cpu_status_abnormal(cpu_id)
            elif "" == info.Status:
                metrics['cpu_status'].add_metric([cpu_id], 20)
                if is_cpu_status_abnormal(cpu_id):
                    remove_cpu_status_abnormal(cpu_id)
            else:
                metrics['cpu_status'].add_metric([cpu_id], 10)
                send_cpu_status_alarm_to_mn(cpu_id, info.Status)

    # get physical memory info
    r, memory_infos = bash_ro("hd_ctl -c memory")
    if r == 0:
        memory_locator_list = collect_memory_locator()
        infos = jsonobject.loads(memory_infos)
        for info in infos:
            slot_number = info.Locator
            if slot_number in memory_locator_list:
                memory_locator_list.remove(slot_number)
            if "ok" == info.State.lower():
                metrics['physical_memory_status'].add_metric([slot_number], 0)
                if is_memory_status_abnormal(slot_number):
                    remove_memory_status_abnormal(slot_number)
            elif "" == info.State:
                metrics['physical_memory_status'].add_metric([slot_number], 20)
                if is_memory_status_abnormal(slot_number):
                    remove_memory_status_abnormal(slot_number)
            else:
                metrics['physical_memory_status'].add_metric([slot_number], 10)
                send_physical_memory_status_alarm_to_mn(slot_number, info.State)

        if len(memory_locator_list) != 0:
            for locator in memory_locator_list:
                metrics['physical_memory_status'].add_metric([locator], 10)
                send_physical_memory_status_alarm_to_mn(locator, "unknown")

    # get fan info
    origin_fan_flag = False
    r, fan_infos = bash_ro("hd_ctl -c fan")
    if r == 0:
        infos = jsonobject.loads(fan_infos)
        for info in infos.fan_list:
            fan_name = info.Name
            if fan_name == "":
                origin_fan_flag = True
                break
            if info.Status == "":
                origin_fan_flag = True
                break

            fan_rpm = "0" if info.SpeedRPM == "" else info.SpeedRPM
            metrics['fan_speed_rpm'].add_metric([fan_name], float(fan_rpm))

            if "ok" == info.Status.lower():
                metrics['fan_speed_state'].add_metric([fan_name], 0)
                if is_fan_status_abnormal(fan_name):
                    remove_fan_status_abnormal(fan_name)
            elif "" == info.Status:
                metrics['fan_speed_state'].add_metric([fan_name], 20)
                if is_fan_status_abnormal(fan_name):
                    remove_fan_status_abnormal(fan_name)
            else:
                metrics['fan_speed_state'].add_metric([fan_name], 10)
                send_physical_fan_status_alarm_to_mn(fan_name, info.Status)
    else:
        origin_fan_flag = True

    # get power info
    r, sdr_data = bash_ro("ipmitool sdr elist")
    if r == 0:
        power_list = []
        for line in sdr_data.splitlines():
            info = line.lower().strip()
            if re.match(r"^ps\w*(\ |_)status", info):
                ps_id = info.split("|")[0].strip().split(" ")[0].split("_")[0]
                ps_state = info.split("|")[4].strip()
                if "presence detected" == ps_state:
                    metrics['power_supply'].add_metric([ps_id], 0)
                elif "presence detected" in ps_state and "ac lost" in ps_state:
                    metrics['power_supply'].add_metric([ps_id], 10)
                else:
                    metrics['power_supply'].add_metric([ps_id], 20)
            elif re.match(r"^ps\w*(\ |_)(pin|pout)", info):
                ps_id = info.split("|")[0].strip().split(" ")[0].split("_")[0]
                if "pout" in info and ps_id in power_list:
                    continue
                ps_out_power = info.split("|")[4].strip().lower()
                ps_out_power = float(filter(str.isdigit, ps_out_power)) if bool(
                    re.search(r'\d', ps_out_power)) else float(0)
                metrics['power_supply_current_output_power'].add_metric([ps_id], ps_out_power)
                power_list.append(ps_id)
            elif re.match(r"\w*fan(\w*(_|\ )speed|[a-z0-9]\ *\|)\w*", info):
                if not origin_fan_flag:
                    continue
                if "m2" in info:
                    continue
                fan_rpm = info.split("|")[4].strip()
                if fan_rpm == "" or fan_rpm == "no reading" or fan_rpm == "disabled":
                    continue
                fan_name = info.split("|")[0].strip()
                fan_state = 0 if info.split("|")[2].strip() == "ok" else 10
                fan_rpm = float(filter(str.isdigit, fan_rpm)) if bool(re.search(r'\d', fan_rpm)) else float(0)
                metrics['fan_speed_state'].add_metric([fan_name], fan_state)
                metrics['fan_speed_rpm'].add_metric([fan_name], fan_rpm)
                if fan_state == 0 and is_fan_status_abnormal(fan_name):
                    remove_fan_status_abnormal(fan_name)
                elif fan_state == 10:
                    send_physical_fan_status_alarm_to_mn(fan_name, info.split("|")[2].strip())
            elif re.match(r"^cpu\d+_core_temp", info):
                if not is_hygon:
                    continue
                pattern = r'cpu(\d+)_core_temp.*?(\d+) degrees c'
                match = re.search(pattern, info)
                if not match:
                    continue
                cpu_id = "CPU" + str(match.group(1))
                temp = float(match.group(2).strip())
                metrics['cpu_temperature'].add_metric([cpu_id], temp)

    collect_equipment_state_last_result = metrics.values()
    return collect_equipment_state_last_result


@thread.AsyncThread
def check_equipment_state_from_ipmitool(metrics):
    sensor_handlers = {
        "Memory": send_physical_memory_status_alarm_to_mn,
        "Fan": send_physical_fan_status_alarm_to_mn,
        "Power Supply": send_physical_power_supply_status_alarm_to_mn
    }

    r, sensor_infos = bash_ro(
        "ipmi-sensors --sensor-types=Memory,fan,Power_Supply -Q --ignore-unrecognized-events --comma-separated-output "
        "--no-header-output --sdr-cache-recreate --output-sensor-state")
    if r == 0:
        for sensor_info in sensor_infos.splitlines():
            sensor = sensor_info.split(",")
            sensor_name = sensor[1].strip()
            sensor_type = sensor[2].strip()
            sensor_state = sensor[3].strip()
            sensor_event = sensor[6].strip()

            if sensor_type == "Memory" and "Presence detected" in sensor_event:
                metrics['ipmi_memory_status'].add_metric([sensor_name, sensor_type],
                                                         0 if sensor_state == 'Nominal' else 1)

            if sensor_state.lower() == "critical" and sensor_type in sensor_handlers:
                sensor_handlers[sensor_type](sensor_name, sensor_state)
            else:
                remove_fan_status_abnormal(sensor_name)
                remove_power_supply_status_abnormal(sensor_name)
                remove_memory_status_abnormal(sensor_name)


def collect_equipment_state_from_ipmi():
    metrics = {
        "ipmi_status": GaugeMetricFamily('ipmi_status', 'ipmi status', None, []),
        "cpu_temperature": GaugeMetricFamily('cpu_temperature', 'cpu temperature', None, ['cpu']),
        "cpu_status": GaugeMetricFamily('cpu_status', 'cpu status', None, ['cpu']),
        "ipmi_memory_status": GaugeMetricFamily('ipmi_memory_status', 'ipmi memory status', None, ['name', 'type']),
    }
    metrics['ipmi_status'].add_metric([], bash_r("ipmitool mc info"))

    r, cpu_info = bash_ro("ipmitool sdr elist | grep -i cpu")  # type: (int, str)
    if r != 0:
        return metrics.values()

    check_equipment_state_from_ipmitool(metrics)

    '''
        ================
        CPU TEMPERATURE
        ================
        CPU1_Temp        | 39h | ok  |  7.18 | 34 degrees C
        CPU1_Core_Temp   | 39h | ok  |  7.18 | 34 degrees C
        CPU_Temp_01      | 39h | ok  |  7.18 | 34 degrees C
        CPU1 Temp        | 39h | ok  |  7.18 | 34 degrees C
        CPU1 Core Rem    | 04h | ok  |  3.96 | 41 degrees C
        
        ================
        CPU STATUS
        ================
        CPU_STATUS_01    | 52h | ok  |  3.0 | Presence detected
        CPU1 Status      | 3Ch | ok  |  3.96 | Presence detected
        CPU1_Status      | 7Eh | ok  |  3.0 | Presence detected
    '''

    cpu_temperature_pattern = r'^(cpu\d+_temp|cpu\d+_core_temp|cpu_temp_\d+|cpu\d+ temp|cpu\d+ core rem)$'
    cpu_status_pattern = r'^(cpu_status_\d+|cpu\d+ status|cpu\d+_status)$'

    for line in cpu_info.lower().splitlines():
        sensor = line.split("|")
        if len(sensor) != 5:
            continue
        sensor_id = sensor[0].strip()
        sensor_value = sensor[4].strip()
        if re.match(cpu_temperature_pattern, sensor_id):
            cpu_id = int(re.sub(r'\D', '', sensor_id))
            cpu_temperature_match = re.search(r'(-?\d+(\.\d+)?)', sensor_value)
            cpu_temperature = float(cpu_temperature_match.group(1)) if cpu_temperature_match else 0
            metrics['cpu_temperature'].add_metric(["CPU%d" % cpu_id], float(cpu_temperature))
        if re.match(cpu_status_pattern, sensor_id):
            cpu_id = int(re.sub(r'\D', '', sensor_id))
            cpu_status = 0 if "presence detected" == sensor_value else 10
            metrics['cpu_status'].add_metric(["CPU%d" % cpu_id], float(cpu_status))
            if cpu_status == 10:
                send_cpu_status_alarm_to_mn(cpu_id, sensor_value)
            else:
                remove_cpu_status_abnormal(cpu_id)

    return metrics.values()


def collect_equipment_state():
    metrics = {
        'power_supply': GaugeMetricFamily('power_supply',
                                          'power supply', None, ['ps_id']),
        'ipmi_status': GaugeMetricFamily('ipmi_status', 'ipmi status', None, []),
    }

    r, ps_info = bash_ro("ipmitool sdr type 'power supply'")  # type: (int, str)
    if r == 0:
        for info in ps_info.splitlines():
            info = info.strip()
            ps_id = info.split("|")[0].strip().split(" ")[0]
            health = 10 if "fail" in info.lower() or "lost" in info.lower() else 0
            metrics['power_supply'].add_metric([ps_id], health)

    metrics['ipmi_status'].add_metric([], bash_r("ipmitool mc info"))
    return metrics.values()


def fetch_vm_qemu_processes():
    processes = []
    for process in psutil.process_iter():
        try:
            if process.name() == QEMU_CMD or QEMU_CMD in process.cmdline(): # /usr/libexec/qemu-kvm
                processes.append(process)
        except psutil.NoSuchProcess:
            pass
        if process.name() == QEMU_CMD:  # /usr/libexec/qemu-kvm
            processes.append(process)
    return processes


def find_vm_uuid_from_vm_qemu_process(process):
    prefix = 'guest='
    suffix = ',debug-threads=on'
    try:
        for word in process.cmdline():
            # word like 'guest=707e9d31751e499eb6110cce557b4168,debug-threads=on'
            if word.startswith(prefix) and word.endswith(suffix):
                return word[len(prefix) : len(word) - len(suffix)]
        return None
    except psutil.NoSuchProcess:
        return None
    for word in process.cmdline():
        # word like 'guest=707e9d31751e499eb6110cce557b4168,debug-threads=on'
        if word.startswith(prefix) and word.endswith(suffix):
            return word[len(prefix): len(word) - len(suffix)]
    return None


def collect_vm_statistics():
    metrics = {
        'cpu_occupied_by_vm': GaugeMetricFamily('cpu_occupied_by_vm',
                                                'Percentage of CPU used by vm', None, ['vmUuid'])
    }

    processes = fetch_vm_qemu_processes()
    if len(processes) == 0:
        return metrics.values()

    pid_vm_map = {}
    for process in processes:
        pid_vm_map[str(process.pid)] = find_vm_uuid_from_vm_qemu_process(process)

    def collect(vm_pid_arr):
        vm_pid_arr_str = ','.join(vm_pid_arr)

        r, pid_cpu_usages_str = bash_ro("top -b -n 1 -p %s -w 512" % vm_pid_arr_str)
        if r != 0 or not pid_cpu_usages_str:
            return

        for pid_cpu_usage in pid_cpu_usages_str.splitlines():
            if QEMU_CMD not in pid_cpu_usage:
                continue
            arr = pid_cpu_usage.split()
            pid = arr[0]
            vm_uuid = pid_vm_map[pid]
            cpu_usage = arr[8]
            metrics['cpu_occupied_by_vm'].add_metric([vm_uuid], float(cpu_usage))

    n = 16  # procps/top has '#define MONPIDMAX  20'
    for i in range(0, len(pid_vm_map.keys()), n):
        collect(pid_vm_map.keys()[i:i + n])

    return metrics.values()


# since Cloud 4.5.0, Because GetVmGuestToolsAction calls are too frequent,
# the information about whether pvpanic is configured for VM
# will flow to the management node through the monitoring data.
# @see ZSTAC-49036
def collect_vm_pvpanic_enable_in_domain_xml():
    KEY = 'pvpanic_enable_in_domain_xml'
    metrics = {
        KEY: GaugeMetricFamily(KEY,
                               'Whether the pvpanic attribute of the VM enabled in the domain XML', None, ['vmUuid'])
    }

    processes = fetch_vm_qemu_processes()
    if len(processes) == 0:
        return metrics.values()

    # if pvpanic enable in domain xml (qemu process cmdline has 'pvpanic,ioport'), collect '1'
    # if not, collect '0'
    for process in processes:
        vm_uuid = find_vm_uuid_from_vm_qemu_process(process)
        r = ""
        try:
            r = filter(lambda word: word == 'pvpanic,ioport=1285', process.cmdline())
        except psutil.NoSuchProcess:
            pass

        enable = 1 if len(r) > 0 else 0
        metrics[KEY].add_metric([vm_uuid], enable)

    return metrics.values()


collect_node_disk_wwid_last_time = None
collect_node_disk_wwid_last_result = None
sblk_pv_vg = {}
sblk_pv_identities = {}
sblk_pv_state_fail_last_report_time = {}


def collect_node_disk_wwid():
    def get_physical_devices(pvpath, is_mpath):
        if is_mpath:
            dm_name = os.path.basename(os.path.realpath(pvpath))
            disks = os.listdir("/sys/block/%s/slaves/" % dm_name)
        else:
            disks = [os.path.basename(pvpath)]

        return ["/dev/%s" % re.sub('[0-9]$', '', s) for s in disks]

    def get_device_from_path(ctx, devpath):
        return pyudev.Device.from_device_file(ctx, devpath)

    def get_disk_wwids(b):
        links = b.get('DEVLINKS')
        if not links:
            return []

        return [os.path.basename(str(p)) for p in links.split() if "disk/by-id" in p and "lvm-pv" not in p]

    global collect_node_disk_wwid_last_time
    global collect_node_disk_wwid_last_result
    global sblk_pv_vg
    global sblk_pv_identities

    # NOTE(weiw): some storage can not afford frequent TUR. ref: ZSTAC-23416
    if collect_node_disk_wwid_last_time is None or (time.time() - collect_node_disk_wwid_last_time) >= 300:
        collect_node_disk_wwid_last_time = time.time()
    elif (time.time() - collect_node_disk_wwid_last_time) < 300 and collect_node_disk_wwid_last_result is not None:
        return collect_node_disk_wwid_last_result

    metrics = {
        'node_disk_wwid': GaugeMetricFamily('node_disk_wwid',
                                            'node disk wwid', None, ["disk", "wwid"])
    }

    collect_node_disk_wwid_last_result = metrics.values()

    o = bash_o("pvs --nolocking -t --noheading -o pv_name,vg_name").strip().splitlines()
    context = pyudev.Context()

    sblk_pv_vg = {}
    sblk_pv_identities = {}
    for line in o:
        pv, vg = line.strip().split()
        dm_uuid = get_device_from_path(context, pv).get("DM_UUID", "")
        multipath_wwid = dm_uuid[6:] if dm_uuid.startswith("mpath-") else None

        for disk in get_physical_devices(pv, multipath_wwid):
            disk_name = os.path.basename(disk)
            wwids = get_disk_wwids(get_device_from_path(context, disk))
            if multipath_wwid is not None:
                wwids.append(multipath_wwid)
            if len(wwids) > 0:
                metrics['node_disk_wwid'].add_metric([disk_name, ";".join([w.strip() for w in sorted(wwids)])], 1)
                sblk_pv_identities[disk_name] = ";".join([w.strip() for w in wwids])

            sblk_pv_vg[disk_name] = vg

    collect_node_disk_wwid_last_result = metrics.values()
    return collect_node_disk_wwid_last_result


def collect_memory_overcommit_statistics():
    global PAGE_SIZE

    metrics = {
        'host_ksm_pages_shared_in_bytes': GaugeMetricFamily('host_ksm_pages_shared_in_bytes',
                                                            'host ksm shared pages', None, []),
        'host_ksm_pages_sharing_in_bytes': GaugeMetricFamily('host_ksm_pages_sharing_in_bytes',
                                                             'host ksm sharing pages', None, []),
        'host_ksm_pages_unshared_in_bytes': GaugeMetricFamily('host_ksm_pages_unshared_in_bytes',
                                                              'host ksm unshared pages', None, []),
        'host_ksm_pages_volatile': GaugeMetricFamily('host_ksm_pages_volatile',
                                                     'host ksm volatile pages', None, []),
        'host_ksm_full_scans': GaugeMetricFamily('host_ksm_full_scans',
                                                 'host ksm full scans', None, []),
        'collectd_virt_memory': GaugeMetricFamily('collectd_virt_memory',
                                                  'collectd_virt_memory gauge', None, ['instance', 'type', 'virt']),
    }

    if PAGE_SIZE is None:
        return metrics.values()

    # read metric from /sys/kernel/mm/ksm
    value = linux.read_file("/sys/kernel/mm/ksm/pages_shared")
    if value:
        metrics['host_ksm_pages_shared_in_bytes'].add_metric([], float(value.strip()) * PAGE_SIZE)

    value = linux.read_file("/sys/kernel/mm/ksm/pages_sharing")
    if value:
        metrics['host_ksm_pages_sharing_in_bytes'].add_metric([], float(value.strip()) * PAGE_SIZE)

    value = linux.read_file("/sys/kernel/mm/ksm/pages_unshared")
    if value:
        metrics['host_ksm_pages_unshared_in_bytes'].add_metric([], float(value.strip()) * PAGE_SIZE)

    value = linux.read_file("/sys/kernel/mm/ksm/pages_volatile")
    if value:
        metrics['host_ksm_pages_volatile'].add_metric([], float(value.strip()))

    value = linux.read_file("/sys/kernel/mm/ksm/full_scans")
    if value:
        metrics['host_ksm_full_scans'].add_metric([], float(value.strip()))

    with asyncDataCollectorLock:
        for domain_name, maximum_memory in domain_max_memory.items():
            metrics['collectd_virt_memory'].add_metric([domain_name, "max_balloon", domain_name],
                                                       1024 * float(maximum_memory.strip()))

    return metrics.values()


def collect_physical_network_interface_state():
    metrics = {
        'physical_network_interface': GaugeMetricFamily('physical_network_interface',
                                                        'physical network interface', None,
                                                        ['interface_name', 'speed']),
    }

    nics = get_host_physicl_nics()
    if len(nics) != 0:
        for nic in nics:
            nic = nic.strip()
            try:
                # NOTE(weiw): sriov nic contains carrier file but can not read
                status = linux.read_nic_carrier("/sys/class/net/%s/carrier" % nic).strip() == "1"
            except Exception as e:
                status = False
            speed = str(get_nic_supported_max_speed(nic))
            metrics['physical_network_interface'].add_metric([nic, speed], status)

    return metrics.values()


def collect_host_conntrack_statistics():
    metrics = {
        'zstack_conntrack_in_count': GaugeMetricFamily('zstack_conntrack_in_count',
                                                       'zstack conntrack in count'),
        'zstack_conntrack_in_percent': GaugeMetricFamily('zstack_conntrack_in_percent',
                                                         'zstack conntrack in percent')
    }
    conntrack_count = linux.read_file("/proc/sys/net/netfilter/nf_conntrack_count")
    metrics['zstack_conntrack_in_count'].add_metric([], float(conntrack_count))

    conntrack_max = linux.read_file("/proc/sys/net/netfilter/nf_conntrack_max")
    percent = float(format(float(conntrack_count) / float(conntrack_max) * 100, '.2f'))
    conntrack_percent = 1.0 if percent <= 1.0 else percent
    metrics['zstack_conntrack_in_percent'].add_metric([], conntrack_percent)

    return metrics.values()


def parse_nvidia_smi_output_to_list(data):
    lines = data.splitlines()
    vgpu_list = []
    current_vgpu = None
    for line in lines:
        indentation = len(line) - len(line.lstrip())
        line = line.strip()
        if "vGPU ID" in line:
            if current_vgpu is not None:
                vgpu_list.append(current_vgpu)
            current_vgpu = {}
        if ':' in line and current_vgpu is not None:
            key, value = map(str.strip, line.split(':', 1))
            if value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit() and '%' in value:
                value = float(value.replace('%', ''))
            current_vgpu[key] = value
    if current_vgpu is not None:
        vgpu_list.append(current_vgpu)
    return vgpu_list


def handle_gpu_status(gpu_status, pci_device_address):
    if gpu_status == 'critical':
        send_physical_gpu_status_alarm_to_mn(gpu_status, pci_device_address)
    else:
        remove_gpu_status_abnormal(pci_device_address)


def get_gpu_metrics():
    return {
        "host_gpu_power_draw": GaugeMetricFamily('host_gpu_power_draw', 'gpu power draw', None,
                                            ['pci_device_address', 'gpu_serial']),
        "host_gpu_temperature": GaugeMetricFamily('host_gpu_temperature', 'gpu temperature', None,
                                             ['pci_device_address', 'gpu_serial']),
        "host_gpu_fan_speed": GaugeMetricFamily('host_gpu_fan_speed', 'current percentage of gpu fan speed', None,
                                           ['pci_device_address', 'gpu_serial']),
        "host_gpu_utilization": GaugeMetricFamily('host_gpu_utilization', 'gpu utilization', None, ['pci_device_address']),
        "host_gpu_memory_utilization": GaugeMetricFamily('host_gpu_memory_utilization', 'gpu memory utilization', None,
                                                    ['pci_device_address', 'gpu_serial']),
        "host_gpu_rxpci_in_bytes": GaugeMetricFamily('host_gpu_rxpci_in_bytes', 'gpu rxpci in bytes', None,
                                                ['pci_device_address', 'gpu_serial']),
        "host_gpu_txpci_in_bytes": GaugeMetricFamily('host_gpu_txpci_in_bytes', 'gpu txpci in bytes', None,
                                                ['pci_device_address', 'gpu_serial']),
        "host_gpu_status": GaugeMetricFamily('host_gpu_status', 'gpu status, 0 is critical, 1 is nominal', None,
                                        ['pci_device_address', 'gpuStatus', 'gpu_serial']),
        "vgpu_utilization": GaugeMetricFamily('vgpu_utilization', 'vgpu utilization', None, ['vm_uuid', 'mdev_uuid']),
        "vgpu_memory_utilization": GaugeMetricFamily('vgpu_memory_utilization', 'vgpu memory utilization', None,
                                                     ['vm_uuid', 'mdev_uuid'])
    }


def add_gpu_pci_device_address(type, pci_device_address, gpu_serial):
    pci_device_address_list = gpu_devices.get(type, set())
    pci_device_address_list.add((pci_device_address, gpu_serial))
    gpu_devices[type] = pci_device_address_list

def check_gpu_status_and_save_gpu_status(type, metrics):
    pci_device_address_list = gpu_devices.get(type, set())
    for pci_device_address, gpu_serial in pci_device_address_list:
        gpuStatus, gpu_status_int_value = convert_pci_status_to_int(pci_device_address)
        if gpu_status_int_value == 2:
            pci_device_address_list.discard((pci_device_address, gpu_serial))
            gpu_devices[type] = pci_device_address_list
            continue

        metrics['host_gpu_status'].add_metric([pci_device_address, gpuStatus, gpu_serial], gpu_status_int_value)
        handle_gpu_status(gpuStatus, pci_device_address)


def calculate_percentage(part, total):
    if total == 0:
        return "0.0"
    percentage = (float(part) / float(total)) * 100
    return round(percentage, 1)


def collect_tianshu_gpu_status():
    metrics = get_gpu_metrics()

    if has_ix_smi() is False:
        return metrics.values()
    if shell.run(gpu.is_tianshu_v1()) == 0:
        cmd = gpu.get_tianshu_gpu_metric_info_cmd_v1()
    else:
        cmd = gpu.get_tianshu_gpu_metric_info_cmd_v2()

    r, gpu_info = bash_ro(cmd)
    if r != 0:
        check_gpu_status_and_save_gpu_status("TIANSHU", metrics)
        return metrics.values()

    for info in gpu_info.splitlines():
        info = info.strip().split(',')
        pci_device_address = info[5].strip().lower()
        gpu_serial = info[6].strip()
        if len(pci_device_address.split(':')[0]) == 8:
            pci_device_address = pci_device_address[4:].lower()

        add_gpu_pci_device_address("TIANSHU", pci_device_address, gpu_serial)

        add_metrics('host_gpu_power_draw', info[0].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_temperature', info[1].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_utilization', info[2].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_memory_utilization', info[3].strip(), [pci_device_address, gpu_serial], metrics)
        if len(info) == 8:
            add_metrics('host_gpu_fan_speed', info[7].strip(), [pci_device_address, gpu_serial], metrics)
        check_gpu_status_and_save_gpu_status("TIANSHU", metrics)
    return metrics.values()


def collect_nvidia_gpu_status():
    metrics = get_gpu_metrics()

    if has_nvidia_smi() is False:
        return metrics.values()

    r, gpu_info = bash_ro(
        "nvidia-smi --query-gpu=power.draw,temperature.gpu,fan.speed,utilization.gpu,utilization.memory,index,"
        "gpu_bus_id,gpu_serial,memory.used,memory.total --format=csv,noheader")
    if r != 0:
        check_gpu_status_and_save_gpu_status("NVIDIA", metrics)
        return metrics.values()

    for info in gpu_info.splitlines():
        info = info.strip().split(',')
        pci_device_address = info[6].strip().lower()
        gpu_serial = info[7].strip()
        if len(pci_device_address.split(':')[0]) == 8:
            pci_device_address = pci_device_address[4:].lower()

        add_gpu_pci_device_address("NVIDIA", pci_device_address, gpu_serial)

        add_metrics('host_gpu_power_draw', info[0].replace('W', '').strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_temperature', info[1].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_fan_speed', info[2].replace('%', '').strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_utilization', info[3].replace('%', '').strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_memory_utilization', calculate_percentage(info[8].replace('MiB', '').strip(), info[9].replace('MiB', '').strip()),
                    [pci_device_address, gpu_serial], metrics)
        r, gpu_pci_rx_tx = bash_ro("nvidia-smi pci -gCnt -i %s" % info[5].strip())
        if r != 0:
            logger.warn("get gpu[%s] pcie rx/tx count failed" % info[5].strip())
            continue

        for line in gpu_pci_rx_tx.splitlines():
            line = line.strip()

            if line.startswith("TX_BYTES:"):
                add_metrics('host_gpu_txpci_in_bytes', line.split()[-1], [pci_device_address, gpu_serial], metrics)
            if line.startswith("RX_BYTES:"):
                add_metrics('host_gpu_rxpci_in_bytes', line.split()[-1], [pci_device_address, gpu_serial], metrics)

    check_gpu_status_and_save_gpu_status("NVIDIA", metrics)

    r, vgpu_info = bash_ro("nvidia-smi vgpu -q")
    if r != 0 or "VM Name" not in vgpu_info:
        return metrics.values()

    for vgpu in parse_nvidia_smi_output_to_list(vgpu_info):
        vm_uuid = vgpu["VM Name"]
        mdev_uuid = vgpu["MDEV UUID"].replace('-', '')
        add_metrics('vgpu_utilization', vgpu['Gpu'].replace('%', '').strip(), [vm_uuid, mdev_uuid], metrics)
        add_metrics('vgpu_memory_utilization', vgpu['Memory'].replace('%', '').strip(), [vm_uuid, mdev_uuid], metrics)
    return metrics.values()


def collect_huawei_gpu_status():
    metrics = get_gpu_metrics()
    metrics['host_gpu_ddr_capacity'] = GaugeMetricFamily('host_gpu_ddr_capacity', 'gpu DDR Capacity', None,
                                            ['pci_device_address', 'gpu_serial'])
    metrics['host_gpu_ddr_usage_rate'] = GaugeMetricFamily('host_gpu_ddr_usage_rate', 'gpu DDR Usage Rate(%)', None,
                                            ['pci_device_address', 'gpu_serial'])
    metrics['host_gpu_hbm_capacity'] = GaugeMetricFamily('host_gpu_hbm_capacity', 'gpu HBM Capacity', None,
                                            ['pci_device_address', 'gpu_serial'])
    metrics['host_gpu_hbm_rate'] = GaugeMetricFamily('host_gpu_hbm_rate', 'gpu HBM Usage Rate(%)', None,
                                                         ['pci_device_address', 'gpu_serial'])

    if has_npu_smi() is False:
        return metrics.values()

    r, gpu_info_out = bash_ro("stdbuf -oL timeout 2 npu-smi info watch -d 2 -s ptam")
    if r != 0 and r != 124:
        check_gpu_status_and_save_gpu_status("HUAWEI", metrics)
        return metrics.values()
    npu_ids = set()
    for info in gpu_info_out.splitlines():
        if 'NpuID' in info:
            continue
        gpu_info = [s for s in info.split() if s]

        npu_id = gpu_info[0].strip()
        if npu_id in npu_ids:
            continue
        npu_ids.add(npu_id)
        pci_device_address = None
        gpu_serial = None
        gpu_ddr_capacity = None
        gpu_ddr_usage_rate = None
        gpu_hbm_capacity = None
        gpu_hbm_rate = None
        gpu_power = None

        r, info_out = bash_ro("npu-smi info -t board -i %s;npu-smi info -t power -i %s;npu-smi info -t usages -i %s" % (npu_id, npu_id, npu_id))
        if r != 0:
            logger.error("npu query gpu board is error, %s " % info_out)
            break

        for line in info_out.splitlines():
            line = line.strip()
            if not line:
                continue
            if "PCIe Bus Info" in line:
                pci_device_address = line.split(":", 1)[1].strip().lower()
                continue
            if "Serial Number" in line:
                gpu_serial = line.split(":")[1].strip()
                continue
            if "DDR Capacity(MB)" in line:
                gpu_ddr_capacity = float(line.split(":")[1].strip()) * 1024 * 1024
                continue
            if "DDR Usage Rate" in line:
                gpu_ddr_usage_rate = line.split(":")[1].strip()
                continue
            if "HBM Capacity" in line:
                gpu_hbm_capacity = float(line.split(":")[1].strip()) * 1024 * 1024
                continue
            if "HBM Usage Rate" in line:
                gpu_hbm_rate = line.split(":")[1].strip()
                continue
            if "Power Dissipation" in line:
                gpu_power = line.split(":")[1].strip()

            if (pci_device_address is not None and gpu_serial is not None and gpu_ddr_capacity is not None
                    and gpu_ddr_usage_rate is not None and gpu_ddr_usage_rate is not None and gpu_hbm_capacity is not None
                    and gpu_hbm_rate is not None and gpu_power is not None):
                break

        add_gpu_pci_device_address("HUAWEI", pci_device_address, gpu_serial)
        add_metrics('host_gpu_power_draw', gpu_power if gpu_info[2].strip() == 'NA' else gpu_info[2].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_temperature', gpu_info[3].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_utilization', gpu_info[4].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_memory_utilization', gpu_info[5].strip(), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_ddr_capacity', gpu_ddr_capacity, [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_ddr_usage_rate', gpu_ddr_usage_rate, [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_hbm_capacity', gpu_hbm_capacity, [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_hbm_rate', gpu_hbm_rate, [pci_device_address, gpu_serial], metrics)

    check_gpu_status_and_save_gpu_status("HUAWEI", metrics)
    return metrics.values()

def collect_hy_gpu_status():
    metrics = get_gpu_metrics()

    if has_hy_smi() is False:
        return metrics.values()

    r, gpu_info = bash_ro('hy-smi --showuse --showmemuse  --showpower --showtemp --showserial --showbus --json')
    if r != 0:
        check_gpu_status_and_save_gpu_status("HY", metrics)
        return metrics.values()

    gpu_info_json = json.loads(gpu_info)
    for card_name, card_data in gpu_info_json.items():
        gpu_serial = card_data['Serial Number']
        pci_device_address = card_data["PCI Bus"].lower()
        add_gpu_pci_device_address("HY", pci_device_address, gpu_serial)
        add_metrics('host_gpu_power_draw', card_data.get("Average Graphics Package Power (W)"), [pci_device_address, gpu_serial],
                    metrics)
        add_metrics('host_gpu_temperature', card_data.get("Temperature (Sensor junction) (C)"), [pci_device_address, gpu_serial],
                    metrics)
        add_metrics('host_gpu_fan_speed', card_data.get("Fan speed (%)"), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_utilization', card_data.get("DCU use (%)"), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_memory_utilization', card_data.get("DCU memory use (%)"), [pci_device_address, gpu_serial],
                    metrics)
    check_gpu_status_and_save_gpu_status("HY", metrics)
    return metrics.values()


def collect_amd_gpu_status():
    metrics = get_gpu_metrics()

    if has_rocm_smi() is False:
        return metrics.values()

    r, gpu_info = bash_ro(
        'rocm-smi --showpower --showtemp  --showmemuse --showuse --showfan --showbus  --showserial --json')
    if r != 0:
        check_gpu_status_and_save_gpu_status("AMD", metrics)
        return metrics.values()

    gpu_info_json = json.loads(gpu_info.strip())
    for card_name, card_data in gpu_info_json.items():
        gpu_serial = card_data['Serial Number']
        pci_device_address = card_data['PCI Bus'].lower()
        add_gpu_pci_device_address("AMD", pci_device_address, gpu_serial)
        add_metrics('host_gpu_power_draw', card_data.get('Average Graphics Package Power (W)'), [pci_device_address, gpu_serial],
                    metrics)
        add_metrics('host_gpu_temperature', card_data.get('Temperature (Sensor edge) (C)'), [pci_device_address, gpu_serial],
                    metrics)
        add_metrics('host_gpu_fan_speed', card_data.get('Fan speed (%)'), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_utilization', card_data.get('GPU use (%)'), [pci_device_address, gpu_serial], metrics)
        add_metrics('host_gpu_memory_utilization', card_data.get('GPU Memory Allocated (VRAM%)'),
                    [pci_device_address, gpu_serial], metrics)
    check_gpu_status_and_save_gpu_status("AMD", metrics)
    return metrics.values()


def collect_disk_stat():
    global sblk_pv_state_fail_last_report_time
    class BlockInfo(object):
        def __init__(self):
            self.dev_name = None
            self.state = None
            self.status = None

        def convert_status_to_int(self):
            return 1 if self.status == "active" else 0

        def convert_state_to_int(self):
            return 1 if self.state in ["running", "live"] else 0

    def report_disk_state_abnormal_if_need(b):
        if b.dev_name not in sblk_pv_vg:
            return
        elif b.state in ["running", "live"]:
            sblk_pv_state_fail_last_report_time[b.dev_name] = None
            return

        if sblk_pv_state_fail_last_report_time.get(b.dev_name) is not None \
                and linux.get_current_timestamp() - sblk_pv_state_fail_last_report_time.get(b.dev_name) < 3600:
            logger.debug("sblk pv %s for vg %s state is %s, skip reporting to mn because it has been reported in the past hour"
                         % (b.dev_name, sblk_pv_vg.get(b.dev_name), b.state))
            return

        remove_physical_volume_state_abnormal(b.dev_name)
        send_physical_volume_status_alarm_to_mn(b.dev_name, sblk_pv_identities.get(b.dev_name), b.state, sblk_pv_vg.get(b.dev_name))
        sblk_pv_state_fail_last_report_time[b.dev_name] = linux.get_current_timestamp()


    class BlockInfoGenerator(object):
        def __init__(self):
            self.mpath_generated = False
            self.dev_multipath_stat = {}  # type: dict[str, BlockInfo]

        def _generate_block_mpath_basic_info(self):
            # collect multipath dm info, output example:
            # 0 13107200 multipath 2 0 0 0 3 1 A 0 1 2 8:16 A 0 0 1 E 0 1 2 8:128 A 0 0 1 E 0 1 2 8:224 A 0 0 1
            # 0 13107200 multipath 2 0 0 0 1 1 A 0 3 0 8:16 A 0 8:128 A 0 8:224 A 0
            # 0 88080384 multipath 2 0 0 0 2 1 A 0 1 2 259:0 A 0 0 1 E 0 1 2 259:1 F 1 0 1
            # 0 100663296000 multipath 2 0 0 0 2 1 A 0 2 0 8:224 A 0 8:64 A 0 E 0 2 0 65:144 A 0 65:80 A 0
            r, o = bash_ro("dmsetup status --target multipath")
            if r != 0:
                return
            for line in o.strip().splitlines():
                line = line.strip()
                path_groups = re.findall(r'[ADE] [ 0-9]+(?:\d \d+:\d+ [AF]\s+)+', line)
                for match in path_groups:
                    status = match[0]
                    paths = re.findall(r' \d+:\d+ [AF]', match)
                    for p in paths:
                        dev, state = p.strip().split(" ")
                        blk = BlockInfo()
                        blk.status = "enabled" if status == 'E' else "active"
                        blk.state = "failed" if state == 'F' else "running"
                        self.dev_multipath_stat[dev] = blk

        def generate(self, dev_name):
            if not self.mpath_generated:
                self._generate_block_mpath_basic_info()
                self.mpath_generated = True
            block = BlockInfo()
            block.dev_name = dev_name
            dev = linux.read_file("/sys/block/%s/dev" % block.dev_name).strip()
            block.status = self.dev_multipath_stat[dev].status if dev in self.dev_multipath_stat else "active"
            block.state = self.dev_multipath_stat[dev].state if dev in self.dev_multipath_stat else \
                linux.read_file("/sys/block/%s/device/state" % block.dev_name).strip()
            report_disk_state_abnormal_if_need(block)
            return block


    metrics = {
        'disk_device_status': GaugeMetricFamily('disk_device_status', 'disk device status', None, ['disk']),
        'disk_device_state': GaugeMetricFamily('disk_device_state', 'disk device state', None, ['disk'])
    }

    def collect_scsi_disk_stat():
        if not os.path.exists("/sys/class/scsi_disk"):
            return
        for disk in os.listdir("/sys/class/scsi_disk"):
            dev_name = os.listdir("/sys/class/scsi_disk/%s/device/block" % disk)
            if not dev_name:
                continue

            dev_name = dev_name[0]
            block = generator.generate(dev_name)
            metrics['disk_device_status'].add_metric([block.dev_name], float(block.convert_status_to_int()))
            metrics['disk_device_state'].add_metric([block.dev_name], float(block.convert_state_to_int()))

    def collect_nvme_disk_stat():
        if not os.path.exists("/sys/class/nvme"):
            return
        for controller in filter(lambda c: os.path.isdir(os.path.join("/sys/class/nvme", c)), os.listdir("/sys/class/nvme")):
            for device in filter(lambda d: d.startswith("nvme"), os.listdir("/sys/class/nvme/%s" % controller)):
                wwid_path = os.path.join("/sys/class/nvme", controller, device, "wwid")
                if not os.path.exists(wwid_path):
                    continue

                block = generator.generate(device)
                metrics['disk_device_status'].add_metric([block.dev_name], float(block.convert_status_to_int()))
                metrics['disk_device_state'].add_metric([block.dev_name], float(block.convert_state_to_int()))

    generator = BlockInfoGenerator()
    collect_scsi_disk_stat()
    collect_nvme_disk_stat()
    return metrics.values()


def add_metrics(metric_name, value, labels, metrics):
    if value is None or value == "":
        return

    if isinstance(value, (int, float)):
        metrics[metric_name].add_metric(labels, float(value))
        return

    if isinstance(value, (str, unicode)) and value.replace('.', '', 1).isdigit():
        metrics[metric_name].add_metric(labels, float(value))
        return

    logger.info("value %s for metric %s labels:%s is not a valid number" % (value, metric_name, ",".join(labels)))


@in_bash
def convert_pci_status_to_int(pci_address):
    r, pci_status = bash_ro("lspci -s %s" % pci_address)
    if r != 0:
        return "no_exist", 2

    if 'rev ff' in pci_status:
        return "critical", 0

    return "nominal", 1


def collect_hba_port_device_state():
    metrics = {'hba_port_state': GaugeMetricFamily('hba_port_state','hba device port state', None, ['port_name'])}

    r, o = bash_ro("systool -c fc_host -v")
    if r != 0:
        return metrics.values()
    port_name = None
    port_state = None
    name = None

    for line in o.strip().split("\n"):
        infos = line.split("=")
        if len(infos) != 2:
            continue
        k = infos[0].lower().strip()
        v = infos[1].strip().strip('"')
        if k == "class device":
            name = v
        if k == "port_name":
            port_name = v
        if k == "port_state":
            port_state = v
        if k == "device path":
            if port_name not in hba_port_state_list_record_map.keys():
                hba_port_state_list_record_map[port_name] = port_state

            if hba_port_state_list_record_map[port_name] != port_state:
                hba_port_state_list_record_map[port_name] = port_state
                send_hba_port_state_abnormal_alarm_to_mn(name, port_name, port_state)

            port_name = None
            port_state = None
            name = None
    return metrics.values()


def has_hy_smi():
    return shell.run_without_log("which hy-smi") == 0

def has_ix_smi():
    return shell.run_without_log("which ixsmi") == 0

def has_nvidia_smi():
    return shell.run_without_log("which nvidia-smi") == 0


def has_rocm_smi():
    if bash_r("lsmod | grep -q amdgpu") != 0:
        if bash_r("modprobe amdgpu") != 0:
            return False
    return shell.run_without_log("which rocm-smi") == 0

def has_npu_smi():
    return shell.run_without_log("which npu-smi") == 0


class ProcessPhysicalMemoryUsageAlarm(object):
    def __init__(self, pid, process_name, mem_usage, **kwargs):
        self.pid = pid
        self.process_name = process_name
        self.memory_usage = mem_usage
        self.additionalProperties = kwargs

    def to_dict(self):
        result = {
            "hostUuid": ALARM_CONFIG.get(kvmagent.HOST_UUID),
            "pid": self.pid,
            "processName": self.process_name,
            "memoryUsage": self.memory_usage,
            "additionalProperties": self.additionalProperties
        }
        return result

    @thread.AsyncThread
    def send_alarm_to_mn(self):
        if ALARM_CONFIG is None:
            logger.warn("Cannot find ALARM_CONFIG")
            return
        url = ALARM_CONFIG.get(kvmagent.SEND_COMMAND_URL)
        if not url:
            logger.warn("Cannot find SEND_COMMAND_URL, unable to transmit alarm info to management node")
            return

        http.json_dump_post(url, self.to_dict(), {'commandpath': '/host/process/physicalMemory/usage/alarm'})


def report_self_abnormal_memory_usage_if_need(usage):
    global kvmagent_physical_memory_usage_alarm_time
    if kvmagent_physical_memory_usage_alarm_time and linux.get_current_timestamp() - kvmagent_physical_memory_usage_alarm_time <= 1800:
        return

    ProcessPhysicalMemoryUsageAlarm(os.getpid(), "zstack-kvmagent", long(usage)).send_alarm_to_mn()
    kvmagent_physical_memory_usage_alarm_time = linux.get_current_timestamp()


def dump_debug_info_if_need():
    global dump_stack_and_objects
    if dump_stack_and_objects:
        debug.dump_debug_info(None, None)
    dump_stack_and_objects = False


def collect_kvmagent_memory_statistics():
    metrics = {
        'kvmagent_used_physical_memory': GaugeMetricFamily('kvmagent_used_physical_memory', 'kvmagent used physical memory', None, ['pid'])
    }

    used_physical_memory = float(psutil.Process().memory_info().rss)
    metrics['kvmagent_used_physical_memory'].add_metric([str(os.getpid())], used_physical_memory)

    if kvmagent.kvmagent_physical_memory_usage_hardlimit:
        if used_physical_memory > kvmagent.kvmagent_physical_memory_usage_hardlimit or \
                used_physical_memory > kvmagent.kvmagent_physical_memory_usage_alarm_threshold:
            logger.warn("kvmagent used physical memory abnormal, used: %s" % used_physical_memory)
            report_self_abnormal_memory_usage_if_need(used_physical_memory)
            dump_debug_info_if_need()

    return metrics.values()


kvmagent.register_prometheus_collector(collect_host_network_statistics)
kvmagent.register_prometheus_collector(collect_host_capacity_statistics)
kvmagent.register_prometheus_collector(collect_vm_statistics)
kvmagent.register_prometheus_collector(collect_vm_pvpanic_enable_in_domain_xml)
kvmagent.register_prometheus_collector(collect_node_disk_wwid)
kvmagent.register_prometheus_collector(collect_host_conntrack_statistics)
kvmagent.register_prometheus_collector(collect_physical_network_interface_state)
kvmagent.register_prometheus_collector(collect_memory_overcommit_statistics)

if misc.isMiniHost():
    kvmagent.register_prometheus_collector(collect_lvm_capacity_statistics)
    kvmagent.register_prometheus_collector(collect_mini_raid_state)
    kvmagent.register_prometheus_collector(collect_equipment_state)

if misc.isHyperConvergedHost():
    kvmagent.register_prometheus_collector(collect_ipmi_state)
else:
    kvmagent.register_prometheus_collector(collect_equipment_state_from_ipmi)

kvmagent.register_prometheus_collector(collect_raid_state)
kvmagent.register_prometheus_collector(collect_ssd_state)
kvmagent.register_prometheus_collector(collect_nvidia_gpu_status)
kvmagent.register_prometheus_collector(collect_amd_gpu_status)
kvmagent.register_prometheus_collector(collect_hy_gpu_status)
kvmagent.register_prometheus_collector(collect_huawei_gpu_status)
kvmagent.register_prometheus_collector(collect_tianshu_gpu_status)
kvmagent.register_prometheus_collector(collect_hba_port_device_state)
kvmagent.register_prometheus_collector(collect_disk_stat)
kvmagent.register_prometheus_collector(collect_kvmagent_memory_statistics)

class SetServiceTypeOnHostNetworkInterfaceRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(SetServiceTypeOnHostNetworkInterfaceRsp, self).__init__()


class PrometheusPlugin(kvmagent.KvmAgent):
    COLLECTD_PATH = "/prometheus/collectdexporter/start"
    SET_SERVICE_TYPE_ON_HOST_NETWORK_INTERFACE = "/host/setservicetype/networkinterface"

    @kvmagent.replyerror
    @in_bash
    def start_prometheus_exporter(self, req):
        @in_bash
        def start_collectd(cmd):
            conf_path = os.path.join(os.path.dirname(cmd.binaryPath), 'collectd.conf')
            ingore_block_device = "/:sd[c-e]/" if kvmagent.host_arch in ["mips64el", "aarch64", "loongarch64"] else "//"

            conf = '''Interval {{INTERVAL}}
# version {{VERSION}}
FQDNLookup false

LoadPlugin syslog
LoadPlugin aggregation
LoadPlugin cpu
LoadPlugin disk
LoadPlugin interface
LoadPlugin memory
LoadPlugin network
LoadPlugin virt

<Plugin aggregation>
	<Aggregation>
		#Host "unspecified"
		Plugin "cpu"
		#PluginInstance "unspecified"
		Type "cpu"
		#TypeInstance "unspecified"

		GroupBy "Host"
		GroupBy "TypeInstance"

		CalculateNum false
		CalculateSum false
		CalculateAverage true
		CalculateMinimum false
		CalculateMaximum false
		CalculateStddev false
	</Aggregation>
</Plugin>

<Plugin cpu>
  ReportByCpu true
  ReportByState true
  ValuesPercentage true
</Plugin>

<Plugin disk>
  Disk "/^sd[a-z]{1,2}$/"
  Disk "/^hd[a-z]{1,2}$/"
  Disk "/^vd[a-z]{1,2}$/"
  Disk "/^nvme[0-9][a-z][0-9]$/"
  IgnoreSelected false
</Plugin>

<Plugin "interface">
{% for i in INTERFACES -%}
  Interface "{{i}}"
{% endfor -%}
  IgnoreSelected false
</Plugin>

<Plugin memory>
	ValuesAbsolute true
	ValuesPercentage false
</Plugin>

<Plugin virt>
	Connection "qemu:///system"
	RefreshInterval {{INTERVAL}}
	HostnameFormat name
    PluginInstanceFormat name
    BlockDevice "/:hd[c-e]/"
    BlockDevice "{{IGNORE}}"
    IgnoreSelected true
    ExtraStats "vcpu memory"
</Plugin>

<Plugin network>
	Server "localhost" "25826"
</Plugin>

'''

            tmpt = Template(conf)
            conf = tmpt.render({
                'INTERVAL': cmd.interval,
                'INTERFACES': interfaces,
                'VERSION': cmd.version,
                'IGNORE': ingore_block_device
            })

            need_restart_collectd = False
            if os.path.exists(conf_path):
                with open(conf_path, 'r') as fd:
                    old_conf = fd.read()

                if old_conf != conf:
                    with open(conf_path, 'w') as fd:
                        fd.write(conf)
                    need_restart_collectd = True
            else:
                with open(conf_path, 'w') as fd:
                    fd.write(conf)
                need_restart_collectd = True

            mpidList = linux.find_process_list_by_command('collectdmon', [conf_path])
            cpidList = linux.find_process_list_by_command('collectd', [conf_path])
            logger.info("need_restart_collectd: %s, mpidList: %s, cpidList: %s" % (need_restart_collectd, mpidList, cpidList))

            if need_restart_collectd:
                for pid in mpidList:
                    bash_errorout('kill -TERM %s' % pid)
                for pid in cpidList:
                    bash_errorout('kill -TERM %s' % pid)
                bash_errorout('collectdmon -- -C %s' % conf_path)
            elif mpidList and len(mpidList) > 1:
                for pid in mpidList[1:]:
                    bash_errorout('kill -TERM %s' % pid)
                for pid in cpidList:
                    bash_errorout('kill -TERM %s' % pid)
            elif len(mpidList) == 0:
                for pid in cpidList:
                    bash_errorout('kill -TERM %s' % pid)
                bash_errorout('collectdmon -- -C %s' % conf_path)

        def run_in_systemd(binPath, args, log):
            def get_env_config(path):
                keywords = ["node_exporter", "process_exporter", "zstack_service_exporter"]
                if any(keyword in path for keyword in keywords):
                    return "GOMAXPROCS=1"
                else:
                    return ""

            def get_systemd_name(path):
                exporter_names = [
                    "collectd_exporter",
                    "node_exporter",
                    "pushgateway",
                    "process_exporter",
                    "zstack_service_exporter",
                    "ipmi_exporter"
                ]
                for name in exporter_names:
                    if name in path:
                        return name
                return None

            def reload_and_restart_service(service_name):
                bash_errorout("systemctl daemon-reload && systemctl restart %s.service" % service_name)

            service_env_config = get_env_config(binPath)
            service_name = get_systemd_name(binPath)
            if not service_name:
                logger.warn("cannot get service name from binPath: %s" % binPath)
                return

            service_path = '/etc/systemd/system/%s.service' % service_name
            memory_limit_config = ""
            if service_name == "ipmi_exporter":
                memory_limit_config = "MemoryLimit=64M"
            elif service_name == "process_exporter":
                memory_limit_config = "MemoryLimit=1G"
            elif service_name == "zstack_service_exporter":
                memory_limit_config = "MemoryLimit=1G"

            service_conf = '''
[Unit]
Description=prometheus %s
After=network.target

[Service]
Environment="%s"
ExecStart=/bin/sh -c '%s %s > %s 2>&1'
ExecStop=/bin/sh -c 'pkill -TERM -f %s'

%s
Restart=always
RestartSec=30s
[Install]
WantedBy=multi-user.target
''' % (service_name, service_env_config, binPath, args, '/dev/null' if log.endswith('/pushgateway.log') else log, binPath, memory_limit_config)

            if not os.path.exists(service_path):
                linux.write_file(service_path, service_conf, True)
                os.chmod(service_path, 0o644)
                reload_and_restart_service(service_name)
                return

            if linux.read_file(service_path) != service_conf:
                linux.write_file(service_path, service_conf, True)
                logger.info("%s.service conf changed" % service_name)

            os.chmod(service_path, 0o644)
            # restart service regardless of conf changes, for ZSTAC-23539
            reload_and_restart_service(service_name)

        @lock.file_lock("/run/collectd-conf.lock", locker=lock.Flock())
        def start_collectd_exporter(cmd):
            start_collectd(cmd)
            start_exporter(cmd)

        @in_bash
        def start_exporter(cmd):
            EXPORTER_PATH = cmd.binaryPath
            LOG_FILE = os.path.join(os.path.dirname(EXPORTER_PATH), cmd.binaryPath + '.log')
            ARGUMENTS = cmd.startupArguments
            if not ARGUMENTS:
                ARGUMENTS = ""
            os.chmod(EXPORTER_PATH, 0o755)
            run_in_systemd(EXPORTER_PATH, ARGUMENTS, LOG_FILE)

        def start_custom_exporter(cmd, config_filename, config_option):
            EXPORTER_PATH = cmd.binaryPath
            if not os.path.exists(EXPORTER_PATH):
                logger.info("binaryPath %s not found." % EXPORTER_PATH)
                return

            LOG_FILE = os.path.join(os.path.dirname(EXPORTER_PATH), os.path.basename(cmd.binaryPath) + '.log')
            conf_path = os.path.join(os.path.dirname(EXPORTER_PATH), config_filename)

            try:
                with open(conf_path, 'w') as file:
                    file.write(cmd.configYaml)
                logger.info("config file %s writing completed." % conf_path)
            except Exception as e:
                logger.warn("an error occurred while writing to the file: %s" % e)
                return

            run_in_systemd(EXPORTER_PATH, "%s=%s" % (config_option, conf_path), LOG_FILE)

        def check_if_mn_node_and_start_exporter(cmd, config_file, config_option):
            if linux.find_process_by_cmdline('appName=zstack'):
                logger.info("%s is already running on mn. skipping startup on compute node." % cmd.binaryPath)
                return
            start_custom_exporter(cmd, config_file, config_option)

        @in_bash
        def start_zs_exporter(cmd):
            check_if_mn_node_and_start_exporter(cmd, "zs_host_exporter_config.yaml", "-config.file")

        @in_bash
        def start_process_exporter(cmd):
            check_if_mn_node_and_start_exporter(cmd, "process_exporter_config.yaml", "-config.path")

        @in_bash
        def start_ipmi_exporter(cmd):
            bash_errorout(
                "modprobe ipmi_msghandler; modprobe ipmi_devintf; modprobe ipmi_poweroff; modprobe ipmi_si; modprobe ipmi_watchdog")
            EXPORTER_PATH = cmd.binaryPath
            LOG_FILE = os.path.join(os.path.dirname(EXPORTER_PATH), cmd.binaryPath + '.log')
            ARGUMENTS = cmd.startupArguments

            conf_path = os.path.join(os.path.dirname(EXPORTER_PATH), 'ipmi.yml')

            conf = '''
# Configuration file for ipmi_exporter
modules:
  default:
    collectors:
      - bmc
      - ipmi
      - dcmi
      - chassis
    exclude_sensor_ids:
      - 2
      - 29
      - 32'''

            if not os.path.exists(conf_path) or open(conf_path, 'r').read() != conf:
                with open(conf_path, 'w') as fd:
                    fd.write(conf)

            os.chmod(EXPORTER_PATH, 0o755)
            if shell.run("pgrep %s" % EXPORTER_PATH) == 0:
                bash_errorout("pkill -TERM -f %s" % EXPORTER_PATH)
            if os.path.exists("/etc/systemd/system/None.service"):
                os.remove("/etc/systemd/system/None.service")
            run_in_systemd(EXPORTER_PATH, ARGUMENTS, LOG_FILE)

        para = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = kvmagent.AgentResponse()

        eths = os.listdir("/sys/class/net")
        interfaces = []
        for eth in eths:
            if eth in ['lo', 'bonding_masters']:
                continue
            elif eth.startswith(('br_', 'vnic', 'docker', 'gre', 'erspan', 'outer', 'ud_')):
                continue
            elif not eth:
                continue
            else:
                interfaces.append(eth)

        for cmd in para.cmds:
            if "collectd_exporter" in cmd.binaryPath:
                start_collectd_exporter(cmd)
            elif "ipmi_exporter" in cmd.binaryPath:
                if not is_virtual_machine():
                    start_ipmi_exporter(cmd)
                else:
                    logger.info("Current environment is a virtualized environment, skipping ipmi_exporter startup")
                    continue
            elif "process_exporter" in cmd.binaryPath:
                start_process_exporter(cmd)
            elif "zstack_service_exporter" in cmd.binaryPath:
                start_zs_exporter(cmd)
            else:
                start_exporter(cmd)

        return jsonobject.dumps(rsp)

    def install_colletor(self):
        class Collector(object):
            __collector_cache = {}

            @classmethod
            def __get_cache__(cls):
                # type: () -> list
                keys = cls.__collector_cache.keys()
                if keys is None or len(keys) == 0:
                    return None
                if (time.time() - keys[0]) < 9:
                    return cls.__collector_cache.get(keys[0])
                return None

            @classmethod
            def __store_cache__(cls, collectStartTime, ret):
                # type: (list) -> None
                cls.__collector_cache.clear()
                cls.__collector_cache.update({collectStartTime: ret})

            @classmethod
            def check(cls, v):
                try:
                    if v is None:
                        return False
                    if isinstance(v, GaugeMetricFamily):
                        return Collector.check(v.samples)
                    if isinstance(v, list) or isinstance(v, tuple):
                        for vl in v:
                            if Collector.check(vl) is False:
                                return False
                    if isinstance(v, dict):
                        for vk in v.iterkeys():
                            if vk == "timestamp" or vk == "exemplar":
                                continue
                            if Collector.check(v[vk]) is False:
                                return False
                except Exception as e:
                    logger.warn("got exception in check value %s: %s" % (v, e))
                    return True
                return True

            def collect(self):
                global latest_collect_result
                ret = []

                def get_result_run(f, fname):
                    # type: (typing.Callable, str) -> None
                    global collectResultLock
                    global latest_collect_result

                    r = f()
                    if not Collector.check(r):
                        logger.warn(
                            "result from collector %s contains illegal character None, details: \n%s" % (fname, r))
                        return
                    with collectResultLock:
                        latest_collect_result[fname] = r

                collectStartTime = time.time()
                cache = Collector.__get_cache__()
                if cache is not None:
                    return cache

                for c in kvmagent.metric_collectors:
                    name = "%s.%s" % (c.__module__, c.__name__)
                    if collector_dict.get(name) is not None and collector_dict.get(name).is_alive():
                        continue
                    collector_dict[name] = thread.ThreadFacade.run_in_thread(get_result_run, (c, name,))

                for i in range(7):
                    for t in collector_dict.values():
                        if t.is_alive():
                            time.sleep(0.5)
                            break

                for k in collector_dict.iterkeys():
                    if collector_dict[k].is_alive():
                        logger.warn("It seems that the collector [%s] has not been completed yet,"
                                    " temporarily use the last calculation result." % k)

                for v in latest_collect_result.itervalues():
                    ret.extend(v)
                Collector.__store_cache__(collectStartTime, ret)
                return ret

        REGISTRY.register(Collector())

    @thread.AsyncThread
    def start_async_data_collectors(self):
        while True:
            self.collect_domain_maximum_memory()
            time.sleep(300)

    def collect_domain_maximum_memory(self):
        o = bash_o('virsh domstats --list-running --balloon')
        if not o:
            return

        # Domain: '8e5c8fb20a8a4276b6c17267105e7710'
        #   balloon.current=1048576
        #   balloon.maximum=1048576
        #   balloon.swap_in=0
        #   balloon.swap_out=0
        #   balloon.major_fault=336
        #   balloon.minor_fault=3514274
        #   balloon.unused=793852
        #   balloon.available=1017068
        #   balloon.last-update=1690513108
        #   balloon.rss=411420
        #
        # Domain: '3f512fc8c3e5430bbfddb45db5485f11'
        #   balloon.current=1048576
        #   balloon.maximum=1048576
        #   balloon.swap_in=0
        #   balloon.swap_out=0
        #   balloon.major_fault=336
        #   balloon.minor_fault=3511963
        #   balloon.unused=793576
        #   balloon.available=1017068
        #   balloon.last-update=1690513112
        #   balloon.rss=412900

        # collect balloon.maximum and domain name
        with asyncDataCollectorLock:
            domain_max_memory.clear()
            for line in o.splitlines():
                if line.startswith("Domain:"):
                    domain = line.split("'")[1]
                elif line.startswith("  balloon.maximum="):
                    if domain is None:
                        logger.warn("can not get domain name, skip this domain")
                        continue

                    domain_max_memory[domain] = line.split("=")[1]
                    domain = None

    def init_global_config(self):
        global PAGE_SIZE
        output = bash_o("getconf PAGESIZE")
        if output == "" or output is None:
            PAGE_SIZE = 4096
        else:
            PAGE_SIZE = int(output)

    @kvmagent.replyerror
    def set_service_type_on_host_network_interface(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = SetServiceTypeOnHostNetworkInterfaceRsp()
        rsp.success = False

        dev_name = cmd.interfaceName
        if cmd.vlanId is not None and cmd.vlanId is not 0:
            dev_name = '%s.%s' % (cmd.interfaceName, cmd.vlanId)

        register_service_type(dev_name, cmd.serviceType)
        rsp.success = True

        return jsonobject.dumps(rsp)

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.COLLECTD_PATH, self.start_prometheus_exporter)
        http_server.register_async_uri(self.SET_SERVICE_TYPE_ON_HOST_NETWORK_INTERFACE,
                                       self.set_service_type_on_host_network_interface)

        self.init_global_config()
        self.install_colletor()
        self.start_async_data_collectors()
        start_http_server(7069)

    def stop(self):
        pass

    def configure(self, config):
        global ALARM_CONFIG
        ALARM_CONFIG = config
