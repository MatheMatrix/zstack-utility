import threading
import re

from zstacklib.utils import thread
from zstacklib.utils.bash import *
from enum import Enum
import json

from zstacklib.utils.pci import VendorEnum
from zstacklib.utils.qga import VmQga

logger = log.get_logger(__name__)


class VmGpuStatus(Enum):
    NOT_EXIST = "not_exist"
    CRITICAL_FAULT = "critical"
    NOMINAL = "nominal"


def shut_persistenced_by_guesttool(domain):
    vm_uuid = domain.name()
    qga = VmQga(domain)
    if qga.state != VmQga.QGA_STATE_RUNNING:
        return 0, "skip shuting down nvidia-persistenced, qga is not running for vm {}".format(vm_uuid)

    cmd = get_shut_nvidia_persistence_cmd("mswindows" in qga.os)
    if qga.os == "mswindows":
        exitcode, ret_data = qga.guest_exec_powershell(cmd)
    else:
        exitcode, ret_data, _ = qga.guest_exec_bash(cmd)
    return exitcode, ret_data


def nvidia_pre_detach_from_vm(domain, vm_uuid):
    """NVIDIA specific pre-detach-from-VM hook"""
    if not domain or not domain.isActive():
        logger.info(
            "no need to shutdown nvidia-persistenced for vm %s, it is not running" % vm_uuid)
        return 0, None
    else:
        logger.info("start to shutdown nvidia-persistenced for vm %s" % vm_uuid)
        return shut_persistenced_by_guesttool(domain)


def nvidia_pre_detach_from_host():
    """NVIDIA specific pre-detach-from-host hook"""
    logger.info("start to shutdown nvidia-persistenced on host")
    r, o, _ = bash_roe(get_shut_nvidia_persistence_cmd())
    return r, o


_pre_detach_from_vm_hooks = {
    VendorEnum.NVIDIA: nvidia_pre_detach_from_vm
}

_pre_detach_from_host_hooks = {
    VendorEnum.NVIDIA: nvidia_pre_detach_from_host
}


def pre_detach_from_vm(domain, vm_uuid, vendor):
    """Execute pre-detach-from-VM hook for specific vendor"""
    if vendor in _pre_detach_from_vm_hooks:
        return _pre_detach_from_vm_hooks[vendor](domain, vm_uuid)
    logger.warn(
        "No hook registered for vendor: {0}, do nothing".format(vendor))
    return 0, None


# def pre_detach_from_host(vendor):
#     """Execute pre-detach-from-host hook for specific vendor"""
#     if vendor in _pre_detach_from_host_hooks:
#         return _pre_detach_from_host_hooks[vendor]()
#     logger.warn("No hook registered for vendor: {0}, do nothing".format(vendor))
#     return 0, None


def extract_and_clean_json(smi_output):
    start_idx = smi_output.find('{')
    end_idx = smi_output.rfind('}')

    if start_idx == -1 or end_idx == -1:
        logger.info("No JSON brackets found in SMI output")
        return None

    if start_idx >= end_idx:
        logger.info("Invalid JSON bracket order in SMI output")
        return None

    json_str = (
        smi_output[start_idx:end_idx + 1]
        .strip()
        .replace(', ,', ',')
        .replace(',,', ',')
        .replace(', }', '}')
        .replace(', ]', ']')
    )
    return json_str


def parse_nvidia_gpu_output(output):
    gpuinfos = []
    for part in output.split('\n'):
        if len(part.strip()) == 0:
            continue
        infos = part.split(',')
        gpuinfo = {}
        pci_device_address = infos[0].strip().lower()
        if len(pci_device_address.split(':')[0]) == 8:
            pci_device_address = pci_device_address[4:].lower()
        gpuinfo["pciAddress"] = pci_device_address
        gpuinfo["memory"] = infos[1].strip()
        gpuinfo["power"] = infos[2].strip()
        gpuinfo["serialNumber"] = infos[3].strip()
        gpuinfos.append(gpuinfo)
    return gpuinfos


def parse_amd_gpu_output(output):
    gpuinfos = []
    try:
        gpu_info_json = json.loads(extract_and_clean_json(output))
        if gpu_info_json is None:
            return gpuinfos

        for card_name, card_data in gpu_info_json.items():
            gpuinfo = {}
            pci_device_address = card_data.get('PCI Bus').lower()
            if len(pci_device_address.split(':')[0]) == 8:
                pci_device_address = pci_device_address[4:].lower()

            gpuinfo["pciAddress"] = pci_device_address
            gpuinfo["memory"] = card_data.get('VRAM Total Memory (B)')
            gpuinfo["power"] = card_data.get('Average Graphics Package Power (W)',
                                             card_data.get('Current Socket Graphics Package Power (W)', None))
            gpuinfo["serialNumber"] = card_data.get('Serial Number')
            gpuinfos.append(gpuinfo)
    except Exception as e:
        logger.error("amd query gpu is error, %s " % e)

    return gpuinfos


def parse_hy_gpu_output(output):
    gpuinfos = []
    try:
        gpu_info_json = json.loads(extract_and_clean_json(output))
        if gpu_info_json is None:
            return gpuinfos

        for card_name, card_data in gpu_info_json.items():
            gpuinfo = {}
            pci_device_address = card_data['PCI Bus'].lower()
            if len(pci_device_address.split(':')[0]) == 8:
                pci_device_address = pci_device_address[4:].lower()

            gpuinfo["pciAddress"] = pci_device_address
            gpuinfo["memory"] = card_data['Available memory size (MiB)'] + \
                " MiB"
            gpuinfo["power"] = card_data['Max Graphics Package Power (W)']
            gpuinfo["serialNumber"] = card_data['Serial Number']
            gpuinfos.append(gpuinfo)
    except Exception as e:
        logger.error("haiguang query gpu is error, %s " % e)

    return gpuinfos


