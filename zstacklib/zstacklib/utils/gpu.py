import os

from zstacklib.utils import log, linux
from zstacklib.utils.bash import *
import json

logger = log.get_logger(__name__)


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
        gpu_info_json = json.loads(output.strip())
        for card_name, card_data in gpu_info_json.items():
            gpuinfo = {}
            pci_device_address = card_data['PCI Bus'].lower()
            if len(pci_device_address.split(':')[0]) == 8:
                pci_device_address = pci_device_address[4:].lower()

            gpuinfo["pciAddress"] = pci_device_address
            gpuinfo["memory"] = card_data['VRAM Total Memory (B)']
            gpuinfo["power"] = card_data['Average Graphics Package Power (W)']
            gpuinfo["serialNumber"] = card_data['Serial Number']
            gpuinfos.append(gpuinfo)
    except Exception as e:
        logger.error("amd query gpu is error, %s " % e)

    return gpuinfos


def parse_hy_gpu_output(output):
    gpuinfos = []
    try:
        gpu_info_json = json.loads(output)
        for card_name, card_data in gpu_info_json.items():
            gpuinfo = {}
            pci_device_address = card_data['PCI Bus'].lower()
            if len(pci_device_address.split(':')[0]) == 8:
                pci_device_address = pci_device_address[4:].lower()

            gpuinfo["pciAddress"] = pci_device_address
            gpuinfo["memory"] = card_data['Available memory size (MiB)'] + " MiB"
            gpuinfo["power"] = card_data['Max Graphics Package Power (W)']
            gpuinfo["serialNumber"] = card_data['Serial Number']
            gpuinfos.append(gpuinfo)
    except  Exception as e:
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
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Serial Number" in line:
            gpuinfo["serialNumber"] = line.split(":")[1].strip()
        elif "PCIe Bus Info" in line:
            gpuinfo["pciAddress"] = line.partition(": ")[-1].strip().lower()
        elif "DDR Capacity(MB)" in line or "HBM Capacity" in line:
            memory_value = int(line.split(":")[1].strip().split()[0])
            total_memory += memory_value
        elif "Power Dissipation" in line or "Real-time Power(W)" in line:
            gpuinfo["power"] = line.split(":")[1].strip()

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
    cmd = "npu-smi info -t board -i {0};npu-smi info -i {0} -t memory;npu-smi info -t power -i {0}".format(npu_id)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def get_huawei_gpu_product_name_cmd(npu_id, iswindows=False):
    cmd = "npu-smi info -t product -i {0}".format(npu_id)
    if iswindows:
        cmd = cmd.replace(" ", "|")
    return cmd


def is_hygon_gpu_cmd(pci_addr):
    cmd = "hy-smi --showbus | grep {0}".format(pci_addr)
    return cmd


def reload_hygon_gpu_driver_cmd():
    cmd = "hy-smi --unloaddriver && hy-smi --loaddriver"
    return cmd

def get_vastai_type():
    r, o, e = bash_roe("lspci | grep Vastai")
    first_line = o.split('\n')[0]
    if "SG100" in first_line:
        return "3D"
    elif "SV100" in first_line:
        return "AI"
    return None

def run_json_command(cmd):
    r, output, e = bash_roe(cmd)
    if r != 0 or output is None:
        return None
    json_start = output.find('{')
    if json_start == -1:
        logger.error("No JSON data found in command %s output, output: %s", cmd, output)
        return None
    json_str = output[json_start:]
    try:
        return json.loads(json_str)
    except ValueError as ve:
        logger.error("JSON decode failed for command: %s, error: %s", cmd, ve)
        return None