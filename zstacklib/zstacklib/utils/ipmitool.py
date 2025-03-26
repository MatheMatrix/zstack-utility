from zstacklib.utils import shell
import log
import time
import threading
from zstacklib.utils.singleflight import Group

logger = log.get_logger(__name__)

sft = Group()

_cache_lock = threading.Lock()
ipmi_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 60
}


def get_sensor_info_from_ipmi(force_refresh=False):
    ipmi_sensor_cmd = "ipmitool sdr elist"

    def ipmi_sensor_call():
        try:
            return shell.call(ipmi_sensor_cmd), None
        except Exception as e:
            return None, str(e)

    current_time = int(time.time())
    if not force_refresh and ipmi_cache["data"] and (current_time - ipmi_cache["timestamp"] < ipmi_cache["ttl"]):
        logger.debug("returning ipmi sensor data from cache")
        return ipmi_cache["data"]

    result = sft.do(ipmi_sensor_cmd, ipmi_sensor_call)
    if result.error:
        logger.warn("failed to get ipmi sensor info: %s" % result.error)
        return ''

    with _cache_lock:
        ipmi_cache["data"] = result.value[0]
        ipmi_cache["timestamp"] = int(time.time())
    return ipmi_cache["data"]