def get_huawei_npu_id(npu_id_output):
    npu_ids = []
    for line in npu_id_output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "NPU ID" in line:
            npu_ids.append(line.split(":")[1].strip())
    return npu_ids


def parse_huawei_gpu_output_by_npu_id(output):
    gpuinfos = []
    gpuinfo = {}
    total_memory = 0
    total_ddr_memory = 0
    found_total_memory = False
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Serial Number" in line:
            gpuinfo["serialNumber"] = line.split(":")[1].strip()
        elif "PCIe Bus Info" in line:
            gpuinfo["pciAddress"] = line.partition(": ")[-1].strip().lower()
        elif line.startswith("Total DDR Capacity(MB)"):
            memory_value = int(line.split(":")[1].strip().split()[0])
            total_ddr_memory += memory_value
            found_total_memory = True
        elif (line.startswith("DDR Capacity(MB)") or line.startswith("HBM Capacity")) and not found_total_memory:
            memory_value = int(line.split(":")[1].strip().split()[0])
            total_memory += memory_value
        elif "Power Dissipation" in line or "Real-time Power(W)" in line:
            gpuinfo["power"] = line.split(":")[1].strip()

    total_memory = total_ddr_memory if found_total_memory else total_memory

    if total_memory > 0:
        gpuinfo["memory"] = "%s MB" % total_memory

    gpuinfos.append(gpuinfo)
    return gpuinfos


def get_huawei_product_type(output):
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Product Type" in line:
            return line.split(":")[1].strip()
    return None


def parse_tianshu_gpu_output(output):
    gpuinfos = []
    for part in output.split('\n'):
        if len(part.strip()) == 0:
            continue
        infos = part.split(',')
        gpuinfo = {}
        pci_device_address = infos[0].strip()
        if len(pci_device_address.split(':')[0]) == 8:
            pci_device_address = pci_device_address[4:].lower()

        gpuinfo["pciAddress"] = pci_device_address
        gpuinfo["memory"] = infos[1].strip()
        gpuinfo["power"] = infos[2].strip()
        gpuinfo["serialNumber"] = infos[3].strip()
        gpuinfos.append(gpuinfo)

    return gpuinfos


def parse_enflame_gpu_output(output):
    """
    ...
    old version driver:

    DEV ID 7
        Driver Info
            Ver                     : 1.2.4.12
        Device Info
            Dev Name                : S60
            Dev UUID                : TR1V57100501
            Dev SN                  : C0AAD40510049
            Dev PN                  : EFB-0088000-00
            Dev MFD                 : 2024-10-13
            Health                  : True
        PCIe Info
            Vendor ID               : 1e36
            Device ID               : c035
            Domain                  : 0000
            Bus                     : b1
            Dev                     : 00
            Func                    : 0
            Link Info
            Max Link Speed          : Gen5
            Max Link Width          : X16
            Cur Link Speed          : Gen5
            Cur Link Width          : X16
            Tx Throughput           : 0 MiB/s
            Rx Throughput           : 0 MiB/s
        Clock Info
            Mem CLK                 : 7000 MHz
        Power Info
            Power Capa              : 300 W
            Cur Power               : 102 W
            Dpm Level               : Sleep
        Device Mem Info
            Mem Size                : 42976 MiB
            Mem Usage               : 1129 MiB
            Mem Ecc                 : enable
        Temperature Info
            GCU Temp                : 41 C
        Voltage Info
            VDD GCU                 : 0.702 V
            VDD SOC                 : 0.743 V
            VDD MEMQC               : 1.349 V
        Device Usage Info
            GCU Usage               : 0.0 %
        ECC Mode
            Current                 : Enable
            Pending                 : Enable
        RMA Info
            Flags                   : False
            DBE                     : 0
        Power Cable
            Status                  : Normal
        VPU Info
            Encoder Usage           : 0 %
            Decoder Usage           : 0 %

    new version driver:
        DEV ID 0
        Driver Info
            Ver                     : 1.4.3.4
        Device Info
            Dev Name                : S60
            Dev UUID                : TPUH74190604
            Dev SN                  : C0AA640520685
            Dev PN                  : EFB-0088000-00
            Dev MFD                 : 2024-10-6
            Health                  : True
        PCIe Info
            Vendor ID               : 1e36
            Device ID               : c035
            Domain                  : 0000
            Bus                     : 00
            Dev                     : 0c
            Func                    : 0
            Link Info
            Max Link Speed          : Gen5
            Max Link Width          : X16
            Cur Link Speed          : Gen5
            Cur Link Width          : X16
            Tx Throughput           : 0 MiB/s
            Rx Throughput           : 0 MiB/s
        Clock Info
            Mem CLK                 : 7000 MHz
        Power Info
            Power Capa              : 300 W
            Cur Power               : 104 W
            Dpm Level               : Sleep
        Device Mem Info
            Total Size              : 42976 MiB
            Reserved Size           : 1129 MiB
            Used Size               : 0 MiB
            Free Size               : 41846 MiB
        Temperature Info
            GCU Temp                : 45 ('C Celsius sign, utf-8 char, not log here)
        Voltage Info
            VDD GCU                 : 0.7 V
            VDD SOC                 : 0.743 V
            VDD MEMQC               : 1.347 V
        Device Usage Info
            GCU Usage               : 0.0 %
        ECC Mode
            Current                 : Enable
            Pending                 : Enable
        RMA Info
            Flags                   : False
            Total DBE               : 0
                MC0 DBE             : 0
                MC1 DBE             : 0
                MC2 DBE             : 0
                MC3 DBE             : 0
                MC4 DBE             : 0
                MC5 DBE             : 0
                MC6 DBE             : 0
                MC7 DBE             : 0
                MC8 DBE             : 0
                MC9 DBE             : 0
                MC10 DBE            : 0
                MC11 DBE            : 0
        Power Cable
            Status                  : Normal
        VPU Info
            Encoder Usage           : 0 %
            Decoder Usage           : 0 %
        Error Records
            Total Error Count       : 0
            Reset Count             : 0
            Last Reset Date         : N/A
        Error Details
            User Triggered Reset    : 0
            Internal Error          : 0
            SIP Error               : 0
            Bus Error               : 0
            FW Error                : 0
            DTE Error               : 0
            DRAM HBM Error          : 0
            PCIE Error              : 0
            Unknown Error           : 0
    ...
    """
    gpu_infos = []

    for dev in output.split("DEV ID")[1:]:
        gpuinfo = {}
        domain = bus = dev_id = func = None

        for line in dev.strip().splitlines():
            line = line.strip()
            if ':' in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
            else:
                key = line
                value = ''

            if key == "Domain":
                domain = value.zfill(4)
            elif key == "Bus":
                bus = value.zfill(2)
            elif key == "Dev":
                dev_id = value.zfill(2)
            elif key == "Func":
                func = value
            elif key == "Mem Size" or key == "Total Size":
                gpuinfo["memory"] = value
            elif key == "Mem Usage" or key == "Used Size":
                gpuinfo["memoryUsage"] = value
            elif key == "Cur Power":
                gpuinfo["power"] = value
            elif key == "Power Capa":
                gpuinfo["powerCap"] = value
            elif key == "Dpm Level":
                gpuinfo["dpmLevel"] = value
            elif key == "GCU Temp":
                gpuinfo["temperature"] = value
            elif key == "GCU Usage":
                gpuinfo["gcuUsage"] = value
            elif key == "Dev SN":
                gpuinfo["serialNumber"] = value
            elif key == "Tx Throughput":
                gpuinfo["txThroughput"] = value
            elif key == "Rx Throughput":
                gpuinfo["rxThroughput"] = value

        if domain and bus and dev_id and func:
            gpuinfo["pciAddress"] = "{}:{}:{}.{}".format(
                domain, bus, dev_id, func)
            gpu_infos.append(gpuinfo)

    return gpu_infos


