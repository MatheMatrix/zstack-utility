import queue
from zstacklib.utils import singleton

@singleton.singleton
class VmPluginQueueSingleton(object):
    queue = queue.Queue()
