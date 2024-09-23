from zstacklib.utils import shell
from zstacklib.utils.multi_singleflight import multi_sf

sensor_info_from_ipmi = ""


def get_sensor_info_from_ipmi():
    return sensor_info_from_ipmi


def get_ipmi_sensor_info():
    global sensor_info_from_ipmi
    ipmi_sensor_cmd = "ipmitool sdr elist"
    cache_time = 20

    def ipmi_sensor_call():
        return shell.call(ipmi_sensor_cmd)

    sensor_info_from_ipmi = multi_sf.do(ipmi_sensor_cmd, cache_time, ipmi_sensor_call)
    return sensor_info_from_ipmi