def get_tianshu_product_name(output):
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Product Name" in line:
            return line.split(":")[1].strip()
    return None


def get_nvidia_gpu_basic_info_cmd(iswindows=False):
    cmd = "nvidia-smi --query-gpu=gpu_bus_id,memory.total,power.limit,gpu_serial --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_amd_gpu_basic_info_cmd(iswindows=False):
    cmd = "rocm-smi --showbus --showmeminfo vram --showpower --showserial --json"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_hy_gpu_basic_info_cmd(iswindows=False):
    cmd = "hy-smi --showserial --showmaxpower --showmemavailable --showbus --json"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def is_tianshu_v1(iswindows=False):
    cmd = "ixsmi --query-gpu=fan.speed --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_tianshu_gpu_basic_info_cmd_v1(iswindows=False):
    cmd = "ixsmi --query-gpu=gpu_bus_id,memory.total,gpu.power.limit,gpu_serial --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_tianshu_gpu_basic_info_cmd_v2(iswindows=False):
    cmd = "ixsmi --query-gpu=gpu_bus_id,memory.total,power.limit,gpu_serial --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_tianshu_gpu_metric_info_cmd_v1(iswindows=False):
    cmd = "ixsmi --query-gpu=gpu.power.draw,temperature.gpu,utilization.gpu,utilization.memory,index,gpu_bus_id," \
          "gpu_serial,fan.speed  --format=csv,noheader,nounits"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_tianshu_gpu_metric_info_cmd_v2(iswindows=False):
    cmd = "ixsmi --query-gpu=power.draw,temperature.gpu,utilization.gpu,utilization.memory,index,gpu_bus_id," \
          "gpu_serial --format=csv,noheader,nounits"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_tianshu_gpu_product_name_cmd(iswindows=False):
    cmd = "ixsmi -q |grep 'Product Name'"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_huawei_gpu_npu_id_cmd():
    return "npu-smi info -l"


def get_huawei_gpu_basic_info_cmd(npu_id, iswindows=False):
    cmd = "npu-smi info -t board -i {0};npu-smi info -i {0} -t memory;npu-smi info -t power -i {0}".format(
        npu_id)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_huawei_gpu_product_name_cmd(npu_id, iswindows=False):
    cmd = "npu-smi info -t product -i {0}".format(npu_id)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_huawei_gpu_aios_rank_table_dict(npu_ids, iswindows=False):
    for npu_id in npu_ids:
        if not npu_id.isdigit():
            raise ValueError("NPU ID must be a digit, got: {}".format(npu_id))

    # Build the command to get IP addresses for each NPU ID using hccn_tool
    device_ips = {}
    device_netmasks = {}
    for npu_id in npu_ids:
        # output example:
        # hccn_tool -i 6 -ip -g
        # ipaddr:172.20.9.77
        # netmask:255.255.0.0
        r, o, e = bash_roe("hccn_tool -i %s -ip -g" % npu_id)

        ip = None
        netmask = None
        if r == 0 and o:
            # Try to match "ipaddr:172.20.9.71" pattern
            import re
            ip_match = re.search(r'ipaddr:(\d+\.\d+\.\d+\.\d+)', o)
            if ip_match:
                ip = ip_match.group(1)
            else:
                # Try alternate pattern "IP: 10.20.0.2"
                ip_match_alt = re.search(r'IP:\s+(\d+\.\d+\.\d+\.\d+)', o)
                if ip_match_alt:
                    ip = ip_match_alt.group(1)

            netmask_match = re.search(r'netmask:(\d+\.\d+\.\d+\.\d+)', o)
            if netmask_match:
                netmask = netmask_match.group(1)
            else:
                netmask_match_alt = re.search(
                    r'Netmask:\s+(\d+\.\d+\.\d+\.\d+)', o)
                if netmask_match_alt:
                    netmask = netmask_match_alt.group(1)

        # Use fallback IP if no IP found
        if not ip:
            logger.warning(
                "Could not retrieve IP for NPU ID %s, using default format" % npu_id)
            ip = "10.20.0.%s" % (int(npu_id) + 2)
        if not netmask:
            logger.warning(
                "Could not retrieve netmask for NPU ID %s, using default" % npu_id)
            netmask = "255.255.0.0"

        device_ips[npu_id] = ip
        device_netmasks[npu_id] = netmask

    # Build rank table dictionary
    rank_table = {
        "server_count": len(npu_ids),
        "server_list": []
    }

    for _, npu_id in enumerate(npu_ids):
        server_info = {
            "device_id": npu_id,
            "host": device_ips[npu_id],
            "device_ip": device_ips[npu_id],
            "netmask": device_netmasks[npu_id]
        }
        rank_table["server_list"].append(server_info)

    return rank_table


