import weakref
import threading
import functools
from zstacklib.utils import log

try:
    # Python 3
    import queue as Queue
except ImportError:
    # Python 2 fallback
    import Queue

logger = log.get_logger(__name__)
_internal_lock = threading.RLock()
_queues = weakref.WeakValueDictionary()
TOKEN = object()

class _WrappedQueue(object):
    def __init__(self, maxsize):
        self.q = Queue.Queue(maxsize)
        self.lock = threading.RLock()

def _get_queue(name, maxsize):
    with _internal_lock:
        q = _queues.get(name)
        if q is None:
            q = _WrappedQueue(maxsize)
            _queues[name] = q
        return q

class NamedQueue(object):
    def __init__(self, name, maxsize, block=True, timeout=None, lock_enabled=False):
        self.name = name
        self.maxsize = maxsize
        self.block = block
        self.timeout = timeout
        self._lock_enabled = lock_enabled
        self._lock_acquired = False
        self.enqueued = False

    def __enter__(self):
        self.queue = _get_queue(self.name, self.maxsize)
        try:
            self.queue.q.put(TOKEN, block=self.block, timeout=self.timeout)
            self.enqueued = True
            if self._lock_enabled:
                self.queue.lock.acquire()
                self._lock_acquired = True
        except Queue.Full:
            self.enqueued = False

        return self


    def __exit__(self, type, value, traceback):
        if self.enqueued:
            try:
                self.queue.q.get_nowait()
            except Queue.Empty:
                logger.debug("queue was unexpectedly empty in __exit__")
            except Exception as e:
                logger.debug("dequeue error %s" % (str(e)))

        if self._lock_enabled and self._lock_acquired:
            try:
                self.queue.lock.release()
            except Exception as e:
                logger.debug("release lock error %s" % (str(e)))


def _fail_queue_default_handler(f, *args, **kwargs):
    logger.debug("queue is full, skip to execute func %s " % f.__name__)

def queue(name='defaultQueue', maxsize=10, block=True, timeout=None, lock_enabled=False, fail_queue_handler=_fail_queue_default_handler):
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            with NamedQueue(name, maxsize, block, timeout, lock_enabled) as nq:
                if not nq.enqueued and fail_queue_handler is not None:
                    return fail_queue_handler(f, *args, **kwargs)
                elif not nq.enqueued:
                    return

                retval = f(*args, **kwargs)
            return retval
        return inner
    return wrap