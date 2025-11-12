from kvmagent import kvmagent
from zstacklib.utils import gpu, thread
from zstacklib.utils import log
import threading

log.configure_log('/var/log/zstack/zstack-kvmagent.log')
logger = log.get_logger(__name__)


class AgentRsp(object):
    def __init__(self):
        self.success = True
        self.error = None


class NvidiaPersistencedMonitor(kvmagent.KvmAgent):
    _lock = threading.Lock()

    def __init__(self):
        self.state = False
        self._monitor_thread = None
        self.config = None

    def configure(self, config):
        self.config = config

    def start(self):
        with self._lock:
            if not self.state:
                self.state = True
                self.start_nvidia_persistenced_monitor()
                logger.debug("start NvidiaPersistencedMonitor")

    def stop(self):
        with self._lock:
            if self.state:
                self.state = False
                logger.debug("stop NvidiaPersistencedMonitor")

                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.stop()
                    self._monitor_thread.join(timeout=5)
                    self._monitor_thread = None

    @kvmagent.replyerror
    def start_nvidia_persistenced_monitor(self):
        self._monitor_thread = thread.ThreadFacade.run_in_thread(
            gpu.watch_and_ensure_nvidia_persistenced)