def check_huawei_npu_is_isolated(npu_id, all_npu_ids, iswindows=False):
    """
    Check whether a Huawei NPU is isolated using `npu-smi info -t hccs`.
    Return True when health status is not OK. Do not inspect lane majority.
    """
    if not npu_id or not all_npu_ids or len(all_npu_ids) <= 1:
        return False

    try:
        r, _, _ = bash_roe("which npu-smi")
        if r != 0:
            logger.debug("npu-smi not found, cannot check isolation status")
            return False

        cmd = "npu-smi info -t hccs -i {0} -c 0".format(npu_id)
        if iswindows:
            cmd = cmd.replace(" ", "|")

        r, o, e = bash_roe(cmd)
        if r != 0 or not o:
            logger.warning("failed to run '%s' for NPU %s: %s" %
                           (cmd, npu_id, e))
            return False

        for line in o.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("hccs health status"):
                parts = line.split(":", 1)
                status = parts[1].strip().upper() if len(parts) > 1 else ""
                if status != "OK":
                    logger.debug(
                        "NPU %s health status is %s, treating as isolated" % (npu_id, status))
                    return True
                return False

        logger.debug(
            "NPU %s health status not found in output, treating as not isolated" % npu_id)
        return False

    except Exception as ex:
        logger.warning("failed to check NPU %s isolation status: %s" %
                       (npu_id, str(ex)))
        return False


def is_valid_video_controller(device):
    invalid_keywords = {"iBMC"}
    return all(keyword not in device for keyword in invalid_keywords)


def is_valid_co_processor(vendor):
    return vendor in [VendorEnum.HAIGUANG]


def is_valid_communication_controller(vendor):
    return vendor in [VendorEnum.KUNLUNXIN]


# get_vastai_type() has been moved to zstacklib.gpu.vendors.vastai.Vastai.get_vastai_type()


def is_valid_processing_accelerator(device):
    valid_keywords = {"Device", "SV100", "MI308X", "S60"}
    return any(keyword in device for keyword in valid_keywords)


def get_enflame_gpu_info_cmd():
    return "efsmi -q"


def post_process_enflame_gpu_device(to):
    to.virtStatus = "UNVIRTUALIZABLE"


def get_kunlunxin_gpu_xpu_id_cmd():
    return "xpu-smi -L"


def get_kunlunxin_xpu_id(xpu_id_output):
    xpu_ids = []
    for line in xpu_id_output.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^XPU\s+(\d+):', line)
        if match:
            xpu_ids.append(match.group(1))
    return xpu_ids


def get_kunlunxin_gpu_basic_info_cmd(xpu_id, iswindows=False):
    cmd = "xpu-smi -q --id={0}".format(xpu_id)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def parse_kunlunxin_gpu_output_by_npu_id(output):
    """
    Timestamp                                 : Sun Nov 30 10:46:37 2025
    Driver Version                            : 5.0.21.26
    XPU-RT Version                            : 10.2

    Attached XPUs                             : 1
    XPU 00000000:21:00.0
    Product Name                          : P800 PCIe
    Product Brand                         : KUNLUNXIN
    Product Architecture                  : KL3
    Serial Number                         : 02K0MA0258D0007R
    XPU UUID                              : GPU-8412bfa1-c3b9-50e6-86b5-065b83a1537c
    Minor Number                          : 0
    PCIe Id                               : 3
    XPU Part Number                       : B00100300110211
    Firmware Version
        PBL Version                       : 1.0
        PCIE Version                      : 2.14
        SBL Version                       : 1.54
        ALL Version                       : 1.0.2.14.1.54
        CPLD Version                      : 2.0
    PCI
        Bus                               : 0x21
        Device                            : 0x00
        Function                          : 0x0
        Domain                            : 0x0000
        Device Id                         : 0x36862057
        Bus Id                            : 00000000:21:00.0
        Sub System Id                     : 0x00010001
        XPU Link Info
            PCIe Generation
                Max                       : 4
                Current                   : 3
            Link Width
                Max                       : 16x
                Current                   : 16x
    Memory Usage
        Total                             : 98304 MiB
        Reserved                          : 0 MiB
        Used                              : 0 MiB
        Free                              : 98304 MiB
    L3 Usage
        Total                             : 96 MiB
        Reserved                          : 0 MiB
        Used                              : 0 MiB
        Free                              : 96 MiB
    Utilization
        Xpu                               : 0 %
    Ecc Mode
        Current                           : Enabled
        Pending                           : Enabled
    ECC Errors
        Volatile
            DRAM Correctable              : 0
            DRAM Uncorrectable            : 0
        Aggregate
            DRAM Correctable              : 0
            DRAM Uncorrectable            : 0
    Temperature
        XPU Current Temp                  : 40 C
    Power Readings
        Enforced Power Limit              : 350.00 W
        Power Draw                        : 75.00 W
    Clocks
        Cluster                           : 1450 MHz
        CDNN                               : 1450 MHz
    Processes                             : None
    """
    gpuinfos = []
    gpuinfo = {}
    current_section = None
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            current_section = line
            continue

        if "Serial Number" in line:
            gpuinfo["serialNumber"] = line.split(":")[1].strip()
        elif "Bus Id" in line:
            parts = line.split(":", 1)
            pci_device_address = parts[1].strip().lower()
            if len(pci_device_address.split(':')[0]) == 8:
                pci_device_address = pci_device_address[4:].lower()
            gpuinfo["pciAddress"] = pci_device_address
        elif current_section == "Memory Usage":
            if "Total" in line:
                total_memory = line.split(":")[1].strip()
                gpuinfo["memory"] = total_memory
            elif "Used" in line:
                used_memory = line.split(":")[1].strip()
                gpuinfo["memoryUsage"] = used_memory
        elif current_section == "Utilization":
            if "Xpu" in line and "%" in line:
                xpu_utilization = line.split(":")[1].strip()
                gpuinfo["xpuUtilization"] = xpu_utilization
        elif "Enforced Power Limit" in line:
            gpuinfo["power"] = line.split(":")[1].strip()
        elif "Power Draw" in line:
            gpuinfo["powerDraw"] = line.split(":")[1].strip()
        elif "XPU Current Temp" in line:
            gpuinfo["temperature"] = line.split(":")[1].strip()

    logger.info("kunlunxin gpu info: %s" % gpuinfo)
    gpuinfos.append(gpuinfo)
    return gpuinfos


def get_gpu_status_cmd(pci_device_address, iswindows=False):
    cmd = "lspci -s {}".format(pci_device_address)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_shut_nvidia_persistence_cmd(iswindows=False):
    cmd = "ps -ef | grep nvidia-persistenced | grep -v grep | awk '{print $2}' | xargs -r kill -15"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def has_nvidia_gpu():
    r, _, _ = bash_roe("which nvidia-smi")
    if r != 0:
        return False
    r, o, e = bash_roe("nvidia-smi -L")
    return r == 0 and o and len(o.strip()) > 0


_nvidia_persistenced_active = False
_nvidia_persistenced_lock = threading.Lock()


def ensure_nvidia_persistenced_once(timeout=5):
    global _nvidia_persistenced_active

    with _nvidia_persistenced_lock:
        # If already running, nothing to do
        r, o, e = bash_roe("pgrep -f nvidia-persistenced || true")
        is_running = bool(o and o.strip())

        if is_running:
            _nvidia_persistenced_active = True
            return True

        if _nvidia_persistenced_active:
            _nvidia_persistenced_active = False
            logger.debug(
                'nvidia-persistenced stopped, will retry in next cycle')
            return True

        start_cmd = "nohup nvidia-persistenced >/dev/null 2>&1 &"
        logger.info('starting nvidia-persistenced with: %s' % start_cmd)
        bash_roe(start_cmd)

        # Wait for it to appear
        time.sleep(timeout)
        r, o, e = bash_roe("pgrep -f nvidia-persistenced || true")
        if o and o.strip():
            return True
        else:
            logger.warning(
                'nvidia-persistenced did not appear after start attempt')
            return False


def start_nvidia_persistenced_monitor(poll_interval=60 * 2, stop_event=None):
    """Monitor nvidia-persistenced and restart it if it dies while GPU exists."""
    logger.info(
        "start_nvidia_persistenced_monitor: starting monitor (interval=%s)" % poll_interval)
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        if not has_nvidia_gpu():
            stop_event.wait(poll_interval)
            continue

        r = ensure_nvidia_persistenced_once()
        if not r:
            logger.warning(
                "nvidia-persistenced not running and could not be started")

        stop_event.wait(poll_interval)


def watch_and_ensure_nvidia_persistenced(poll_interval=30, stop_event=None):
    """Watch for GPUs appearing later. Once detected, ensure persistenced and start monitor, then exit."""
    logger.info(
        "watch_and_ensure_nvidia_persistenced: watching for NVIDIA GPU (interval=%s)" % poll_interval)
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        if has_nvidia_gpu():
            ensure_nvidia_persistenced_once()
            thread.ThreadFacade.run_in_thread(start_nvidia_persistenced_monitor, [
                                              poll_interval, stop_event])
            return

        stop_event.wait(poll_interval)


def get_alibaba_ppu_product_name_cmd(iswindows=False):
    """Get Alibaba PPU product name command"""
    cmd = "ppu-smi -q | grep 'Product Name'"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_alibaba_ppu_product_name(output):
    """Parse Alibaba PPU product name from ppu-smi -q output"""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Product Name" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
    return None


def get_alibaba_ppu_basic_info_cmd(iswindows=False):
    """Get Alibaba PPU basic info command (PCI address, memory, power limit, serial)"""
    cmd = "ppu-smi --query-ppu=gpu_bus_id,memory.total,power.limit,gpu_serial --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_alibaba_ppu_metric_info_cmd(iswindows=False):
    """Get Alibaba PPU metric info command (PCI address, utilization, temperature, power draw, memory utilization, pcie tx/rx, serial)"""
    cmd = "ppu-smi --query-ppu=gpu_bus_id,utilization.ppu,temperature.ppu,power.draw,utilization.memory,pcie.throughput.tx,pcie.throughput.rx,gpu_serial --format=csv,noheader"
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def parse_alibaba_ppu_output(output):
    """
    Parse Alibaba PPU basic info output.

    Input format:
    00000000:08:00.0, 98304 MiB, 400.00 W, 02A8B95253C002B8

    Returns list of dicts with pciAddress, memory, power, serialNumber
    """
    gpuinfos = []
    for line in output.split('\n'):
        if len(line.strip()) == 0:
            continue
        parts = line.split(',')
        if len(parts) < 4:
            continue

        gpuinfo = {}
        pci_address = parts[0].strip().lower()
        # Remove domain prefix if 8 chars (e.g., 00000000:08:00.0 -> 0000:08:00.0)
        if len(pci_address.split(':')[0]) == 8:
            pci_address = pci_address[4:].lower()

        gpuinfo["pciAddress"] = pci_address
        gpuinfo["memory"] = parts[1].strip()
        gpuinfo["power"] = parts[2].strip()
        gpuinfo["serialNumber"] = parts[3].strip()
        gpuinfos.append(gpuinfo)

    return gpuinfos


def parse_alibaba_ppu_metric_output(output):
    """
    Parse Alibaba PPU metric info output.

    Input format:
    00000000:08:00.0, 0 %, 27 C, 83.03 W, 02A8B95253C002B8

    Returns list of dicts with pciAddress, utilization, temperature, power, serialNumber
    """
    gpuinfos = []
    for line in output.split('\n'):
        if len(line.strip()) == 0:
            continue
        parts = line.split(',')
        if len(parts) < 5:
            continue

        gpuinfo = {}
        pci_address = parts[0].strip().lower()
        # Remove domain prefix if 8 chars
        if len(pci_address.split(':')[0]) == 8:
            pci_address = pci_address[4:].lower()

        gpuinfo["pciAddress"] = pci_address
        gpuinfo["utilization"] = parts[1].replace('%', '').strip()
        gpuinfo["temperature"] = parts[2].replace('C', '').strip()
        gpuinfo["power"] = parts[3].replace('W', '').strip()
        gpuinfo["serialNumber"] = parts[4].strip()
        gpuinfos.append(gpuinfo)

    return gpuinfos


# =============================================================================
# Unified Simplified Interface - One-line call handles all logic
# =============================================================================

def get_info(pci_address=None, pci_device=None, vendor_name=None):
    """
    Unified GPU information collection interface - one-line call handles all logic

    Automatically handles:
    - Auto-identify vendor (if not provided)
    - Prioritize plugin (no environment variable check, try directly)
    - Auto fallback to legacy when plugin fails
    - Handle all vendor-specific fields (Huawei npuId, product name, etc.)

    Args:
        pci_address: PCI address string, e.g., "0000:3b:00.0"
        pci_device: PciDeviceTO object (optional, auto-extract pci_address and vendor)
        vendor_name: VendorEnum value (optional, auto-identify)

    Returns:
        dict: GPU information dictionary, format:
        {
            "memory": "15360 MiB",
            "power": "70.00 W", 
            "serialNumber": "...",
            "isDriverLoaded": True,
            # vendor-specific fields (e.g., Huawei's npuId, isIsolated, productName, aiosRankTable, etc.)
        }
        Returns None if collection fails or device is not a GPU
    """
    # 1. Extract pci_address and vendor_name
    if pci_device:
        pci_address = pci_device.pciDeviceAddress
        if not vendor_name and hasattr(pci_device, 'vendor'):
            vendor_name = pci_device.vendor

    if not pci_address:
        return None

    # Normalize PCI address
    pci_address = pci_address.lower().strip()
    if len(pci_address.split(':')[0]) == 8:
        pci_address = pci_address[4:]

    # 2. Try using plugin (no environment variable check, try directly)
    try:
        from zstacklib.gpu import (
            get_gpu_vendor,
            get_vendor_enum_mapping,
        )

        # Get mapping from vendor enum to plugin vendor name
        vendor_enum_mapping = get_vendor_enum_mapping()
        plugin_vendor_name = vendor_enum_mapping.get(
            vendor_name) if vendor_name else None

        if plugin_vendor_name:
            plugin = get_gpu_vendor(plugin_vendor_name)
            if plugin and plugin.is_available():
                # Use plugin to collect information
                gpu_infos = plugin.get_basic_info()
                for gpu_info in gpu_infos:
                    # Plugin returned pci_address is already normalized, compare directly
                    if gpu_info.pci_address.lower() == pci_address.lower():
                        result = gpu_info.to_addon_dict()

                        # Handle vendor-specific extra fields
                        if vendor_name == VendorEnum.HUAWEI:
                            # Huawei special handling: npuId, isIsolated already in extra
                            result.update(gpu_info.extra)

                            # Collect product name and aios rank table (using legacy functions)
                            try:
                                npu_ids = plugin.get_npu_ids()  # Class method
                                if npu_ids:
                                    r, o, e = bash_roe(
                                        get_huawei_gpu_product_name_cmd(npu_ids))
                                    if r == 0 and o and "not support" not in o:
                                        product_type = get_huawei_product_type(
                                            o)
                                        if product_type:
                                            result["productName"] = product_type

                                    # Collect aios rank table
                                    try:
                                        aios_rank_table = get_huawei_gpu_aios_rank_table_dict(
                                            npu_ids)
                                        if aios_rank_table:
                                            result["opaque"] = {
                                                "aiosRankTable": aios_rank_table}
                                    except Exception as e:
                                        logger.debug(
                                            "Failed to get aios rank table: %s" % str(e))
                            except Exception as e:
                                logger.debug(
                                    "Failed to get Huawei product name: %s" % str(e))

                        elif vendor_name == VendorEnum.TIANSHU:
                            # Tianshu special handling: product name
                            try:
                                r, o, e = bash_roe(
                                    get_tianshu_gpu_product_name_cmd())
                                if r == 0 and o:
                                    product_name = get_tianshu_product_name(o)
                                    if product_name:
                                        result["productName"] = product_name
                            except Exception as e:
                                logger.debug(
                                    "Failed to get Tianshu product name: %s" % str(e))

                        elif vendor_name == VendorEnum.ALIBABA:
                            # Alibaba special handling: product name
                            try:
                                r, o, e = bash_roe(
                                    get_alibaba_ppu_product_name_cmd())
                                if r == 0 and o:
                                    product_name = get_alibaba_ppu_product_name(
                                        o)
                                    if product_name:
                                        result["productName"] = product_name
                            except Exception as e:
                                logger.debug(
                                    "Failed to get Alibaba product name: %s" % str(e))

                        return result
    except Exception as e:
        logger.debug("Plugin failed for %s, fallback to legacy: %s" %
                     (pci_address, str(e)))

    # 3. Fallback to legacy (error tolerance mechanism)
    return _get_info_legacy(pci_address, vendor_name)


def _get_info_legacy(pci_address, vendor_name):
    """
    Legacy method to collect GPU information (as fallback error tolerance)
    """
    if not vendor_name:
        return None

    pci_address = pci_address.lower()

    # Legacy vendor handler function mapping
    legacy_handlers = {
        VendorEnum.NVIDIA: _collect_nvidia_legacy,
        VendorEnum.AMD: _collect_amd_legacy,
        VendorEnum.HAIGUANG: _collect_haiguang_legacy,
        VendorEnum.HUAWEI: _collect_huawei_legacy,
        VendorEnum.TIANSHU: _collect_tianshu_legacy,
        VendorEnum.VASTAI: _collect_vastai_legacy,
        VendorEnum.ENFLAME: _collect_enflame_legacy,
        VendorEnum.ALIBABA: _collect_alibaba_legacy,
    }

    handler = legacy_handlers.get(vendor_name)
    if not handler:
        return None

    try:
        return handler(pci_address)
    except Exception as e:
        logger.warn("Legacy handler failed for %s (%s): %s" %
                    (vendor_name, pci_address, str(e)))
        return None


def _collect_nvidia_legacy(pci_address):
    """NVIDIA legacy collection"""
    r, o, e = bash_roe("which nvidia-smi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, o, e = bash_roe(get_nvidia_gpu_basic_info_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_infos = parse_nvidia_gpu_output(o)
    for gpuinfo in gpu_infos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }
            return result

    return {"isDriverLoaded": False}


def _collect_amd_legacy(pci_address):
    """AMD legacy collection"""
    r, o, e = bash_roe("which rocm-smi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, o, e = bash_roe(get_amd_gpu_basic_info_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_infos = parse_amd_gpu_output(o)
    for gpuinfo in gpu_infos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }
            return result

    return {"isDriverLoaded": False}


def _collect_haiguang_legacy(pci_address):
    """Haiguang legacy collection"""
    r, o, e = bash_roe("which hy-smi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, o, e = bash_roe(get_hy_gpu_basic_info_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_infos = parse_hy_gpu_output(o)
    for gpuinfo in gpu_infos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }
            return result

    return {"isDriverLoaded": False}


def _collect_huawei_legacy(pci_address):
    """Huawei legacy collection (includes special fields)"""
    r, o, e = bash_roe("which npu-smi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, npu_ids_out = bash_ro(get_huawei_gpu_npu_id_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    npu_ids = get_huawei_npu_id(npu_ids_out)
    if not npu_ids:
        return {"isDriverLoaded": False}

    npu_infos = []
    npu_id_map = {}
    for npu_id in npu_ids:
        r, o, e = bash_roe(get_huawei_gpu_basic_info_cmd(npu_id))
        if r != 0:
            continue

        parsed_infos = parse_huawei_gpu_output_by_npu_id(o)
        for info in parsed_infos:
            pci_addr = info.get("pciAddress", "")
            if pci_addr:
                npu_id_map[pci_addr.lower()] = npu_id
        npu_infos.extend(parsed_infos)

    # Find matching GPU
    for npu_info in npu_infos:
        if pci_address not in npu_info.get("pciAddress", "").lower():
            continue

        result = {
            "memory": npu_info.get("memory"),
            "power": npu_info.get("power"),
            "serialNumber": npu_info.get("serialNumber"),
            "isDriverLoaded": True,
        }

        # Add Huawei special fields
        matched_npu_id = npu_id_map.get(pci_address)
        if matched_npu_id:
            result["npuId"] = matched_npu_id
            try:
                is_isolated = check_huawei_npu_is_isolated(
                    matched_npu_id, npu_ids)
                result["isIsolated"] = is_isolated
            except Exception as ex:
                result["isIsolated"] = False

        # Collect product name
        try:
            r, o, e = bash_roe(get_huawei_gpu_product_name_cmd(npu_ids))
            if r == 0 and o and "not support" not in o:
                product_type = get_huawei_product_type(o)
                if product_type:
                    result["productName"] = product_type
        except Exception as e:
            logger.debug("Failed to get Huawei product name: %s" % str(e))

        # Collect aios rank table
        try:
            aios_rank_table = get_huawei_gpu_aios_rank_table_dict(npu_ids)
            if aios_rank_table:
                result["opaque"] = {"aiosRankTable": aios_rank_table}
        except Exception as e:
            logger.debug("Failed to get aios rank table: %s" % str(e))

        return result

    return {"isDriverLoaded": False}


def _collect_tianshu_legacy(pci_address):
    """Tianshu legacy collection"""
    r, o, e = bash_roe("which ixsmi")
    if r != 0:
        return {"isDriverLoaded": False}

    if shell.run(is_tianshu_v1()) == 0:
        cmd = get_tianshu_gpu_basic_info_cmd_v1()
    else:
        cmd = get_tianshu_gpu_basic_info_cmd_v2()

    r, o, e = bash_roe(cmd)
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_infos = parse_tianshu_gpu_output(o)
    for gpuinfo in gpu_infos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }

            # Collect product name
            try:
                r, o, e = bash_roe(get_tianshu_gpu_product_name_cmd())
                if r == 0 and o:
                    product_name = get_tianshu_product_name(o)
                    if product_name:
                        result["productName"] = product_name
            except Exception as e:
                logger.debug("Failed to get Tianshu product name: %s" % str(e))

            return result

    return {"isDriverLoaded": False}


def _collect_vastai_legacy(pci_address):
    """Vastai legacy collection"""
    try:
        from zstacklib.gpu.vendors.vastai import Vastai
        from zstacklib.utils import shell, sizeunit
    except ImportError:
        return {"isDriverLoaded": False}
    
    r, o, e = bash_roe("which vasmi")
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_type = Vastai.get_vastai_type()
    gpuinfos = []

    data = shell.run_with_json_result("vasmi getmem --display-format=json")
    if data:
        for elem in data.get("elem", []):
            gpuinfo = {}
            pci_bus = elem.get("pci_bus", "N/A")
            gpuinfo["pciAddress"] = Vastai.normalize_pci_address(pci_bus)
            gpuinfo["serialNumber"] = elem.get("sn", "N/A")
            key = "Physical" if gpu_type == "AI" else "Physical memory"
            row_memory = elem.get("vals", {}).get(key, {}).get("value", "N/A")
            gpuinfo["memory"] = row_memory if row_memory == "N/A" else str(
                sizeunit.get_size(row_memory)) + "B"
            gpuinfos.append(gpuinfo)

    summary_data = shell.run_with_json_result(
        "vasmi summary --display-format=json")
    if summary_data:
        for elem in summary_data.get("elem", []):
            dev_bus_id_raw = elem.get("vals", {}).get(
                "devBusId", {}).get("value", "N/A")
            dev_bus_id = Vastai.normalize_pci_address(dev_bus_id_raw)
            max_power = elem.get("vals", {}).get(
                "P_Cap", {}).get("value", "N/A")
            for gpuinfo in gpuinfos:
                if gpuinfo["pciAddress"] == dev_bus_id:
                    gpuinfo["power"] = max_power

    for gpuinfo in gpuinfos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }
            return result

    return {"isDriverLoaded": False}


def _collect_enflame_legacy(pci_address):
    """Enflame legacy collection"""
    r, o, e = bash_roe("which efsmi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, o, e = bash_roe(get_enflame_gpu_info_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    for info in parse_enflame_gpu_output(o):
        if pci_address not in info.get("pciAddress", "").lower():
            continue

        mem = info.get("memory", "")
        power = info.get("powerCap", "")
        serial = info.get("serialNumber", "")

        result = {"isDriverLoaded": True}

        if mem and re.match(r"^\s*\d+\s*MiB\s*$", mem, re.IGNORECASE):
            result["memory"] = mem.strip()
        if power and re.match(r"^\s*\d+(\.\d+)?\s*W\s*$", power, re.IGNORECASE):
            result["power"] = power.strip()
        if serial and serial.strip():
            result["serialNumber"] = serial

        return result

    return {"isDriverLoaded": False}


def _collect_alibaba_legacy(pci_address):
    """Alibaba legacy collection"""
    r, o, e = bash_roe("which ppu-smi")
    if r != 0:
        return {"isDriverLoaded": False}

    r, o, e = bash_roe(get_alibaba_ppu_basic_info_cmd())
    if r != 0:
        return {"isDriverLoaded": False}

    gpu_infos = parse_alibaba_ppu_output(o)
    for gpuinfo in gpu_infos:
        if pci_address in gpuinfo.get("pciAddress", "").lower():
            result = {
                "memory": gpuinfo.get("memory"),
                "power": gpuinfo.get("power"),
                "serialNumber": gpuinfo.get("serialNumber"),
                "isDriverLoaded": True,
            }

            # Collect product name
            try:
                r, o, e = bash_roe(get_alibaba_ppu_product_name_cmd())
                if r == 0 and o:
                    product_name = get_alibaba_ppu_product_name(o)
                    if product_name:
                        result["productName"] = product_name
            except Exception as e:
                logger.debug("Failed to get Alibaba product name: %s" % str(e))

            return result

    return {"isDriverLoaded": False}


def get_all_info():
    """
    Collect information for all GPUs

    Returns:
        list: List of GPU information dictionaries
    """
    results = []

    # Try using plugin
    try:
        from zstacklib.gpu import get_all_gpu_vendors
        for vendor_class in get_all_gpu_vendors():
            if not vendor_class.is_available():
                continue
            gpu_infos = vendor_class.get_basic_info()
            for gpu_info in gpu_infos:
                result = gpu_info.to_addon_dict()
                result.update(gpu_info.extra)
                results.append(result)

        if results:
            return results
    except Exception as e:
        logger.debug("Plugin failed, fallback to legacy: %s" % str(e))

    return results


def get_metrics(pci_address=None, pci_device=None, vendor_name=None):
    """
    Collect GPU metrics (for Prometheus)

    Args:
        pci_address: PCI address
        pci_device: PciDeviceTO object
        vendor_name: VendorEnum value

    Returns:
        dict: GPU metrics dictionary, returns None on failure
    """
    # Similar implementation to get_info, but collects metrics
    # Simplified implementation, returns None for now
    return None


def get_all_metrics():
    """
    Collect metrics for all GPUs

    Returns:
        list: List of GPU metrics dictionaries
    """
    results = []

    try:
        from zstacklib.gpu import get_all_gpu_vendors
        for vendor_class in get_all_gpu_vendors():
            if not vendor_class.is_available():
                continue
            metrics_list = vendor_class.collect_metrics()
            for metrics in metrics_list:
                result = {
                    "pci_address": metrics.pci_address,
                    "serial_number": metrics.serial_number,
                    "utilization": metrics.utilization,
                    "memory_utilization": metrics.memory_utilization,
                    "temperature": metrics.temperature,
                    "power_draw": metrics.power_draw,
                    "fan_speed": metrics.fan_speed,
                    "pcie_tx_bytes": metrics.pcie_tx_bytes,
                    "pcie_rx_bytes": metrics.pcie_rx_bytes,
                }
                result.update(metrics.extra)
                results.append(result)
    except Exception as e:
        logger.debug("Failed to collect metrics via plugin: %s" % str(e))

    return results
